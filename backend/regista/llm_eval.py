"""Score the live agents on the demo match with whatever model is configured.

    REGISTA_LLM=foundry FOUNDRY_PROJECT_ENDPOINT=... FOUNDRY_MODEL=gpt-4.1-mini regista llm-eval

Reports first-draft verification rate (how often the model's copy passes the fact check untouched), final
verification after retries, template fallbacks, the most common rejection reasons, latency, whether the Pundit
actually calls its tools, and whether model-written recaps survive the Verifier.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from statistics import median
from typing import Any

from .agents.config import load_config
from .agents.pundit import Pundit
from .agents.recap import offline_recap, recap_payload
from .agents.story import AgentFailure, AgentRuntime, StoryJob, run_story
from .agents.tools import MatchTools
from .agents.verifier import verify_texts
from .evaluation import replay
from .sim.engine import simulate

QUESTIONS = [
    ("en", "analyst", "Why are Northbridge winning the ball so high since the hour?"),
    ("es", "casual", "¿Quién es el mejor jugador del partido?"),
    ("ar", "casual", "ما هي احتمالات فوز كل فريق؟"),
    ("fr", "new_fan", "Qui contrôle le match en ce moment, et pourquoi ?"),
]


def _reason(issue: str) -> str:
    for key, label in (("not supported", "unsupported figure"), ("not part of this moment", "unexpected player"),
                       ("too long", "too long"), ("brand-safety", "brand safety"), ("malformed", "malformed output")):
        if key in issue:
            return label
    return "other"


async def run(seed: int = 16, moments: int = 12, langs: tuple[str, ...] = ("en", "es", "ar"), concurrency: int = 3) -> dict[str, Any]:
    cfg = load_config()
    rt = AgentRuntime(cfg)
    res = simulate("NOR", "CAL", seed, "derby")
    st, det, all_moments = replay(res)
    names = {"players": {pid: p.info.short_name for pid, p in st.players.items()}, "teams": dict(st.short)}
    story = [m for m in all_moments if m.lane == "story" and m.kind not in {"half_time", "full_time"}][:moments]
    sem = asyncio.Semaphore(concurrency)
    reasons: Counter[str] = Counter()

    async def one(m: Any) -> dict[str, Any]:
        async with sem:
            t0 = time.perf_counter()
            job = StoryJob(m.as_dict(), {"score": dict(st.score), "clock": st.clock}, list(langs), names, names["players"],
                           st.home, st.away)
            job = await run_story(rt, job)
            verifier = [s for s in job.trace if s["agent"] == "Verifier"]
            for issue in (job.verdict or {}).get("issues", []):
                reasons[_reason(issue)] += 1
            return {"moment": m.kind, "clock": m.clock, "first_draft_ok": bool(verifier) and verifier[0]["status"] == "ok",
                    "attempts": job.attempts, "fallback_langs": job.fallback_langs,
                    "verified_without_fallback": bool(job.verdict and job.verdict.get("ok") and not job.verdict.get("via")),
                    "ms": round((time.perf_counter() - t0) * 1000), "sample_en": job.narration.get("en", {}).get("analyst", {})}

    t_all = time.perf_counter()
    rows = await asyncio.gather(*(one(m) for m in story))
    for sp in rt.telemetry.spans:
        if sp.agent == "Verifier" and sp.status == "rejected":
            reasons["rejected drafts"] += 1

    class Ctx:
        state, moments = st, det.moments

    pundit = Pundit(rt, MatchTools(Ctx()))
    answers = []
    for lang, persona, q in QUESTIONS:
        a = await pundit.ask(q, lang, persona)
        answers.append({"lang": lang, "question": q, "answer": a["answer"], "tools": a["tools"], "model": a["model"], "ms": a["ms"]})

    recaps = []
    for lang in ("en", "ar"):
        payload = recap_payload(st, det.moments, names, lang, "analyst", "full_time")
        t0 = time.perf_counter()
        source = rt.model_name
        try:
            if cfg.is_offline:
                raise AgentFailure("offline")
            data = await rt.call(rt.recapper, "Recap", json.dumps(payload, ensure_ascii=False, default=str))
        except AgentFailure:
            data, source = offline_recap(payload), "deterministic"
        fields = {"headline": data.get("headline", ""), "summary": data.get("summary", ""), "tactical": data.get("tactical_story", "")}
        fields.update({f"tp{i}": tp.get("text", "") for i, tp in enumerate(data.get("turning_points", []))})
        allowed = {p["id"] for p in payload["top_players"]} | {pid for m in payload["moments"] for pid in m["players"]}
        v = verify_texts({lang: {"analyst": fields}}, [payload["teams"], payload["score"], payload["top_players"],
                                                      [m["facts"] for m in payload["moments"]], payload["wp_path"]],
                         allowed, names["players"])
        recaps.append({"lang": lang, "source": source, "verified": v.ok, "issues": v.issues[:4], "headline": fields["headline"],
                       "ms": round((time.perf_counter() - t0) * 1000)})

    lat = sorted(r["ms"] for r in rows) or [0]
    n = max(1, len(rows))
    return {
        "model": rt.model_name,
        "moments": len(rows),
        "languages": list(langs),
        "first_draft_verified": round(sum(r["first_draft_ok"] for r in rows) / n, 2),
        "verified_without_fallback": round(sum(r["verified_without_fallback"] for r in rows) / n, 2),
        "jobs_with_fallback": sum(1 for r in rows if r["fallback_langs"]),
        "mean_attempts": round(sum(r["attempts"] for r in rows) / n, 2),
        "story_latency_ms": {"p50": median(lat), "p95": lat[int(0.95 * (len(lat) - 1))]},
        "wall_s": round(time.perf_counter() - t_all, 1),
        "rejection_reasons": dict(reasons),
        "agents": rt.telemetry.summary()["agents"],
        "pundit": answers,
        "pundit_used_tools": round(sum(1 for a in answers if a["tools"]) / len(answers), 2),
        "recaps": recaps,
        "jobs": rows,
    }
