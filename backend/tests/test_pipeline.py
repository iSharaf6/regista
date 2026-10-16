"""End-to-end and unit tests. Everything runs offline (REGISTA_LLM unset)."""

from __future__ import annotations

import asyncio

import pytest

from regista.agents.config import LLMConfig
from regista.agents.director import Director
from regista.agents.producer import Producer
from regista.agents.pundit import Pundit
from regista.agents.story import AgentRuntime, StoryJob, run_story
from regista.agents.templates import LANGS, PERSONAS, Names, narrate
from regista.agents.tools import MatchTools
from regista.agents.verifier import verify_texts
from regista.evaluation import replay
from regista.schema.cues import Provenance
from regista.schema.profiles import FanProfile, Mode
from regista.sim.engine import simulate
from regista.sim.realism import team_stats


@pytest.fixture(scope="module")
def match():
    res = simulate("NOR", "CAL", 16, "derby")
    st, det, moments = replay(res)
    return res, st, det, moments


def names_for(st):
    return Names({pid: p.info.short_name for pid, p in st.players.items()}, dict(st.short))


def test_simulation_is_deterministic():
    a = simulate("NOR", "CAL", 3, "derby")
    b = simulate("NOR", "CAL", 3, "derby")
    assert [e.model_dump() for e in a.events[:200]] == [e.model_dump() for e in b.events[:200]]
    assert a.summary["score"] == b.summary["score"]


def test_feed_contains_only_observable_facts(match):
    res, *_ = match
    for ev in res.events:
        assert "xg" not in ev.qualifiers and "difficulty" not in ev.qualifiers  # interpretation happens downstream


def test_match_statistics_are_football_shaped(match):
    res, *_ = match
    for stats in team_stats(res).values():
        assert 300 < stats["passes"] < 800
        assert 0.65 < stats["pass_accuracy"] < 0.92
        assert 3 <= stats["shots"] <= 30
        assert 8.5 < stats["outfield_distance_km"] < 13.5


def test_ground_truth_is_logged(match):
    res, *_ = match
    assert any(t["type"] == "tactical_shift" for t in res.truth)
    assert all("true_xg" in t for t in res.truth if t["type"] == "shot")


def test_moments_carry_evidence_and_factors(match):
    _, st, _, moments = match
    goals = [m for m in moments if m.kind == "goal"]
    assert len(goals) == sum(st.score.values())
    for g in goals:
        assert g.evidence and g.why
        assert 0 <= g.facts["wp_after"][0] <= 1


def test_templates_cover_every_moment_language_and_persona(match):
    _, st, _, moments = match
    names = names_for(st)
    for m in moments:
        for lang in LANGS:
            for persona in PERSONAS:
                out = narrate(m.as_dict(), names, lang, persona, st.home, st.away)
                assert out["caption"]


def test_verifier_rejects_invented_numbers_and_players(match):
    _, st, _, moments = match
    goal = next(m for m in moments if m.kind == "goal")
    roster = {pid: p.info.short_name for pid, p in st.players.items()}
    outsider = next(pid for pid in roster if pid not in goal.players)
    bad = {"en": {"casual": {"caption": "GOAL", "line": f"A 47 metre screamer, assisted by {roster[outsider]}!", "explainer": ""}}}
    verdict = verify_texts(bad, [goal.facts], set(goal.players), roster)
    assert not verdict.ok
    assert any("47" in i for i in verdict.issues)
    assert any(roster[outsider] in i for i in verdict.issues)


def test_verifier_blocks_brand_unsafe_copy(match):
    _, st, _, moments = match
    goal = next(m for m in moments if m.kind == "goal")
    roster = {pid: p.info.short_name for pid, p in st.players.items()}
    copy = {"en": {"casual": {"caption": "GOAL", "line": "Time to place a bet!", "explainer": ""}}}
    assert not verify_texts(copy, [goal.facts], set(goal.players), roster).ok


def _job(st, m, langs):
    names = names_for(st)
    nd = {"players": names.players, "teams": names.teams}
    return StoryJob(m.as_dict(), {"score": st.score}, langs, nd, names.players, st.home, st.away)


async def _run_all(rt, jobs):
    return await asyncio.gather(*(run_story(rt, j) for j in jobs))


def test_story_workflow_offline_all_languages(match):
    _, st, _, moments = match
    rt = AgentRuntime(LLMConfig())
    story = [m for m in moments if m.lane == "story"][:8]
    done = asyncio.run(_run_all(rt, [_job(st, m, list(LANGS)) for m in story]))
    for job in done:
        assert job.verdict["ok"], job.verdict
        assert set(job.narration) == set(LANGS)
        assert {t["agent"] for t in job.trace} >= {"Verifier", "Producer"}


def test_chaos_degrades_to_grounded_copy(match):
    _, st, _, moments = match
    rt = AgentRuntime(LLMConfig())
    rt.telemetry.chaos_fail_rate = 1.0
    m = next(m for m in moments if m.kind == "goal")
    job = asyncio.run(run_story(rt, _job(st, m, ["en", "es"])))
    assert job.verdict["ok"]
    assert job.narration["en"]["casual"]["line"]
    statuses = {(s.agent, s.status) for s in rt.telemetry.spans}
    assert ("Analyst", "error") in statuses and ("Analyst", "fallback") in statuses


def test_director_gives_rival_fans_different_broadcasts(match):
    _, st, _, moments = match
    names = names_for(st)
    goal = next(m for m in moments if m.kind == "goal")
    i18n = {lang: {p: narrate(goal.as_dict(), names, lang, p, st.home, st.away) for p in PERSONAS} for lang in LANGS}
    cue = Producer(st).from_moment(goal, i18n, Provenance(agent="Producer", verified=True))
    scorer_fan = Director(FanProfile(id="a", favorite_team=goal.team, language="en"), st, names).decide(cue)
    rival = st.other(goal.team)
    rival_fan = Director(FanProfile(id="b", favorite_team=rival, language="ar", mode=Mode.ANALYST), st, names).decide(cue)
    assert scorer_fan and rival_fan
    assert scorer_fan.title != rival_fan.title
    assert scorer_fan.payload["partisan"] == "for" and rival_fan.payload["partisan"] == "against"
    assert rival_fan.payload["rtl"] is True


def test_pundit_answers_offline_in_several_languages(match):
    _, st, det, _ = match

    class Ctx:
        state, moments = st, det.moments

    pundit = Pundit(AgentRuntime(LLMConfig()), MatchTools(Ctx()))
    for lang, q in (("en", "Who is the best player?"), ("es", "¿Por qué presiona tanto?"), ("ar", "ما هي احتمالات الفوز؟")):
        res = asyncio.run(pundit.ask(q, lang))
        assert res["answer"] and res["tools"]


def test_api_and_mcp_smoke(client):
    if True:
        assert client.get("/api/health").json()["ok"]
        assert client.get("/api/match").json()["info"]["home"]["id"] == "NOR"
        assert client.post("/api/control", json={"action": "seek", "value": 30}).json()["clock"]
        recap = client.get("/api/recap", params={"language": "fr", "persona": "analyst"}).json()
        assert recap["verdict"]["ok"] and recap["recap"]["headline"]
        assert client.get("/api/schema/cue").json()["title"] == "Cue"
        tools = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                            headers={"Accept": "application/json, text/event-stream"}).json()
        assert {"get_tactical_picture", "explain_moment"} <= {t["name"] for t in tools["result"]["tools"]}


def test_verifier_checks_football_claims_in_every_language():
    facts = {"body_part": "foot", "set_piece": None, "xg": 0.2}
    cases = {
        "en": ("Valdane heads it in from close range!", True),
        "es": ("¡Cabezazo de Valdane!", True),
        "ar": ("رأسية رائعة من Valdane", True),
        "fr": ("Valdane marque depuis la surface.", False),
        "pt": ("Valdane marca de dentro da área.", False),
    }
    for lang, (line, should_fail) in cases.items():
        texts = {lang: {"casual": {"caption": "GOAL", "line": line, "explainer": ""}}}
        v = verify_texts(texts, [facts], set(), {}, claims=facts)
        assert (not v.ok) == should_fail, (lang, v.issues)
    ok = {"en": {"casual": {"caption": "GOAL", "line": "A low finish from the edge of the penalty area.", "explainer": ""}}}
    assert verify_texts(ok, [facts], set(), {}, claims=facts).ok
    pen = {"en": {"casual": {"caption": "GOAL", "line": "He converts the penalty.", "explainer": ""}}}
    assert not verify_texts(pen, [facts], set(), {}, claims=facts).ok
