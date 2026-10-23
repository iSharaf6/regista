"""Synthetic-only regressions for physical tracking and difficult feed boundaries."""
from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from regista.evaluation import replay
from regista.intel.moments import MomentDetector
from regista.intel.state import MatchState
from regista.schema.events import EventType
from regista.sim.engine import DT, MatchSimulator, SimResult, simulate


@pytest.mark.parametrize("team", ["NOR", "CAL"])
def test_carrier_obeys_speed_acceleration_and_measured_distance(team):
    sim = MatchSimulator(seed=2026102201)
    i = next(i for i in sim.on_team(team) if sim.role(i) != "GK")
    sim.pos[i] = (50, 34)
    sim.vel[:] = 0
    sim.attached = i
    offset = np.array([-0.6 if team == "NOR" else 0.6, 0.2])
    sim.ball[:2] = sim.pos[i] - offset
    measured = 0.0
    for _ in range(60):
        sim.ball[0] += 0.8 if team == "NOR" else -0.8
        before, velocity = sim.pos[i].copy(), sim.vel[i].copy()
        sim._step(sim.pos.copy(), np.ones(sim.N))
        displacement = np.linalg.norm(sim.pos[i] - before)
        measured += displacement
        assert displacement / DT <= sim.maxspd[i] + 1e-7
        assert np.linalg.norm(sim.vel[i] - velocity) <= 4.2 * DT + 1e-7
    assert sim.dist[i] == pytest.approx(measured)
    assert np.linalg.norm(sim.pos[i] - (sim.ball[:2] + offset)) < 2


def test_boundary_distance_counts_actual_movement():
    sim = MatchSimulator(seed=2026102201)
    i = sim.idx["NOR-08"]
    sim.pos[i] = (104.49, 34)
    sim.vel[i] = (5, 0)
    target = sim.pos.copy()
    target[i] = (120, 34)
    sim._step(target, np.ones(sim.N))
    assert sim.pos[i, 0] == 104.5
    assert sim.dist[i] == pytest.approx(0.01)
    assert sim.vel[i, 0] == pytest.approx(0.05)
    assert np.all(sim.dist[~sim.on] == 0)
    assert np.all(sim.vel[~sim.on] == 0)


def test_carrier_keeps_up_with_ball_under_normal_formation_urgency():
    sim = MatchSimulator(seed=2026102201)
    i = sim.idx["NOR-08"]
    sim.pos[i], sim.vel[i] = (50, 34), (0, 0)
    sim.ball = np.array([50.6, 33.8, 0.0])
    sim.poss, sim.carrier = sim.home.id, i
    path, duration = sim.walk_ball((50.6, 33.8), (75.4, 33.8), 6.2)
    sim.advance(duration, ball_fn=path, attach=i)
    assert np.linalg.norm(sim.ball[:2] - sim.pos[i]) < 2
    assert np.linalg.norm(sim.vel[i]) <= sim.maxspd[i]


@pytest.mark.parametrize("t,period,p2_start,expected", [
    (59.99999999999999, 1, 0, (1, 1, 0, "2'")),
    (2699.9999999999995, 1, 0, (1, 45, 0, "45+1'")),
    (3900.5999999999995, 2, 3840.6, (2, 46, 0, "47'")),
    (6540.599999999999, 2, 3840.6, (2, 90, 0, "90+1'")),
])
def test_clock_agrees_with_rounded_feed_timestamp(t, period, p2_start, expected):
    sim = MatchSimulator(seed=2026102201)
    sim.t, sim.period, sim.p2_start = t, period, p2_start
    assert sim.clock() == expected


@pytest.mark.parametrize("duration", [0.01, 0.31, 1.09, 1.11, 3.43])
def test_action_completion_matches_tracking_grid(duration):
    sim = MatchSimulator(seed=2026102201)
    sim.t = 12.4
    end = sim._end_time(duration)
    sim.advance(duration)
    assert round(sim.t, 2) == end
    assert round(sim._ft[-1], 2) == end


@pytest.fixture(scope="module")
def seeded_match():
    return simulate("ASH", "KES", 2026102202, "press")


def test_full_match_tracking_respects_each_players_top_speed(seeded_match):
    res = seeded_match
    players = {p.id: p for t in (res.info.home, res.info.away) for p in t.players}
    dt = np.diff(res.frame_t.astype(float))
    speeds = np.linalg.norm(np.diff(res.frame_pos.astype(float), axis=0), axis=2) / dt[:, None] * 3.6
    speeds[dt >= 1] = np.nan  # half-time repositioning is not running
    caps = np.array([players[pid].top_speed_kmh for pid in res.info.roster])
    # Float32 timestamps/positions can perturb the measured speed by <0.1 km/h.
    assert not np.any(speeds > caps[None, :] + 0.2)


def test_full_match_event_order_score_and_stoppage(seeded_match):
    res = seeded_match
    assert all(a.t <= b.t for a, b in zip(res.events, res.events[1:], strict=False))
    assert len({e.id for e in res.events}) == len(res.events)
    assert [e.seq for e in res.events] == list(range(1, len(res.events) + 1))
    goals = Counter(e.team for e in res.events if e.type == EventType.GOAL)
    assert res.summary["score"] == {t.id: goals[t.id] for t in (res.info.home, res.info.away)}
    p2_start = next(e.t for e in res.events if e.type == EventType.SECOND_HALF)
    assert any("+" in e.clock and e.period == 1 for e in res.events)
    assert any("+" in e.clock and e.period == 2 for e in res.events)
    for event in res.events:
        elapsed = round(event.t if event.period == 1 else event.t - p2_start + 2700, 2)
        assert event.minute == int(elapsed // 60)
        assert event.second == int(elapsed % 60)
        if "t_end" in event.qualifiers:
            ticks = (event.qualifiers["t_end"] - event.t) / DT
            assert ticks == pytest.approx(round(ticks))
        if event.type in {EventType.GOAL, EventType.SAVE}:
            shot = next(e for e in res.events if e.id == event.related[0])
            assert shot.qualifiers["t_end"] <= event.t


@pytest.mark.parametrize("subs_used", [0, 5])
def test_multiple_reds_and_keeper_replacement_keep_manpower_consistent(subs_used):
    sim = MatchSimulator(seed=2026102201)
    sim.subs_made[sim.home.id] = subs_used
    keeper = next(i for i in sim.on_team(sim.home.id) if sim.role(i) == "GK")
    sim.emit(EventType.CARD, sim.home.id, keeper, outcome="red")
    sim.send_off(keeper)
    defender = next(i for i in sim.on_team(sim.home.id) if sim.role(i) == "CB")
    sim.emit(EventType.CARD, sim.home.id, defender, outcome="yellow")
    sim.yellow.add(defender)
    sim.emit(EventType.CARD, sim.home.id, defender, outcome="second_yellow")
    sim.send_off(defender)
    assert len(sim.on_team(sim.home.id)) == 9
    assert sum(sim.role(i) == "GK" for i in sim.on_team(sim.home.id)) == 1
    substitutions = [e for e in sim.events if e.type == EventType.SUBSTITUTION]
    assert len(substitutions) == (1 if subs_used == 0 else 0)
    state = MatchState(sim._info())
    detector = MomentDetector(state)
    moments = []
    for event in sim.events:
        moments.extend(detector.on_enriched(state.on_event(event)))
    assert state.red_cards[sim.home.id] == 2
    assert sum(p.on_pitch for p in state.players.values() if p.team == sim.home.id) == 9
    assert [m.facts["players_remaining"] for m in moments if m.kind == "red_card"] == [10, 9]
    sim.advance(DT)
    assert np.isfinite(sim._fp[-1][:len(sim.home.players), 0]).sum() == 9


def test_penalty_uses_observable_marker_and_derived_model_probability():
    sim = MatchSimulator(seed=2026102201)
    sim.penalty(sim.home.id)
    shot = next(e for e in sim.events if e.type == EventType.SHOT)
    assert shot.qualifiers["set_piece"] == "penalty"
    assert "xg" not in shot.qualifiers
    state = MatchState(sim._info())
    for event in sim.events:
        state.on_event(event)
    assert state.enriched[shot.id]["xg"] == 0.76
    assert next(t for t in sim.truth if t.get("event") == shot.id)["true_xg"] == 0.76


def test_empty_feed_and_quiet_tracking_do_not_invent_events():
    sim = MatchSimulator(seed=2026102201)
    empty = SimResult(sim._info(), [], np.empty(0), np.empty((0, 3)), np.empty((0, sim.N, 2)), [])
    state, _, moments = replay(empty)
    assert state.status == "pre_match"
    assert state.score == {"NOR": 0, "CAL": 0}
    assert moments == []
    sim.advance(5, press=False, dead=True)
    quiet = sim._result()
    state, _, moments = replay(quiet)
    assert state.score == {"NOR": 0, "CAL": 0}
    assert state.events == {}
    assert all(m.kind not in {"goal", "red_card", "half_time", "full_time"} for m in moments)


def test_replay_uses_serialized_frame_time_like_live_session(monkeypatch):
    sim = MatchSimulator(seed=2026102201)
    sim.t = 1.4
    event = sim.emit(EventType.GOAL, sim.home.id, sim.idx["NOR-09"])
    sim._record()
    sim.t = 1.6
    sim._record()
    # float32(1.4) is 1.399999976: comparing it directly delays the event one frame.
    assert float(np.float32(event.t)) < event.t
    monkeypatch.setattr("regista.runtime.session.match_context", lambda st: {"frame_t": st.last_frame["t"]})
    contexts = {}
    replay(sim._result(), contexts)
    assert contexts["m001"]["frame_t"] == 1.4


@pytest.mark.parametrize("truth_t,detection_t,expected_delay", [
    (1000, 1960, 16),  # a long delay entirely within one half must not lose 15 minutes
    (2700, 3900, 5),  # remove the actual interval between the half-time events
    (2660, 4100, 9),  # matching also uses playing time, not a 24-minute wall-clock gap
])
def test_evaluation_delays_use_actual_half_time_interval(monkeypatch, truth_t, detection_t, expected_delay):
    from regista import evaluation
    from regista.intel.moments import Moment

    sim = MatchSimulator(seed=2026102201)
    sim.t = 2800
    sim.emit(EventType.HALF_TIME)
    sim.period, sim.t, sim.p2_start = 2, 3700, 3700
    sim.emit(EventType.SECOND_HALF)
    sim.truth.append({"type": "tactical_shift", "t": truth_t, "team": "NOR", "clock": "46'",
                      "before": {"press_intensity": 0.2}, "after": {"press_intensity": 0.8}})
    sim._record()
    result = sim._result()
    state = MatchState(result.info)
    state._p1_bins = 47
    moment = Moment(id="m001", t=detection_t, clock="51'", kind="press_shift", team="NOR", players=[],
                    importance=0, headline="Synthetic press shift", facts={"direction": "up",
                    "onset_index": int(truth_t // 60), "onset_clock": "46'"})
    monkeypatch.setattr(evaluation, "simulate", lambda *args: result)
    monkeypatch.setattr(evaluation, "replay", lambda *args: (state, None, [moment]))
    measured = evaluation.evaluate([2026102201])["press_shift"]
    assert measured["recall"] == 1
    assert measured["mean_delay_min"] == expected_delay
    assert measured["median_onset_error_min"] == 0


def test_empty_evaluation_does_not_claim_a_zero_false_alarm_rate():
    from regista.evaluation import evaluate

    result = evaluate([])
    assert result["matches"] == 0
    assert result["press_shift"]["false_alarms_per_match"] is None
    assert result["press_shift"]["recall"] is None


def test_llm_evaluation_flushes_final_events_using_feed_timestamps(monkeypatch):
    from regista import llm_eval

    sim = MatchSimulator(seed=2026102201)
    sim.t = 1.4
    sim._record()
    sim.emit(EventType.GOAL, sim.home.id, sim.idx["NOR-09"])
    monkeypatch.setattr(llm_eval, "simulate", lambda *args: sim._result())
    found = llm_eval.detect(2026102201)
    assert found["state"].score[sim.home.id] == 1
    assert [m.kind for m, _ in found["found"]] == ["goal"]
    # A terminal event after the last tracking sample must also be consumed.
    sim.t = 1.6
    sim.emit(EventType.GOAL, sim.home.id, sim.idx["NOR-09"])
    found = llm_eval.detect(2026102201)
    assert found["state"].score[sim.home.id] == 2
    assert len(found["found"]) == 2
