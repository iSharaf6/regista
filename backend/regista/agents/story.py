"""The story lane: a Microsoft Agent Framework workflow.

              /-> Narrator (en) ------\\
    Analyst --                           --> Verifier --ok------------------------> Producer
              \\-> Localizer (es fr ar pt)/       |  \\--rejected: exact issues--> Rewriter --> Verifier
                                                  \\--attempts exhausted--> Fallback -> Producer

Every edge carries one StoryJob - the shared state of the hand-off. Each
agent is a distinct `agent_framework.Agent` with its own instructions; the
Verifier is deterministic on purpose. Model failures, timeouts, a tripped
circuit breaker or injected chaos all degrade to grounded templates, so the
broadcast never goes dark.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from agent_framework import (
    Agent,
    Case,
    Default,
    Executor,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)

from . import prompts
from .clients import OfflineChatClient, make_chat_client, parse_json
from .config import LLMConfig
from .insight import deterministic_insight
from .telemetry import CircuitBreaker, Span, Telemetry
from .templates import PERSONAS, Names, narrate
from .templates import _ctx as template_context
from .verifier import _supported, allowed_numbers, verify_texts


class AgentFailure(Exception):
    pass


@dataclass
class StoryJob:
    moment: dict[str, Any]
    context: dict[str, Any]
    languages: list[str]
    names: dict[str, dict[str, str]]
    roster_names: dict[str, str]
    home: str
    away: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    insight: dict[str, Any] | None = None
    narration: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)
    verdict: dict[str, Any] | None = None
    failed: list[str] = field(default_factory=list)
    redo: list[str] = field(default_factory=list)
    feedback: dict[str, list[str]] = field(default_factory=dict)
    attempts: int = 0
    fallback_langs: list[str] = field(default_factory=list)
    retry_langs: list[str] = field(default_factory=list)  # writers that failed (timeout, bad JSON) and get a second draft
    models: dict[str, str] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    started: float = field(default_factory=time.perf_counter)
    shirts: dict[str, int] = field(default_factory=dict)

    def shirt_numbers(self) -> dict[str, int]:
        """Shirt numbers of this moment's players: commentators in many markets say "el 9" rather than a name."""
        out = {}
        for pid in self.moment.get("players", []):
            num = self.shirts.get(pid)
            if num is None:
                m = re.search(r"(\d+)$", pid)
                num = int(m.group(1)) if m else None
            if num is not None:
                out[self.names["players"].get(pid, pid)] = num
        return out

    def evidence(self) -> list[Any]:
        """What the Verifier checks copy against: deterministic match data only. Model output (including the
        Analyst's key numbers) is never evidence, so a model cannot vouch for its own figures."""
        return [self.moment.get("facts", {}), self.context, list(self.shirt_numbers().values()),
                {"clock": self.moment.get("clock", "")}]

    @property
    def verdict_ok(self) -> bool:
        return bool(self.verdict and self.verdict["ok"])

    @property
    def names_obj(self) -> Names:
        return Names(self.names["players"], self.names["teams"])

    def grounding(self, lang: str) -> dict[str, Any]:
        """The exact, pre-formatted figures and names a writer may use (what the Verifier will accept)."""
        ctx = template_context(self.moment, self.names_obj, lang, self.home, self.away)
        figures = {k: v for k, v in ctx.items() if isinstance(v, (int, float)) or (isinstance(v, str) and any(c.isdigit() for c in v))}
        figures["clock"] = self.moment.get("clock", "")
        figures["shirt_numbers"] = self.shirt_numbers()
        players = [self.names["players"].get(p, "") for p in self.moment.get("players", [])]
        return {"FIGURES": figures, "ALLOWED_PLAYERS": [p for p in players if p],
                "TEAMS": [self.names["teams"].get(self.home, ""), self.names["teams"].get(self.away, "")]}

    def payload(self, task: str, **extra: Any) -> str:
        body = {"task": task, "moment": self.moment, "context": self.context, "names": self.names,
                "home": self.home, "away": self.away,
                "UNITS": metric_units(self.moment.get("facts", {}), self.context), **extra}
        if task in {"narrate", "localize"}:
            body.update(self.grounding(extra.get("language", "en")))
        return json.dumps(body, ensure_ascii=False, default=str)


# What each metric measures, sent with every task: the Verifier binds a figure to its unit, and a writer can only keep
# the unit right if it knows it (a pressing rate is per 100 opponent passes; calling it "per minute" is rejected).
METRIC_UNITS = {
    "press_rate": "pressing actions in the opponent's half per 100 opponent passes from their own 60% of the pitch "
                  "(a share of opportunities, not per minute)",
    "ppda": "opponent passes allowed per defensive action",
    "players_near_ball": "average number of the team's players within 8 m of the ball",
    "line_height": "defensive line height in metres from the team's own goal",
    "closing_distance": "average distance in metres from the nearest presser to the ball",
    "high_regains": "ball recoveries in the opponent's half",
    "players_remaining": "players the team has left on the pitch after this dismissal",
    "players_on_pitch": "players each team has on the pitch now",
    "scorer_goals": "the scorer's goals in this match so far, including this one",
    "xg": "chance quality from 0 to 1: the probability a shot like it scores",
    "wp": "win probability as home / draw / away",
    "difficulty": "pass difficulty from 0 to 100",
}


def metric_units(*sources: dict[str, Any]) -> dict[str, str]:
    keys = [str(k) for src in sources for k in (src or {})]
    return {m: what for m, what in METRIC_UNITS.items() if any(m in k for k in keys)}


class AgentRuntime:
    """Owns the model client, the agents and the reliability machinery."""

    def __init__(self, cfg: LLMConfig, telemetry: Telemetry | None = None, client: Any = None, model_name: str | None = None):
        self.cfg = cfg
        self.telemetry = telemetry or Telemetry()
        self.breaker = CircuitBreaker(cfg.breaker_threshold, cfg.breaker_cooldown_s)
        self.client = client or make_chat_client(cfg)
        self.offline = OfflineChatClient()
        self.model_name = model_name or ("regista-offline" if cfg.is_offline else f"{cfg.provider}:{cfg.model}")
        writer_opts: Any = {"temperature": 0.4, "max_tokens": 700}
        self.analyst = Agent(self.client, prompts.ANALYST, name="Analyst", description="Explains why a moment matters",
                             default_options={"temperature": 0.2, "max_tokens": 500})
        self.narrator = Agent(self.client, prompts.NARRATOR, name="Narrator", description="Writes on-screen copy per audience",
                              default_options=writer_opts)
        self.localizer = Agent(self.client, prompts.LOCALIZER, name="Localizer",
                               description="Writes native copy for other markets", default_options=writer_opts)
        self.recapper = Agent(self.client, prompts.RECAP, name="Recap", description="Writes the automated match report")

    async def call(self, agent: Agent, name: str, payload: str, job: StoryJob | None = None, attempt: int = 1) -> Any:
        """Run one agent with breaker, chaos injection, timeout and JSON parsing. Raises AgentFailure."""
        t0 = time.perf_counter()
        moment_id = job.moment.get("id") if job else None
        t_match = job.moment.get("t", 0.0) if job else 0.0
        if not self.breaker.allow():
            self.telemetry.record(Span(name, "skipped", 0.0, self.model_name, job.id if job else "", moment_id, attempt,
                                       "circuit open", t_match))
            raise AgentFailure("circuit open")
        try:
            if self.telemetry.chaos_fail_rate and random.random() < self.telemetry.chaos_fail_rate:
                await asyncio.sleep(min(2.0, self.telemetry.chaos_latency_ms / 1000 or 0.3))
                raise AgentFailure("injected outage (chaos)")
            if self.telemetry.chaos_latency_ms:
                await asyncio.sleep(self.telemetry.chaos_latency_ms / 1000)
            res = await asyncio.wait_for(agent.run(payload), timeout=self.cfg.timeout_s)
            self.count_tokens(name, res)  # billable whether or not the reply parses
            data = parse_json(res.text)
        except TimeoutError as exc:
            self.breaker.failure()
            self.telemetry.record(Span(name, "timeout", (time.perf_counter() - t0) * 1000, self.model_name,
                                       job.id if job else "", moment_id, attempt, f">{self.cfg.timeout_s}s", t_match))
            raise AgentFailure("timeout") from exc
        except Exception as exc:  # noqa: BLE001 - any model/parse failure degrades gracefully
            self.breaker.failure()
            self.telemetry.record(Span(name, "error", (time.perf_counter() - t0) * 1000, self.model_name,
                                       job.id if job else "", moment_id, attempt, str(exc)[:160], t_match))
            raise AgentFailure(str(exc)) from exc
        self.breaker.success()
        span = self.telemetry.record(Span(name, "ok", (time.perf_counter() - t0) * 1000, self.model_name,
                                          job.id if job else "", moment_id, attempt, "", t_match))
        if job is not None:
            job.trace.append(span.as_dict())
            job.models[name] = self.model_name
        return data

    def count_tokens(self, name: str, res: Any) -> tuple[int, int]:
        usage = getattr(res, "usage_details", None) or {}
        tin, tout = int(usage.get("input_token_count") or 0), int(usage.get("output_token_count") or 0)
        self.telemetry.tokens[name][0] += tin
        self.telemetry.tokens[name][1] += tout
        return tin, tout

    def note(self, job: StoryJob, agent: str, status: str, detail: str = "", ms: float = 0.0) -> None:
        span = self.telemetry.record(Span(agent, status, ms, "deterministic", job.id, job.moment.get("id"),
                                          job.attempts or 1, detail, job.moment.get("t", 0.0)))
        job.trace.append(span.as_dict())


# ---------------------------------------------------------------------- executors
LLM_ANALYST_KINDS = {"goal", "red_card", "press_shift", "big_chance"}  # where a model's "why" earns its latency


class AnalystExecutor(Executor):
    def __init__(self, rt: AgentRuntime):
        super().__init__(id="analyst")
        self.rt = rt

    @handler
    async def run(self, job: StoryJob, ctx: WorkflowContext[StoryJob]) -> None:
        if job.moment.get("kind") not in LLM_ANALYST_KINDS and not self.rt.cfg.is_offline:
            # routing: routine moments are fully explained by their factor breakdown, so skip a model round trip
            job.insight = deterministic_insight(job.moment, job.names_obj)
            job.models["Analyst"] = "deterministic"
            self.rt.note(job, "Analyst", "ok", "routine moment: factor-based insight, no model call")
        else:
            try:
                data = await self.rt.call(self.rt.analyst, "Analyst", job.payload("analyze"), job)
                if not isinstance(data, dict) or "claim" not in data:
                    raise AgentFailure("analyst returned no claim")
                job.insight = _checked_insight(job, data)
            except AgentFailure as exc:
                t0 = time.perf_counter()
                job.insight = deterministic_insight(job.moment, job.names_obj)
                job.models["Analyst"] = "deterministic"
                self.rt.note(job, "Analyst", "fallback", str(exc)[:120], (time.perf_counter() - t0) * 1000)
        job.redo = list(job.languages)
        await ctx.send_message(job)


def _checked_insight(job: StoryJob, data: dict[str, Any]) -> dict[str, Any]:
    """The Analyst is fact-checked too, before any writer sees its insight: key numbers that match data cannot back are
    dropped, and an insight whose text cites unbacked figures or players is replaced by the factor-based one."""
    ev = job.evidence()
    allowed = allowed_numbers(*ev)
    kn = data.get("key_numbers") if isinstance(data.get("key_numbers"), dict) else {}
    data["key_numbers"] = {k: v for k, v in kn.items()
                           if isinstance(v, (int, float)) and not isinstance(v, bool) and _supported(abs(float(v)), allowed)}
    fields = {f: (x if isinstance(x, str) else " ".join(map(str, x)) if isinstance(x, list) else "")
              for f, x in ((f, data.get(f)) for f in ("claim", "why", "tactical_read"))}
    verdict = verify_texts({"en": {"insight": fields}}, ev, set(job.moment.get("players", [])), job.roster_names,
                           claims=job.moment.get("facts", {}))
    if not verdict.ok:
        raise AgentFailure(f"insight failed the fact check: {verdict.issues[0].split('] ', 1)[-1][:100]}")
    return data


async def _write(rt: AgentRuntime, job: StoryJob, lang: str) -> None:
    """One language, one agent: the Narrator owns English, the Localizer writes every other market natively."""
    agent, name, task = (rt.narrator, "Narrator", "narrate") if lang == "en" else (rt.localizer, "Localizer", "localize")
    payload = job.payload(task, language=lang, insight=job.insight, feedback=job.feedback.get(lang))
    try:
        job.narration[lang] = _shape(await rt.call(agent, name, payload, job, job.attempts + 1))
        if lang in job.fallback_langs:  # a second draft after a failed first one: model-written after all
            job.fallback_langs.remove(lang)
    except AgentFailure as exc:
        job.narration[lang] = _template(job, lang)  # on air meanwhile, so nothing waits on the retry
        if lang not in job.fallback_langs:
            job.fallback_langs.append(lang)
        retry = job.attempts + 1 < rt.cfg.max_attempts  # a slow or malformed reply gets the same second draft as a rejection
        if retry and lang not in job.retry_langs:
            job.retry_langs.append(lang)
        rt.note(job, name, "retry" if retry else "fallback", f"{lang}: {str(exc)[:100]}")


class NarratorExecutor(Executor):
    def __init__(self, rt: AgentRuntime):
        super().__init__(id="narrator")
        self.rt = rt

    @handler
    async def run(self, job: StoryJob, ctx: WorkflowContext[StoryJob]) -> None:
        await _write(self.rt, job, "en")
        await ctx.send_message(job)


class LocalizerExecutor(Executor):
    def __init__(self, rt: AgentRuntime):
        super().__init__(id="localizer")
        self.rt = rt

    @handler
    async def run(self, job: StoryJob, ctx: WorkflowContext[StoryJob]) -> None:
        await asyncio.gather(*(_write(self.rt, job, lang) for lang in job.languages if lang != "en"))
        await ctx.send_message(job)


class RewriterExecutor(Executor):
    """Second drafts: every language the Verifier rejected is rewritten in parallel, with its exact issues."""

    def __init__(self, rt: AgentRuntime):
        super().__init__(id="rewriter")
        self.rt = rt

    @handler
    async def run(self, job: StoryJob, ctx: WorkflowContext[StoryJob]) -> None:
        await asyncio.gather(*(_write(self.rt, job, lang) for lang in job.failed))
        await ctx.send_message(job)


def _merge(jobs: list[StoryJob]) -> StoryJob:
    """Fan-in: fold the Narrator's and the Localizer's work into one job (a no-op if they shared the object)."""
    base = jobs[0]
    for other in jobs[1:]:
        if other is base:
            continue
        base.narration.update({k: v for k, v in other.narration.items() if k not in base.narration or k != "en"})
        seen = {t["id"] for t in base.trace}
        base.trace += [t for t in other.trace if t["id"] not in seen]
        base.models.update(other.models)
        base.fallback_langs = sorted(set(base.fallback_langs) | set(other.fallback_langs))
        base.retry_langs = sorted(set(base.retry_langs) | set(other.retry_langs))
    return base


class VerifierExecutor(Executor):
    def __init__(self, rt: AgentRuntime):
        super().__init__(id="verifier")
        self.rt = rt

    @handler
    async def from_writers(self, jobs: list[StoryJob], ctx: WorkflowContext[StoryJob]) -> None:
        await self.run(_merge(jobs), ctx)

    @handler
    async def run(self, job: StoryJob, ctx: WorkflowContext[StoryJob]) -> None:
        t0 = time.perf_counter()
        job.attempts += 1
        check = {lang: job.narration[lang] for lang in job.languages if lang in job.narration}
        allowed_players = set(job.moment.get("players", []))
        verdict = verify_texts(check, job.evidence(), allowed_players, job.roster_names, claims=job.moment.get("facts", {}))
        job.verdict = verdict.as_dict()
        retry, job.retry_langs = [lang for lang in job.retry_langs if lang not in verdict.failed_langs], []
        job.failed = sorted(set(verdict.failed_langs) | set(retry))
        job.redo = list(job.failed)
        job.feedback = {}
        for issue in verdict.issues:
            lang = issue[1:3]
            job.feedback.setdefault(lang, []).append(issue)
        ms = (time.perf_counter() - t0) * 1000
        status = "rejected" if not verdict.ok else "retry" if retry else "ok"
        detail = f"{verdict.numbers_supported}/{verdict.numbers_checked} figures grounded"
        if not verdict.ok:
            detail += f"; {len(verdict.issues)} issue(s) in {','.join(verdict.failed_langs)}: {verdict.issues[0][:90]}"
        if retry:
            detail += f"; second draft for {','.join(retry)} after a failed writer call"
        self.rt.note(job, "Verifier", status, detail, ms)
        await ctx.send_message(job)


class FallbackExecutor(Executor):
    def __init__(self, rt: AgentRuntime):
        super().__init__(id="fallback")
        self.rt = rt

    @handler
    async def run(self, job: StoryJob, ctx: WorkflowContext[StoryJob]) -> None:
        for lang in job.failed:
            job.narration[lang] = _template(job, lang)
            job.fallback_langs.append(lang)
        self.rt.note(job, "Fallback", "fallback", f"templates for {','.join(job.failed)} after {job.attempts} attempt(s)")
        check = {lang: job.narration[lang] for lang in job.languages}
        verdict = verify_texts(check, job.evidence(), set(job.moment.get("players", [])), job.roster_names,
                               claims=job.moment.get("facts", {}))
        job.verdict = {**verdict.as_dict(), "via": "fallback"}  # the templates' own verdict, never overridden
        await ctx.send_message(job)


class ProducerExecutor(Executor):
    def __init__(self, rt: AgentRuntime):
        super().__init__(id="producer")
        self.rt = rt

    @handler
    async def run(self, job: StoryJob, ctx: WorkflowContext[StoryJob, StoryJob]) -> None:
        self.rt.note(job, "Producer", "ok", f"cue ready in {1000 * (time.perf_counter() - job.started):.0f} ms")
        await ctx.yield_output(job)


def _shape(data: Any) -> dict[str, dict[str, str]]:
    if not isinstance(data, dict):
        raise AgentFailure("narration is not an object")
    out = {}
    for p in PERSONAS:
        block = data.get(p)
        if not isinstance(block, dict) or not all(isinstance(block.get(k), str) for k in ("caption", "line", "explainer")):
            raise AgentFailure(f"narration missing {p}")
        out[p] = {k: block[k].strip() for k in ("caption", "line", "explainer")}
    return out


def _template(job: StoryJob, lang: str) -> dict[str, dict[str, str]]:
    return {p: narrate(job.moment, job.names_obj, lang, p, job.home, job.away) for p in PERSONAS}


def build_story_workflow(rt: AgentRuntime) -> Workflow:
    analyst, narrator, localizer = AnalystExecutor(rt), NarratorExecutor(rt), LocalizerExecutor(rt)
    rewriter, verifier = RewriterExecutor(rt), VerifierExecutor(rt)
    fallback, producer = FallbackExecutor(rt), ProducerExecutor(rt)
    max_attempts = rt.cfg.max_attempts
    return (
        WorkflowBuilder(start_executor=analyst, max_iterations=40, name="regista-story",
                        description="Analyst -> (Narrator || Localizer) -> Verifier -> Rewriter loop -> Producer")
        .add_fan_out_edges(analyst, [narrator, localizer])
        .add_fan_in_edges([narrator, localizer], verifier)
        .add_switch_case_edge_group(verifier, [
            Case(lambda j: j.verdict_ok and not j.failed, producer),  # nothing waiting for a second draft
            Case(lambda j: bool(j.failed) and j.attempts < max_attempts, rewriter),
            Default(fallback),
        ])
        .add_edge(rewriter, verifier)
        .add_edge(fallback, producer)
        .build()
    )


async def run_story(rt: AgentRuntime, job: StoryJob) -> StoryJob:
    wf = build_story_workflow(rt)
    result = await wf.run(job)
    outs = result.get_outputs()
    return outs[0] if outs else job
