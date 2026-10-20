"""The self-correcting loop, exercised with a model that behaves like a real LLM gone wrong.

FlakyWriter drafts plausible copy but slips in an invented figure and an uninvolved player, the two most common
ways generated sports copy fails a fact check. It only gets it right once the Verifier's feedback reaches it.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from agent_framework import BaseChatClient, ChatResponse, Content, Message

from regista.agents.clients import OfflineChatClient, parse_json
from regista.agents.config import LLMConfig
from regista.agents.story import AgentRuntime, StoryJob, run_story
from regista.evaluation import replay
from regista.sim.engine import simulate


class FlakyWriter(BaseChatClient):
    OTEL_PROVIDER_NAME = "regista.test"

    def __init__(self, stubborn: bool = False, **kw: Any) -> None:
        super().__init__(**kw)
        self.stubborn = stubborn
        self.feedback_seen: list[list[str]] = []

    async def _respond(self, messages: list[Message]) -> ChatResponse:
        payload = parse_json(next(m.text for m in reversed(messages) if m.role == "user"))
        out = OfflineChatClient.run_task(payload)
        if payload.get("task") in {"narrate", "localize"}:
            fb = payload.get("feedback")
            if fb:
                self.feedback_seen.append(fb)
            if self.stubborn or not fb:
                allowed = set(payload.get("ALLOWED_PLAYERS", []))
                outsider = next(n for n in payload["names"]["players"].values() if n not in allowed and len(n) > 4)
                out["analyst"]["line"] = f"{out['analyst']['line'][:120]} A 47 m run from {outsider}."
        return ChatResponse(messages=[Message("assistant", [Content.from_text(json.dumps(out, ensure_ascii=False))])],
                            model="flaky-writer")

    def _inner_get_response(self, *, messages: Any, stream: bool, options: Any, **kwargs: Any) -> Any:
        return self._respond(list(messages))


@pytest.fixture(scope="module")
def goal_job_parts():
    res = simulate("NOR", "CAL", 16, "derby")
    st, _, moments = replay(res)
    goal = next(m for m in moments if m.kind == "goal")
    names = {"players": {pid: p.info.short_name for pid, p in st.players.items()}, "teams": dict(st.short)}
    return goal, names, st


def _job(parts, langs):
    goal, names, st = parts
    return StoryJob(goal.as_dict(), {"score": dict(st.score)}, langs, names, names["players"], st.home, st.away)


def test_verifier_feedback_makes_the_writer_fix_its_draft(goal_job_parts):
    writer = FlakyWriter()
    rt = AgentRuntime(LLMConfig(provider="test", model="flaky"), client=writer, model_name="flaky-writer")
    job = asyncio.run(run_story(rt, _job(goal_job_parts, ["en", "es"])))
    verifier_steps = [s["status"] for s in job.trace if s["agent"] == "Verifier"]
    assert verifier_steps == ["rejected", "ok"]
    assert job.attempts == 2 and not job.fallback_langs
    assert job.verdict["ok"] and "47" not in job.narration["en"]["analyst"]["line"]
    issues = " ".join(i for fb in writer.feedback_seen for i in fb)
    assert "47" in issues and "not part of this moment" in issues


def test_a_writer_that_never_listens_ends_in_grounded_fallback(goal_job_parts):
    rt = AgentRuntime(LLMConfig(provider="test", model="flaky"), client=FlakyWriter(stubborn=True), model_name="flaky-writer")
    job = asyncio.run(run_story(rt, _job(goal_job_parts, ["en"])))
    assert job.verdict["ok"] and job.verdict.get("via") == "fallback"
    assert "en" in job.fallback_langs
    assert "47" not in job.narration["en"]["analyst"]["line"]
    assert any(s["agent"] == "Fallback" for s in job.trace)


def test_verifier_accepts_the_moments_own_minute_and_shirt_numbers(goal_job_parts):
    from regista.agents.story import VerifierExecutor  # noqa: F401  (import keeps the contract visible)
    from regista.agents.verifier import verify_texts

    goal, names, st = goal_job_parts
    job = _job(goal_job_parts, ["ar"])
    minute = goal.clock.rstrip("'")
    shirt = next(iter(job.shirt_numbers().values()))
    texts = {"ar": {"casual": {"caption": "هدف", "line": f"في الدقيقة {minute} سجل رقم {shirt}", "explainer": ""}}}
    facts = [goal.facts, {}, {}, list(job.shirt_numbers().values()), goal.clock]
    assert verify_texts(texts, facts, set(goal.players), names["players"]).ok
    wrong = {"ar": {"casual": {"caption": "هدف", "line": "في الدقيقة 63 سجل رقم 47", "explainer": ""}}}
    assert not verify_texts(wrong, facts, set(goal.players), names["players"]).ok


class PoisonedAnalyst(FlakyWriter):
    """The Analyst invents a figure, and the writer repeats it until the Verifier objects."""

    async def _respond(self, messages: list[Message]) -> ChatResponse:
        payload = parse_json(next(m.text for m in reversed(messages) if m.role == "user"))
        out = OfflineChatClient.run_task(payload)
        if payload.get("task") == "analyze":
            out.setdefault("key_numbers", {})["scorer_goals"] = 97
            out["claim"] = f"{out.get('claim', '')} His 97th goal for the club."
        elif payload.get("task") in {"narrate", "localize"} and not payload.get("feedback"):
            scorer = payload["names"]["players"][payload["moment"]["players"][0]]
            out["analyst"]["line"] = f"{out['analyst']['line'][:120]} {scorer} has scored 97 goals."
        return ChatResponse(messages=[Message("assistant", [Content.from_text(json.dumps(out, ensure_ascii=False))])],
                            model="poisoned-analyst")


def test_a_model_cannot_vouch_for_its_own_numbers(goal_job_parts):
    rt = AgentRuntime(LLMConfig(provider="test", model="poisoned"), client=PoisonedAnalyst(), model_name="poisoned")
    job = asyncio.run(run_story(rt, _job(goal_job_parts, ["en"])))
    # the Analyst is checked before the writers see it: its invented figure never becomes part of the insight
    analyst = [s for s in job.trace if s["agent"] == "Analyst"]
    assert analyst[-1]["status"] == "fallback" and "fact check" in analyst[-1]["detail"]
    assert "97" not in json.dumps(job.insight, ensure_ascii=False)
    # and a writer that repeats the figure anyway is caught and corrected
    assert [s["status"] for s in job.trace if s["agent"] == "Verifier"][0] == "rejected"
    assert job.verdict["ok"] and "97" not in json.dumps(job.narration, ensure_ascii=False)


def _check(lang: str, line: str, parts) -> bool:
    from regista.agents.verifier import verify_texts

    goal, names, _ = parts
    job = _job(parts, [lang])
    texts = {lang: {"analyst": {"caption": "", "line": line, "explainer": ""}}}
    return verify_texts(texts, job.evidence(), set(goal.players), names["players"], claims=goal.facts).ok


def test_figures_must_match_the_kind_of_fact_they_describe(goal_job_parts):
    # the seed-16 opener: 20', a 56.2 km/h header from 13 m, win chance 75%, the scorer's first goal
    good = {
        "en": "A 56 km/h header from 13 m in the 20th minute, his 1st goal; win chance now 75%.",
        "es": "Cabezazo a 56 km/h desde 13 metros en el minuto 20; 75 por ciento de opciones.",
        "fr": "Une tête à 56 km/h à 13 mètres, à la 20e minute.",
        "ar": "رأسية بسرعة 56 كم/س من 13 متر في الدقيقة 20",
        "pt": "Cabeçada a 56 km/h de 13 metros aos 20'.",
    }
    for lang, line in good.items():
        assert _check(lang, line, goal_job_parts), (lang, line)
    bad = {
        "en": ["He now has 33 goals this season.",          # 33 is a speed constant, not a goal count
               "A 13 km/h dink over the keeper.",            # 13 is the distance, not a speed
               "Struck in the 63rd minute.",                 # ordinals are checked
               "That makes ninety-seven goals for him."],    # and written-out numbers
        "es": ["Ya suma noventa y siete goles."],
        "fr": ["Il marque son septième but, sept buts en tout."],
        "ar": ["هذا هدفه رقم 1 بعد 33 هدفاً"],
        "pt": ["Já são 33 gols na temporada."],
    }
    for lang, lines in bad.items():
        for line in lines:
            assert not _check(lang, line, goal_job_parts), (lang, line)
    # a shirt number next to a goal word is not a goal count
    assert _check("en", "The No. 9 goal machine strikes again.", goal_job_parts)
    assert _check("ar", "رقم 9 هدف رائع", goal_job_parts)


def test_fallback_is_never_marked_verified_when_its_copy_fails(goal_job_parts, monkeypatch):
    import regista.agents.story as story

    def broken_template(job, lang):
        return {p: {"caption": "GOAL", "line": "A 63rd-minute strike, his 33rd goal.", "explainer": ""}
                for p in story.PERSONAS}

    monkeypatch.setattr(story, "_template", broken_template)
    rt = AgentRuntime(LLMConfig(provider="test", model="flaky"), client=FlakyWriter(stubborn=True), model_name="flaky-writer")
    job = asyncio.run(run_story(rt, _job(goal_job_parts, ["en"])))
    assert job.verdict["via"] == "fallback" and not job.verdict["ok"]


class SlowFirstNarrator(BaseChatClient):
    """The English Narrator's first call is slower than the timeout (a model latency spike); the second is normal."""
    OTEL_PROVIDER_NAME = "regista.test"

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.narrate_calls = 0

    async def _respond(self, messages: list[Message]) -> ChatResponse:
        payload = parse_json(next(m.text for m in reversed(messages) if m.role == "user"))
        if payload.get("task") == "narrate":
            self.narrate_calls += 1
            if self.narrate_calls == 1:
                await asyncio.sleep(1.0)
        out = OfflineChatClient.run_task(payload)
        return ChatResponse(messages=[Message("assistant", [Content.from_text(json.dumps(out, ensure_ascii=False))])],
                            model="slow-first")

    def _inner_get_response(self, *, messages: Any, stream: bool, options: Any, **kwargs: Any) -> Any:
        return self._respond(list(messages))


def test_a_timed_out_writer_gets_its_second_draft_instead_of_a_template(goal_job_parts):
    client = SlowFirstNarrator()
    rt = AgentRuntime(LLMConfig(provider="test", model="slow", timeout_s=0.3), client=client, model_name="slow-first")
    job = asyncio.run(run_story(rt, _job(goal_job_parts, ["en", "es"])))
    assert client.narrate_calls == 2 and job.attempts == 2
    assert not job.fallback_langs and job.verdict["ok"] and not job.verdict.get("via")
    statuses = [s["status"] for s in job.trace if s["agent"] == "Verifier"]
    assert statuses == ["retry", "ok"]  # the first pass is not counted as a clean first draft
