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
