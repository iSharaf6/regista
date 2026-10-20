"""Recaps: every field the screen shows is checked, a goal inside the same minute refreshes the report, and a report
written for a timeline that moved on is never handed back as current."""

from __future__ import annotations

import asyncio
import dataclasses

from regista.agents.templates import LANGS, PERSONAS
from regista.runtime.session import DEMO, MatchSession
from regista.schema.events import EventType


def _first_goal_t(s: MatchSession) -> float:
    return min(e.t for e in s.res.events if e.type == EventType.GOAL)


def _model(s: MatchSession, reply, slow: float = 0.0) -> list[int]:
    """Make the session behave as if a model wrote its recaps: `reply(payload)` is the model's JSON."""
    s.cfg = dataclasses.replace(s.cfg, provider="test")
    s.rt.model_name = "test-model"
    calls = [0]

    async def call(agent, name, payload, **_):
        calls[0] += 1
        if slow and calls[0] == 1:
            await asyncio.sleep(slow)
        import json
        return reply(json.loads(payload))
    s.rt.call = call  # type: ignore[method-assign]
    return calls


def _payload(s: MatchSession):
    from regista.agents.recap import recap_payload
    return recap_payload(s.state, s.moments, s.names_dict, "en", "analyst", "full_time")


def test_deterministic_recaps_verify_in_every_language_persona_and_period():
    async def run():
        for seed in (DEMO["seed"], 101):  # 101: Northbridge lose two players to red cards
            s = MatchSession(story_workers=0)
            s.load(DEMO["home"], DEMO["away"], seed, DEMO["scenario"])
            s.advance(50 * 60, live=False)  # through half time
            for lang in LANGS:
                for persona in PERSONAS:
                    out = await s.recap(lang, persona, "half_time")
                    assert out["verdict"]["ok"], (seed, lang, persona, out["verdict"]["issues"])
            s.advance(float(s.res.frame_t[-1]), live=False)  # to the final whistle
            for lang in LANGS:
                for persona in PERSONAS:
                    out = await s.recap(lang, persona, "full_time")
                    assert out["verdict"]["ok"], (seed, lang, persona, out["verdict"]["issues"])
    asyncio.run(run())


def test_unsupported_facts_in_any_visible_field_cost_the_verified_badge():
    """Headline and summary are fine; the player-of-the-match reason, the rating, the closing line, a turning point's
    minute and its evidence are not. The model report is rejected and the grounded one airs instead."""
    async def run():
        s = MatchSession(story_workers=0)
        s.advance(float(s.res.frame_t[-1]), live=False)
        pid = next(iter(s.roster_names))

        def poisoned(p):
            return {"headline": "A hard-fought match", "summary": "Both sides had their moments.", "tactical_story": "",
                    "turning_points": [{"clock": "999'", "text": "The decisive goal.", "evidence": ["e99999"]}],
                    "player_of_the_match": {"player_id": pid, "name": "Someone Else", "reason": "999 goals", "rating": 999},
                    "closing_line": "A night of 999 goals."}
        _model(s, poisoned)
        out = await s.recap("en", "analyst", "full_time")
        assert out["source"].startswith("deterministic (verifier rejected"), out["source"]
        assert out["verdict"]["ok"]
        potm = out["recap"]["player_of_the_match"]
        assert potm.get("rating") != 999 and potm["name"] == s.roster_names.get(potm["player_id"], potm["name"])

        # each problem alone is enough
        clean = {"headline": "A hard-fought match", "summary": "Both sides had their moments.", "tactical_story": "",
                 "turning_points": [], "player_of_the_match": {"player_id": pid, "reason": ""}, "closing_line": ""}
        payload = {**_payload(s), "language": "en", "persona": "analyst"}
        assert s._check_recap(clean, payload, "en", "analyst")[1].ok
        for change in ({"closing_line": "A night of 999 goals."},
                       {"player_of_the_match": {"player_id": pid, "reason": "999 goals"}},
                       {"turning_points": [{"clock": "999'", "text": "A goal.", "evidence": []}]},
                       {"turning_points": [{"clock": s.moments[0].clock, "text": "A moment.", "evidence": ["e99999"]}]},
                       {"player_of_the_match": {"player_id": "XXX-99", "name": "Nobody", "reason": ""}}):
            _, verdict = s._check_recap({**clean, **change}, payload, "en", "analyst")
            assert not verdict.ok, change
    asyncio.run(run())


def test_a_goal_inside_the_same_minute_refreshes_the_live_recap():
    async def run():
        s = MatchSession(story_workers=0)
        t_goal = _first_goal_t(s)
        s.advance(t_goal - 2 - s.clock_t, live=False)
        before = await s.recap("en", "casual")
        s.advance(4, live=False)
        after = await s.recap("en", "casual")
        assert before["period"] == after["period"] == "live"
        assert sum(before["as_of"]["score"].values()) == 0 and sum(after["as_of"]["score"].values()) == 1
        assert after["recap"]["headline"] != before["recap"]["headline"]
    asyncio.run(run())


def test_a_report_written_for_an_old_timeline_is_rewritten_not_returned():
    async def run():
        s = MatchSession(story_workers=0)
        s.advance(float(s.res.frame_t[-1]), live=False)
        calls = _model(s, lambda p: {"headline": f"Report at {p['clock']}", "summary": "", "tactical_story": "",
                                     "turning_points": [], "player_of_the_match": {}, "closing_line": ""}, slow=0.2)
        task = asyncio.create_task(s.recap("en", "casual", "full_time"))
        await asyncio.sleep(0.05)
        s.load("ASH", "KES", 3, "press")  # a new match while the model is still writing
        out = await task
        assert calls[0] == 2 and out["match_id"] == s.res.info.match_id and not out.get("superseded")
        assert out["period"] == "live"  # the new match has not reached full time: no old full-time report
    asyncio.run(run())
