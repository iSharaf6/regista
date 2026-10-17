"""Real-world integration paths: a provider pushing a live feed, production tools polling what is on air,
webhooks for media teams, and the guards that keep a public deployment usable."""

from __future__ import annotations

import asyncio
import time

import pytest

import regista.api.app as api
from regista.runtime.webhooks import Webhooks
from regista.schema.profiles import FanProfile
from regista.sim.engine import simulate


@pytest.fixture(scope="module")
def match():
    return simulate("NOR", "CAL", 16, "derby")


def _batches(res, until_t, step=150):
    events = sorted(res.events, key=lambda e: (e.qualifiers.get("t_end", e.t), e.seq))
    ei = 0
    for k0 in range(0, len(res.frame_t), step):
        frames = [res.frame(k) for k in range(k0, min(k0 + step, len(res.frame_t)))]
        last = frames[-1]["t"]
        batch = []
        while ei < len(events) and events[ei].qualifiers.get("t_end", events[ei].t) <= last:
            batch.append(events[ei].model_dump(mode="json"))
            ei += 1
        yield {"frames": frames, "events": batch}
        if last > until_t:
            return


def test_feed_requires_start_and_validates_roster(client, match):
    assert client.post("/api/feed", json={"frames": [], "events": []}).status_code == 409
    assert client.post("/api/feed/start", json=match.info.model_dump(mode="json")).status_code == 200
    bad = {"frames": [{"t": 1.0, "b": [50, 30, 0], "p": [[1, 1]]}], "events": []}
    assert client.post("/api/feed", json=bad).status_code == 422
    client.post("/api/feed/stop")


def test_live_feed_drives_the_whole_pipeline_and_onair(client, match):
    assert client.post("/api/feed/start", json=match.info.model_dump(mode="json")).json()["mode"] == "live"
    before = client.get("/api/onair", params={"mode": "casual", "lang": "es", "team": "NOR"}).json()
    assert before["score"] == "0-0"
    headlines, seen_lower = [], []
    for body in _batches(match, until_t=21 * 60):
        r = client.post("/api/feed", json=body).json()
        headlines += r["new_moments"]
        onair = client.get("/api/onair", params={"mode": "casual", "lang": "es", "team": "NOR"}).json()
        if onair["flat"]["lower_title"]:
            seen_lower.append(onair["flat"]["lower_title"])
    assert any(h.startswith("GOAL Northbridge") for h in headlines)
    assert client.get("/api/state").json()["score"]["NOR"] == 1
    assert seen_lower, "the goal lower third must be visible to polling production tools"
    assert any("GOLAZO" in t or "GOL" in t for t in seen_lower)  # Spanish copy, partisan for a Northbridge fan
    # providers may resend: ingest is idempotent
    replay_first = next(_batches(match, until_t=0))
    again = client.post("/api/feed", json=replay_first).json()
    assert again["accepted_frames"] == 0 and again["accepted_events"] == 0
    assert client.post("/api/feed/stop").json()["mode"] == "replay"


def test_producer_token_guards_shared_controls(client, monkeypatch):
    monkeypatch.setattr(api, "ADMIN_TOKEN", "s3cret")
    assert client.post("/api/control", json={"action": "pause"}).status_code == 401
    ok = client.post("/api/control", json={"action": "pause"}, headers={"X-Regista-Token": "s3cret"})
    assert ok.status_code == 200
    assert client.get("/api/health").json()["producer_token_required"] is True


def test_pundit_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(api, "ask_limit", api.RateLimit(2))
    answers = [client.post("/api/ask", json={"question": "Who is the best player?", "language": "fr"}).json() for _ in range(3)]
    assert answers[0]["model"] != "rate-limit" and answers[2]["model"] == "rate-limit"
    assert "minute" in answers[2]["answer"]


def test_webhook_payload_works_for_slack_teams_and_discord(match, monkeypatch):
    from regista.agents.templates import Names
    from regista.evaluation import replay

    monkeypatch.setenv("REGISTA_WEBHOOK_URL", "https://example.invalid/hook")
    monkeypatch.setenv("REGISTA_WEBHOOK_LANG", "ar")
    hooks = Webhooks()
    st, _, moments = replay(match)
    goal = next(m for m in moments if m.kind == "goal")
    assert hooks.wants(goal) and not hooks.wants(next(m for m in moments if m.kind == "master_pass"))
    names = Names({pid: p.info.short_name for pid, p in st.players.items()}, dict(st.short))
    msg = hooks.message(goal, names, st.home, st.away, "Northbridge Rovers v Port Calder FC")
    assert msg["text"] == msg["content"] and goal.evidence[0] in msg["text"]
    assert "هدف" in msg["text"]  # Arabic copy


def test_chaos_switches_itself_off():
    async def run():
        s = api.MatchSession()
        await s.control("chaos", {"fail_rate": 1.0, "latency_ms": 500})
        assert s.telemetry.chaos_fail_rate == 1.0 and s._chaos_until > time.monotonic()
        s._chaos_until = time.monotonic() - 1
        await s._housekeeping()
        assert s.telemetry.chaos_fail_rate == 0.0 and s.telemetry.chaos_latency_ms == 0.0
    asyncio.run(run())


def test_abandoned_live_feed_returns_to_the_demo(match):
    async def run():
        s = api.MatchSession()
        s.autoplay = True
        s.start_live(match.info)
        assert s.mode == "live"
        s._last_ingest = time.monotonic() - s.live_idle_s - 1
        await s._housekeeping()
        assert s.mode == "replay" and s.playing
    asyncio.run(run())


def test_an_empty_room_pauses_the_demo_until_someone_watches():
    """An always-on replica must idle when nobody is watching, not loop the match and spend model calls."""
    async def run():
        s = api.MatchSession()
        s.autoplay = True
        await s.control("play")
        await s._housekeeping()
        assert s.playing  # a short gap between viewers is not an empty room
        s._unwatched_since = time.monotonic() - s.empty_pause_s - 1
        await s._housekeeping()
        assert not s.playing and s.control_state()["paused_for_empty_room"]
        v = s.connect(FanProfile(language="ar"))
        await s._housekeeping()
        assert s.playing and not s.control_state()["paused_for_empty_room"]
        # full time with nobody watching stays parked; the next viewer gets a fresh kickoff
        s.disconnect(v.id)
        s.seek(95)
        s.playing, s._ended_at = False, time.monotonic() - 60
        await s._housekeeping()
        assert not s.playing and s.clock_t > 60
        s.connect(FanProfile())
        await s._housekeeping()
        assert s.playing and s.clock_t < 60
    asyncio.run(run())


def test_half_time_recap_stays_true_later_in_the_match():
    async def run():
        s = api.MatchSession()
        s.seek(64)
        live = await s.recap("en", "analyst")
        assert live["period"] == "live" and live["recap"]["headline"]
        ht = await s.recap("en", "analyst", "half_time")
        assert ht["period"] == "half_time" and ht["verdict"]["ok"]
        ht_clock = s._ht_base["clock"]
        assert ht_clock.startswith("45") and all(m["t"] <= s._ht_base["moments"][-1]["t"] for m in s._ht_base["moments"])
        assert not any(m["kind"] == "press_shift" for m in s._ht_base["moments"])  # the 63' press shift is not in it
        assert "since 60'" not in ht["recap"]["tactical_story"]
        # asking for full time before it happens gives a live report, not a fake final
        assert (await s.recap("en", "casual", "full_time"))["period"] == "live"
    asyncio.run(run())
