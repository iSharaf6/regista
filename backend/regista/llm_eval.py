"""Score the live agents on fixed evaluation matches with whatever model is configured.

    REGISTA_LLM=foundry FOUNDRY_PROJECT_ENDPOINT=... FOUNDRY_MODEL=gpt-4.1-mini regista llm-eval

Moments come from evaluation seeds, never the demo seed 16 the prompts were tuned on. They are stratified across
moment kinds, and each carries the match context as it stood when the moment was detected. Reports:

- the full workflow (Analyst -> Narrator || Localizer -> Verifier -> Rewriter loop -> Fallback): first-draft and
  final verification, fallbacks, attempts, latency, tokens and cost;
- two single-agent baselines on the same moments, facts, grounding and model: one call writes every language with no
  checker loop (one-shot), and the same single agent with the same Verifier feedback and the same draft budget as the
  workflow (rewriting only its failing languages) - the fair test of what splitting the work across agents adds;
- a constructed Verifier probe (errors planted with the Verifier's own figure pools: a regression test, not
  independent evidence), hand-written believable errors in every language (wrong tallies, manpower, units and
  minutes) and deterministic templates (how many it wrongly rejects);
- the Pundit's tool use on the demo match and whether model recaps survive the Verifier.

"Verified" means accepted by the Verifier's checks, not independent proof that every statement is true.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter, defaultdict, deque
from itertools import zip_longest
from typing import Any

from agent_framework import Agent

from .agents.clients import parse_json
from .agents.config import load_config
from .agents.prompts import SAFETY, UNITS
from .agents.pundit import Pundit
from .agents.recap import normalize_recap, offline_recap, recap_evidence, recap_fields, recap_payload
from .agents.story import AgentFailure, AgentRuntime, StoryJob, _shape, _template, metric_units, run_story
from .agents.telemetry import percentile
from .agents.templates import MEN, num
from .agents.tools import MatchTools
from .agents.verifier import _supported, allowed_numbers, unit_numbers, verify_texts
from .evaluation import replay
from .intel.moments import MomentDetector
from .intel.state import MatchState
from .runtime.session import _event_order, match_context
from .sim.engine import simulate

# Fixed evaluation matches, separate from the demo seed 16 the prompts were developed on. Their failures have guided
# later repairs, so they are a fixed benchmark, not an untouched final holdout.
EVAL_SEEDS = (101, 202, 303, 404)
PRICE_PER_M = (0.40, 1.60)  # gpt-4.1-mini Global Standard list price, USD per million input / output tokens

QUESTIONS = [
    ("en", "analyst", "Why are Northbridge winning the ball so high since the hour?"),
    ("es", "casual", "¿Quién es el mejor jugador del partido?"),
    ("ar", "casual", "ما هي احتمالات فوز كل فريق؟"),
    ("fr", "new_fan", "Qui contrôle le match en ce moment, et pourquoi ?"),
]

BASELINE = f"""You are a football commentary assistant. In ONE response, write on-screen copy about one live football
MOMENT for every language in LANGUAGES, for three audiences: casual (warm, at most one number), analyst (precise, two or
three numbers), new_fan (plain words, explain jargon). For each give caption (<= 48 characters), line (<= 200
characters) and explainer (<= 320 characters). GROUNDING gives, per language, FIGURES (the only numbers you may use,
already formatted), ALLOWED_PLAYERS (the only players you may name) and TEAMS. Keep names unchanged. Describe only what
FACTS show: never invent what happened before or after, and never call a shot a header, penalty or free kick unless
FACTS say so. {UNITS}
If FEEDBACK is present it lists problems a fact-checker found in your previous draft, per language: return only those
languages, with every problem fixed. {SAFETY}
Return ONLY JSON: {{"<language code>": {{"casual": {{"caption","line","explainer"}}, "analyst": {{...}}, "new_fan": {{...}}}}, ...}}"""

GOAL_WORD = {"en": "goals", "es": "goles", "fr": "buts", "ar": "هدفاً", "pt": "gols"}
FORTY_SEVEN = {"en": "forty-seven", "es": "cuarenta y siete", "fr": "quarante-sept", "pt": "quarenta e sete"}
HEADER = {"en": "A header.", "es": "De cabeza.", "fr": "De la tête.", "ar": "بالرأس.", "pt": "De cabeça."}
PENALTY = {"en": "From the penalty spot.", "es": "De penalti.", "fr": "Sur penalty.", "ar": "من ركلة جزاء.", "pt": "De pênalti."}


# Hand-written believable errors, independent of the Verifier's own helpers: the mistakes a fluent model actually makes.
TALLY = {"en": "{p} now has {n} goals in this match.", "es": "{p} ya suma {n} goles en el partido.",
         "fr": "{p} compte désormais {n} buts dans ce match.", "pt": "{p} já soma {n} gols na partida.",
         "ar": "{p} يرفع رصيده إلى {n} أهداف في المباراة."}
TALLY_WORDS = {"en": "{p} has now scored {w} goals.", "es": "{p} ya lleva {w} goles.", "fr": "{p} a déjà marqué {w} buts.",
               "pt": "{p} já marcou {w} gols.", "ar": "{p} سجل {w} أهداف."}
SMALL_WORD = {"en": {2: "two", 3: "three"}, "es": {2: "dos", 3: "tres"}, "fr": {2: "deux", 3: "trois"},
              "pt": {2: "dois", 3: "três"}, "ar": {2: "اثنين", 3: "ثلاثة"}}
BRACE = {"en": "{p} completes a brace.", "es": "{p} firma un doblete.", "fr": "{p} signe un doublé.",
         "pt": "{p} faz uma dobradinha.", "ar": "{p} يسجل ثنائية."}
MANPOWER = {"en": "{t} are down to {w} men.", "es": "{t} se queda con {w} jugadores.", "fr": "{t} est réduit à {w} joueurs.",
            "pt": "{t} fica com {w} jogadores.", "ar": "{t} يكمل {w}."}
PER_MINUTE = {"en": "{t} now press {r} times per minute.", "es": "{t} presiona ahora {r} veces por minuto.",
              "fr": "{t} presse désormais {r} fois par minute.", "pt": "{t} pressiona agora {r} vezes por minuto.",
              "ar": "{t} يضغط الآن {r} مرة كل دقيقة."}
WRONG_MINUTE = {"en": "It came in the {m}th minute.", "es": "Llegó en el minuto {m}.", "fr": "C'est arrivé à la {m}e minute.",
                "pt": "Aconteceu no minuto {m}.", "ar": "جاء ذلك في الدقيقة {m}."}


def believable(job: StoryJob) -> dict[str, list[bool]]:
    """Append one hand-written, plausible mistake to verified copy, per language, and record whether it is caught."""
    ev, facts = job.evidence(), job.moment.get("facts", {})
    players = set(job.moment.get("players", []))
    kind = job.moment.get("kind")
    team = job.names["teams"].get(job.moment.get("team") or "", "")
    scorer = job.roster_names.get(facts.get("scorer") or "", "")
    minute = int(str(job.moment.get("clock", "0")).split("+")[0].rstrip("'") or 0)
    out: dict[str, list[bool]] = defaultdict(list)
    for lang in job.languages:
        base = job.narration.get(lang, {}).get("analyst", {}).get("line", "")
        if not base:
            continue
        planted: dict[str, str] = {"wrong minute": WRONG_MINUTE[lang].format(m=minute + 3)}
        if kind == "goal" and scorer and facts.get("scorer_goals"):
            n = int(facts["scorer_goals"]) + 1
            planted["wrong goal tally"] = TALLY[lang].format(p=scorer, n=n)
            if n in SMALL_WORD[lang]:
                planted["wrong tally in words"] = TALLY_WORDS[lang].format(p=scorer, w=SMALL_WORD[lang][n])
            if facts["scorer_goals"] != 2:
                planted["false brace"] = BRACE[lang].format(p=scorer)
        if kind == "red_card" and team and facts.get("players_remaining"):
            left = int(facts["players_remaining"])
            wrong = left - 1 if left == 10 else left + 1  # "down to nine" after a first red, "ten" after a second
            planted["wrong manpower"] = MANPOWER[lang].format(t=team, w=MEN[lang].get(wrong, wrong) if lang == "ar"
                                                              else MEN[lang].get(wrong, str(wrong)))
        if kind == "press_shift" and team and facts.get("press_rate_after"):
            planted["rate in the wrong unit"] = PER_MINUTE[lang].format(t=team, r=num(facts["press_rate_after"], lang))
        for k, text in planted.items():
            v = verify_texts({lang: {"analyst": {"probe": f"{base} {text}"}}}, ev, players, job.roster_names, claims=facts)
            out[k].append(not v.ok)
    return out


def _reason(issue: str) -> str:
    for key, label in (("not supported", "unsupported figure"), ("does not match", "figure of the wrong kind"),
                       ("not part of this moment", "unexpected player"), ("contradict", "contradicted claim"),
                       ("too long", "too long"), ("brand-safety", "brand safety"), ("malformed", "malformed output")):
        if key in issue:
            return label
    return "other"


def _cost(tokens_in: int, tokens_out: int) -> float:
    return tokens_in / 1e6 * PRICE_PER_M[0] + tokens_out / 1e6 * PRICE_PER_M[1]


def detect(seed: int) -> dict[str, Any]:
    """Replay an evaluation match, capturing each story moment with the context at the instant it was detected."""
    res = simulate("NOR", "CAL", seed, "derby")
    st = MatchState(res.info)
    det = MomentDetector(st)
    evs = sorted(res.events, key=_event_order)
    found: list[tuple[Any, dict[str, Any]]] = []

    def keep(ms: list[Any]) -> None:
        found.extend((m, match_context(st)) for m in ms if m.lane == "story" and m.kind not in {"half_time", "full_time"})

    k = 0
    for fi in range(len(res.frame_t)):
        frame = res.frame(fi)
        ft = frame["t"]
        for sig in st.on_frame(frame):
            keep(det.on_signal(sig, ft, st.clock))
        while k < len(evs) and _event_order(evs[k])[0] <= ft:
            keep(det.on_enriched(st.on_event(evs[k])))
            k += 1
    while k < len(evs):
        keep(det.on_enriched(st.on_event(evs[k])))
        k += 1
    names = {"players": {pid: p.info.short_name for pid, p in st.players.items()}, "teams": dict(st.short)}
    shirts = {pid: p.info.number for pid, p in st.players.items()}
    return {"seed": seed, "state": st, "detector": det, "found": found, "names": names, "shirts": shirts}


def stratify(matches: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """Round-robin across moment kinds (and across matches within a kind) so rare kinds are represented."""
    per_kind: dict[str, list[list[dict[str, Any]]]] = defaultdict(list)
    for mt in matches:
        by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for m, ctx in mt["found"]:
            by_kind[m.kind].append({"m": m, "ctx": ctx, "match": mt})
        for kind, items in by_kind.items():
            per_kind[kind].append(items)
    queues = {kind: deque(x for group in zip_longest(*lists) for x in group if x) for kind, lists in per_kind.items()}
    out: list[dict[str, Any]] = []
    while len(out) < n and any(queues.values()):
        for kind in sorted(queues):
            if queues[kind] and len(out) < n:
                out.append(queues[kind].popleft())
    return out


def make_job(item: dict[str, Any], langs: list[str]) -> StoryJob:
    mt = item["match"]
    st = mt["state"]
    return StoryJob(item["m"].as_dict(), item["ctx"], list(langs), mt["names"], mt["names"]["players"], st.home, st.away,
                    shirts=mt["shirts"])


def probe(job: StoryJob) -> dict[str, list[bool]]:
    """Plant known errors in verified copy and record whether the Verifier catches each one."""
    ev = job.evidence()
    facts = job.moment.get("facts", {})
    players = set(job.moment.get("players", []))
    pool, units = allowed_numbers(*ev), unit_numbers(*ev)

    def free(allowed: set[float]) -> int:
        return next(c for c in (*range(47, 100), *range(101, 1000)) if not _supported(float(c), allowed))

    allowed_names = {job.roster_names.get(p, "") for p in players}
    outsider = next((name for pid, name in job.roster_names.items() if pid not in players and len(name) > 3
                     and not any(name in a or a in name for a in allowed_names if a)), None)
    out: dict[str, list[bool]] = defaultdict(list)
    # how permissive the pooled check is for this moment: the share of 10..99 a bare figure could take and pass
    out["_pool_coverage"] = [_supported(float(x), pool) for x in range(10, 100)]
    for lang in job.languages:
        base = job.narration.get(lang, {}).get("analyst", {}).get("line", "")
        if not base:
            continue
        planted = {
            "unsupported figure": f"{base} {free(pool)}.",
            "speed of the wrong size": f"{base} {free(units['speed'])} km/h.",
            "wrong match minute": f"{base} {free(units['minute'])}'.",
            "wrong goal count": f"{base} {free(units['goals'])} {GOAL_WORD.get(lang, 'goals')}.",
        }
        if lang in FORTY_SEVEN and not _supported(47.0, pool):
            planted["written-out figure"] = f"{base} {FORTY_SEVEN[lang]}."
        if outsider:
            planted["uninvolved player"] = f"{base} {outsider}."
        if "body_part" in facts and facts.get("body_part") != "head":
            planted["contradicted claim"] = f"{base} {HEADER.get(lang, HEADER['en'])}"
        elif "set_piece" in facts and facts.get("set_piece") != "penalty":
            planted["contradicted claim"] = f"{base} {PENALTY.get(lang, PENALTY['en'])}"
        for kind, text in planted.items():
            v = verify_texts({lang: {"analyst": {"probe": text}}}, ev, players, job.roster_names, claims=facts)
            out[kind].append(not v.ok)
    return out


async def baseline(rt: AgentRuntime, job: StoryJob, max_attempts: int = 1) -> dict[str, Any]:
    """One agent writes every language in one call. With max_attempts=1 there is no checker loop (one-shot); with the
    workflow's budget it gets the same Verifier feedback and rewrites only the languages that failed, like the Rewriter."""
    agent = Agent(rt.client, BASELINE, name="SingleAgent", default_options={"temperature": 0.4, "max_tokens": 4000})
    t0 = time.perf_counter()
    ok_langs: list[str] = []
    tokens = [0, 0]
    error = ""
    pending, feedback, attempts = list(job.languages), {}, 0
    copies: dict[str, Any] = {}
    issues: dict[str, list[str]] = {}
    while pending and attempts < max_attempts:
        attempts += 1
        body = {"task": "narrate_all", "moment": job.moment, "context": job.context, "names": job.names, "home": job.home,
                "away": job.away, "UNITS": metric_units(job.moment.get("facts", {}), job.context),
                "LANGUAGES": pending, "GROUNDING": {lang: job.grounding(lang) for lang in pending}}
        if feedback:
            body["FEEDBACK"] = feedback
        failed: dict[str, list[str]] = {}
        try:
            res = await asyncio.wait_for(agent.run(json.dumps(body, ensure_ascii=False, default=str)), timeout=90)
            usage = getattr(res, "usage_details", None) or {}  # billable whether or not the reply parses
            tokens[0] += int(usage.get("input_token_count") or 0)
            tokens[1] += int(usage.get("output_token_count") or 0)
            data = parse_json(res.text)
            for lang in pending:
                try:
                    copy = _shape(data.get(lang))
                except AgentFailure:
                    failed[lang] = [f"[{lang}] missing or malformed output"]
                    continue
                copies[lang] = copy
                v = verify_texts({lang: copy}, job.evidence(), set(job.moment.get("players", [])), job.roster_names,
                                 claims=job.moment.get("facts", {}))
                if v.ok:
                    ok_langs.append(lang)
                else:
                    failed[lang] = v.issues[:6]
        except Exception as exc:  # noqa: BLE001 - a failed baseline call counts as unverified, it must not stop the run
            error = str(exc)[:120]
            failed = {lang: ["no reply"] for lang in pending}
        issues.update(failed)
        for lang in ok_langs:
            issues.pop(lang, None)
        pending, feedback = list(failed), failed
    return {"ok_langs": ok_langs, "all_ok": len(ok_langs) == len(job.languages), "ms": round((time.perf_counter() - t0) * 1000),
            "tokens": tokens, "attempts": attempts, "error": error, "copy": {k: v.get("analyst", {}) for k, v in copies.items()},
            "issues": issues}


async def recap_checks(rt: AgentRuntime, cfg: Any, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Model recaps of the evaluation matches, checked field by field like the live Recap screen."""
    recaps = []
    for mt, lang in ((matches[0], "en"), (matches[0], "ar"), (matches[1 % len(matches)], "es")):
        payload = recap_payload(mt["state"], mt["detector"].moments, mt["names"], lang, "analyst", "full_time")
        t0 = time.perf_counter()
        source = rt.model_name
        try:
            if cfg.is_offline:
                raise AgentFailure("offline")
            data = await rt.call(rt.recapper, "Recap", json.dumps(payload, ensure_ascii=False, default=str))
        except AgentFailure:
            data, source = offline_recap(payload), "deterministic"
        data = normalize_recap(data, payload, mt["names"]["players"])
        fields, problems = recap_fields(data, payload, mt["names"]["players"])  # every field the Recap screen shows
        allowed = {p["id"] for p in payload["top_players"]} | {pid for m in payload["moments"] for pid in m["players"]}
        v = verify_texts({lang: {"analyst": fields}}, recap_evidence(payload), allowed, mt["names"]["players"])
        if problems:
            v.ok, v.issues = False, problems + v.issues
        recaps.append({"seed": mt["seed"], "lang": lang, "source": source, "verified": v.ok, "issues": v.issues[:4],
                       "headline": fields["headline"], "ms": round((time.perf_counter() - t0) * 1000)})
    return recaps


async def run(moments: int = 24, langs: tuple[str, ...] = ("en", "es", "fr", "ar", "pt"), concurrency: int = 2,
              seeds: tuple[int, ...] = EVAL_SEEDS, with_baseline: bool = True, pace_s: float = 0.0) -> dict[str, Any]:
    """pace_s waits between moments so the run stays under the deployment's token quota: without it, back-to-back
    moments throttle each other and latency (and timeouts) measure the quota, not the model."""
    cfg = load_config()
    rt = AgentRuntime(cfg)
    matches = [detect(seed) for seed in seeds]
    items = stratify(matches, moments)
    sem = asyncio.Semaphore(concurrency)
    reasons: Counter[str] = Counter()
    planted: dict[str, list[bool]] = defaultdict(list)
    believed: dict[str, list[bool]] = defaultdict(list)
    coverage: list[bool] = []
    templates = [0, 0]  # checked, wrongly rejected

    async def one(item: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            t0 = time.perf_counter()
            job = await run_story(rt, make_job(item, list(langs)))
            ms = round((time.perf_counter() - t0) * 1000)
            await asyncio.sleep(pace_s)
        verifier = [s for s in job.trace if s["agent"] == "Verifier"]
        for span in verifier:  # why drafts were sent back (each rejection's first issue)
            if span["status"] == "rejected":
                reasons[_reason(span["detail"])] += 1
        if job.verdict_ok:
            for kind, caught in probe(job).items():
                (coverage if kind == "_pool_coverage" else planted[kind]).extend(caught)
            for kind, caught in believable(job).items():
                believed[kind].extend(caught)
        for lang in langs:
            v = verify_texts({lang: _template(job, lang)}, job.evidence(), set(job.moment.get("players", [])),
                             job.roster_names, claims=job.moment.get("facts", {}))
            templates[0] += 1
            templates[1] += 0 if v.ok else 1
        m = item["m"]
        print(f"workflow {m.kind:14} {m.clock:>6} {ms:>6} ms ok={job.verdict_ok} fallback={job.fallback_langs}",
              file=sys.stderr, flush=True)
        # model-written means no language fell back to a template, whether the Fallback node or a writer substituted it
        model_only = not job.fallback_langs and not job.verdict.get("via")
        return {"seed": item["match"]["seed"], "moment": m.kind, "clock": m.clock, "ms": ms, "attempts": job.attempts,
                "first_draft_ok": bool(verifier) and verifier[0]["status"] == "ok" and model_only,
                "fallback_langs": job.fallback_langs, "verified": job.verdict_ok,
                "verified_without_fallback": job.verdict_ok and model_only,
                "model_langs_verified": len([lang for lang in langs if lang not in job.fallback_langs]) if job.verdict_ok else 0,
                "analyst_insight": "model" if job.models.get("Analyst", "").startswith(("foundry", "azure", "openai"))
                                   else "deterministic",
                "copy": {lang: job.narration.get(lang, {}).get("analyst", {}) for lang in langs}}

    t_all = time.perf_counter()
    rows = await asyncio.gather(*(one(it) for it in items))
    story_tokens = [sum(rt.telemetry.tokens[a][i] for a in ("Analyst", "Narrator", "Localizer")) for i in (0, 1)]

    base_rows: list[dict[str, Any]] = []
    loop_rows: list[dict[str, Any]] = []
    if with_baseline and not cfg.is_offline:
        async def b(item: dict[str, Any], attempts: int) -> dict[str, Any]:
            async with sem:
                r = await baseline(rt, make_job(item, list(langs)), attempts)
                r.update(seed=item["match"]["seed"], moment=item["m"].kind, clock=item["m"].clock)
                await asyncio.sleep(pace_s)
            print(f"baseline x{attempts} {item['m'].kind:14} {r['ms']:>6} ms ok_langs={len(r['ok_langs'])} {r['error'][:60]}",
                  file=sys.stderr, flush=True)
            return r
        base_rows = await asyncio.gather(*(b(it, 1) for it in items))
        loop_rows = await asyncio.gather(*(b(it, cfg.max_attempts) for it in items))

    demo_st, _, demo_moments = replay(simulate("NOR", "CAL", 16, "derby"))

    class Ctx:
        state, moments = demo_st, demo_moments

    pundit = Pundit(rt, MatchTools(Ctx()))
    answers = []
    for lang, persona, q in QUESTIONS:
        a = await pundit.ask(q, lang, persona)
        answers.append({"lang": lang, "question": q, "answer": a["answer"], "tools": a["tools"], "model": a["model"], "ms": a["ms"]})

    recaps = await recap_checks(rt, cfg, matches)

    n = max(1, len(rows))
    lat = [r["ms"] for r in rows] or [0]
    report: dict[str, Any] = {
        "model": rt.model_name,
        "eval_seeds": list(seeds),
        "moments": len(rows),
        "moment_kinds": dict(Counter(r["moment"] for r in rows)),
        "languages": list(langs),
        "workflow": {
            "first_draft_verified": round(sum(r["first_draft_ok"] for r in rows) / n, 3),
            "verified": round(sum(r["verified"] for r in rows) / n, 3),
            "verified_without_fallback": round(sum(r["verified_without_fallback"] for r in rows) / n, 3),
            "moments_model_written": f"{sum(r['verified_without_fallback'] for r in rows)}/{len(rows)}",
            "language_outputs_model_written": round(sum(r["model_langs_verified"] for r in rows) / (n * len(langs)), 3),
            "analyst_insight_from_model": round(sum(r["analyst_insight"] == "model" for r in rows) / n, 3),
            "jobs_with_fallback": sum(1 for r in rows if r["fallback_langs"]),
            "mean_attempts": round(sum(r["attempts"] for r in rows) / n, 2),
            "latency_ms": {"p50": percentile(lat, 0.5), "p95": percentile(lat, 0.95)},
            "tokens_in": story_tokens[0], "tokens_out": story_tokens[1],
            "cost_usd_per_moment": round(_cost(*story_tokens) / n, 5) if not cfg.is_offline else 0.0,
        },
        "verifier_probe": {
            "planted_errors": {k: {"planted": len(v), "caught": sum(v)} for k, v in sorted(planted.items())},
            "caught_rate": round(sum(sum(v) for v in planted.values()) / max(1, sum(len(v) for v in planted.values())), 3),
            "note": "constructed: figures chosen with the Verifier's own pools, so a regression test, not independent evidence",
            "believable_errors": {k: {"planted": len(v), "caught": sum(v)} for k, v in sorted(believed.items())},
            "templates_checked": templates[0], "templates_wrongly_rejected": templates[1],
            "bare_figure_pool_coverage_10_99": round(sum(coverage) / max(1, len(coverage)), 2),
        },
        "rejection_reasons": dict(reasons),
        "agents": rt.telemetry.summary()["agents"],
        "pundit": answers,
        "pundit_used_tools": round(sum(1 for a in answers if a["tools"]) / len(answers), 2),
        "recaps": recaps,
        "wall_s": round(time.perf_counter() - t_all, 1),
        "run": {"concurrency": concurrency, "pace_s": pace_s, "timeout_s": cfg.timeout_s, "max_attempts": cfg.max_attempts,
                "baseline_timeout_s": 90,
                "note": "latency is as observed under these timeouts: workflow calls give up after timeout_s and get "
                        "a second draft, a single-agent call writes every language and is allowed baseline_timeout_s"},
        "jobs": rows,
    }
    def summarise(rs: list[dict[str, Any]]) -> dict[str, Any]:
        bt = [sum(r["tokens"][i] for r in rs) for i in (0, 1)]
        blat = [r["ms"] for r in rs]
        return {
            "all_languages_verified": round(sum(r["all_ok"] for r in rs) / n, 3),
            "moments_all_languages": f"{sum(r['all_ok'] for r in rs)}/{len(rs)}",
            "language_outputs_verified": round(sum(len(r["ok_langs"]) for r in rs) / (n * len(langs)), 3),
            "per_language_verified": {lang: round(sum(lang in r["ok_langs"] for r in rs) / n, 3) for lang in langs},
            "mean_attempts": round(sum(r["attempts"] for r in rs) / n, 2),
            "latency_ms": {"p50": percentile(blat, 0.5), "p95": percentile(blat, 0.95)},
            "tokens_in": bt[0], "tokens_out": bt[1], "cost_usd_per_moment": round(_cost(*bt) / n, 5),
            "errors": sum(1 for r in rs if r["error"]),
        }
    if base_rows:
        report["single_agent_baseline"] = {**summarise(base_rows), "setup": "one call, every language, no checker loop, "
                                           "90 s timeout", "jobs": base_rows}
        report["single_agent_with_checker"] = {**summarise(loop_rows), "setup":
                                               f"one agent, same Verifier feedback, up to {cfg.max_attempts} drafts, "
                                               "rewrites only failing languages, 90 s timeout per call", "jobs": loop_rows}
    else:
        report["single_agent_baseline"] = {"skipped": "offline model" if cfg.is_offline else "disabled"}
    return report
