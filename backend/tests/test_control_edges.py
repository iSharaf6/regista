"""Synthetic feed/control boundary regressions: reject bad inputs without corrupting the active match."""

import asyncio

import pytest

import regista.api.app as api


@pytest.mark.parametrize("patch", [
    {"seed": -1}, {"seed": 1.5}, {"seed": True}, {"seed": None}, {"seed": 2**32},
    {"home": "UNKNOWN"}, {"home": "CAL"}, {"scenario": "unknown"},
])
def test_bad_match_settings_leave_the_active_match_intact(client, patch):
    before = client.get("/api/match").json()
    settings = {"home": "NOR", "away": "CAL", "seed": 16, "scenario": "derby", **patch}
    response = client.post("/api/control", json={"action": "load", "value": settings})
    assert response.status_code == 422
    after = client.get("/api/match").json()
    assert after["info"]["match_id"] == before["info"]["match_id"]
    assert after["params"] == before["params"]
    assert after["control"]["playing"] == before["control"]["playing"]


@pytest.mark.parametrize("action,value", [("load", None), ("seek", -1), ("seek", "no"),
                                         ("speed", None), ("chaos", []), ("chaos", {"latency_ms": None})])
def test_invalid_controls_return_actionable_errors(client, action, value):
    response = client.post("/api/control", json={"action": action, "value": value})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_nonfinite_controls_do_not_poison_the_clock(client):
    s = api.S()
    before = s.control_state()
    for action in ("seek", "speed"):
        for value in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValueError, match="finite"):
                asyncio.run(s.control(action, value))
    assert s.clock_t == before["t"] or abs(s.clock_t - before["t"]) < 0.11
    assert s.speed == before["speed"]


def test_bad_socket_control_does_not_disconnect_the_viewer(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "hello"
        ws.send_json({"type": "control", "action": "seek", "value": "bad"})
        while (message := ws.receive_json())["type"] != "error":
            pass
        assert "finite number" in message["error"]
        ws.send_json({"type": "control", "action": "pause"})
        while (message := ws.receive_json())["type"] != "control":
            pass
        assert message["control"]["playing"] is False


def test_old_match_event_is_rejected_before_it_changes_a_new_feed(client):
    info = client.get("/api/match").json()["info"]
    old_id = info["match_id"]
    info["match_id"] = f"{old_id}-fresh-feed"
    try:
        assert client.post("/api/feed/start", json=info).status_code == 200
        event = {"id": "late-goal", "match_id": old_id, "seq": 1, "t": 20,
                 "period": 1, "minute": 0, "second": 20, "clock": "0'", "type": "goal",
                 "team": info["home"]["id"], "player": info["home"]["players"][0]["id"]}
        response = client.post("/api/feed", json={"events": [event]})
        assert response.status_code == 422
        assert all(score == 0 for score in client.get("/api/state").json()["score"].values())
        assert api.S().res.events == []
    finally:
        client.post("/api/feed/stop")


def test_duplicate_roster_is_rejected_without_replacing_the_match(client):
    before = client.get("/api/match").json()
    info = before["info"]
    info["roster"] = [info["roster"][0]] * len(info["roster"])
    assert client.post("/api/feed/start", json=info).status_code == 422
    assert client.get("/api/match").json()["params"] == before["params"]


def test_joining_a_paused_goal_catches_up_socket_and_polling_viewers():
    """An OBS browser source opened after a goal must not wait for the next event to show it."""
    from regista.runtime.session import MatchSession
    from regista.schema.profiles import FanProfile

    s = MatchSession()
    goal = next(event for event in s.events if event.type == "goal")
    s.advance(goal.t - s.clock_t + 1, live=False)
    assert not s.playing
    out = s.onair(FanProfile(language="ar"))
    assert out["flat"]["lower_title"] and out["flat"]["lower_body"]
    viewer = s.connect(FanProfile(language="es"))
    messages = list(viewer.queue._queue)
    assert messages[0]["type"] == "hello"
    assert any(m["type"] == "cue" and m["cue"]["kind"] == "moment" and m["cue"]["locale"] == "es" for m in messages[1:])


def test_cached_highlight_does_not_consume_replay_rate_limit(client, monkeypatch):
    out = client.get("/api/explore", params={"moment": "highlight"}).json()
    assert out["moment"]["kind"] == "goal"
    monkeypatch.setattr(api, "recap_limit", api.RateLimit(0))
    assert client.get("/api/explore", params={"moment": "highlight"}).status_code == 200
    assert client.get("/api/explore", params={"moment": out["moment"]["id"]}).status_code == 200


def test_goal_count_drill_is_not_offered_for_non_goal_moments(client):
    out = client.get("/api/explore").json()
    non_goal = next(m["id"] for m in out["moments"] if m["kind"] != "goal")
    assert client.get("/api/explore", params={"moment": non_goal, "drill": "ar"}).status_code == 404
    assert client.get("/api/explore", params={"moment": non_goal}).json()["drills"] == []


def test_cached_highlight_does_not_wait_for_an_unrelated_model_build():
    from regista.agents.config import LLMConfig
    from regista.runtime.explore import Explore

    async def run():
        ex = Explore(LLMConfig())
        ex._catalogue = [{"id": "goal-1", "kind": "goal", "clock": "63'", "headline": "Synthetic goal"}]
        ex.cache["goal-1"] = {"moment": {"id": "goal-1"}}
        async with ex.lock:
            out = await asyncio.wait_for(ex.get("highlight"), timeout=0.2)
            assert out["moment"]["id"] == "goal-1"
    asyncio.run(run())


def test_existing_socket_and_polling_viewers_catch_up_after_seek():
    from regista.runtime.session import MatchSession
    from regista.schema.profiles import FanProfile

    s = MatchSession()
    profile = FanProfile(language="ar", favorite_team="CAL")
    assert s.onair(profile)["flat"]["lower_title"] == ""
    viewer = s.connect(FanProfile(language="es"))
    while not viewer.queue.empty():
        viewer.queue.get_nowait()
    goal = next(event for event in s.events if event.type == "goal")
    second_half = next(event.t for event in s.events if event.type == "second_half")
    minute = (goal.t + 1) / 60 if goal.period == 1 else 45 + (goal.t + 1 - second_half) / 60
    s.seek(minute)
    assert s.onair(profile)["flat"]["lower_title"]
    messages = list(viewer.queue._queue)
    assert messages[0]["type"] == "reset"
    assert any(m["type"] == "cue" and m["cue"]["kind"] == "moment" and m["cue"]["locale"] == "es" for m in messages[1:])
