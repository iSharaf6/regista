"""Real-world integration paths: a provider pushing a live feed, production tools polling what is on air,
webhooks for media teams, and the guards that keep a public deployment usable."""

from __future__ import annotations

import asyncio
import json
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
    goal = next(event for event in match.events if event.type == "goal")
    for body in _batches(match, until_t=goal.t + 60, step=25):
        r = client.post("/api/feed", json=body).json()
        headlines += r["new_moments"]
        onair = client.get("/api/onair", params={"mode": "casual", "lang": "es", "team": goal.team}).json()
        if onair["flat"]["lower_title"]:
            seen_lower.append(onair["flat"]["lower_title"])
    assert any(h.startswith("GOAL ") for h in headlines)
    assert client.get("/api/state").json()["score"][goal.team] == 1
    assert seen_lower, "the goal lower third must be visible to polling production tools"
    assert any("GOLAZO" in t or "GOL" in t for t in seen_lower)  # Spanish copy for the scoring team's fan
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


def test_feed_token_locks_the_feed_but_not_playback(client, monkeypatch):
    """Nobody can take over the public broadcast, while judges can still play, pause and run the outage demo."""
    monkeypatch.setattr(api, "FEED_TOKEN", "feed-only")
    monkeypatch.setattr(api, "ADMIN_TOKEN", "")
    assert client.post("/api/feed/stop").status_code == 401
    assert client.post("/api/feed", json={"frames": [], "events": []}).status_code == 401
    assert client.post("/api/control", json={"action": "pause"}).status_code == 200  # playback stays open
    health = client.get("/api/health").json()
    assert health["feed_token_required"] and not health["producer_token_required"]
    too_big = {"frames": [{"t": 0.0, "b": [0, 0, 0], "p": []}] * 3001, "events": []}
    assert client.post("/api/feed", json=too_big, headers={"X-Regista-Token": "feed-only"}).status_code == 422


def test_recaps_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(api, "recap_limit", api.RateLimit(2))
    assert [client.get("/api/recap", params={"language": "en"}).status_code for _ in range(3)] == [200, 200, 429]


def test_pundit_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(api, "ask_limit", api.RateLimit(2))
    answers = [client.post("/api/ask", json={"question": "Who is the best player?", "language": "fr"}).json() for _ in range(3)]
    assert answers[0]["model"] != "rate-limit" and answers[2]["model"] == "rate-limit"
    assert "minute" in answers[2]["answer"]


def test_rate_limits_trust_only_the_address_the_ingress_appends(client, monkeypatch):
    """Behind Container Apps the ingress appends the caller's real address to X-Forwarded-For; earlier entries are the
    caller's own and could be forged, so forging them must not buy more Pundit questions."""
    monkeypatch.setattr(api, "ask_limit", api.RateLimit(2))
    ask = {"question": "Who is the best player?", "language": "en"}
    models = [client.post("/api/ask", json=ask, headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}).json()["model"]
              for i in range(3)]
    assert models[2] == "rate-limit"  # three forged first hops, one real address: limited together
    other = client.post("/api/ask", json=ask, headers={"X-Forwarded-For": "198.51.100.4"}).json()
    assert other["model"] != "rate-limit"  # a different real caller is not affected


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


def test_web_app_never_serves_files_outside_its_folder(tmp_path):
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>")
    (root / "assets" / "app.js").write_text("js")
    (tmp_path / "secret.txt").write_text("nope")
    (root / "escape").symlink_to(tmp_path / "secret.txt")
    assert api.web_file(root, "assets/app.js") == (root / "assets" / "app.js").resolve()
    assert api.web_file(root, "") == (root / "index.html").resolve()
    assert api.web_file(root, "control") == (root / "index.html").resolve()  # SPA routes get the app
    for bad in ["../secret.txt", "assets/../../secret.txt", "../../../../etc/passwd", "escape", "/etc/passwd"]:
        assert api.web_file(root, bad) is None, bad


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


def test_a_late_story_never_lands_on_a_new_timeline(monkeypatch):
    """A model call that finishes after a restart or a new match must be discarded, not attached to a reused id."""
    import regista.runtime.session as session_mod

    release = asyncio.Event()
    real = session_mod.run_story

    async def slow_run_story(rt, job):
        await release.wait()
        return await real(rt, job)

    monkeypatch.setattr(session_mod, "run_story", slow_run_story)

    async def run():
        s = api.MatchSession()
        goal_event = next(e for e in s.events if e.type == "goal")
        s.advance(goal_event.t - s.clock_t + 2, live=False)
        goal = next(m for m in s.moments if m.kind == "goal")
        task = asyncio.create_task(s._run_story(goal, s._gen, s._context()))
        await asyncio.sleep(0)
        s.load("NOR", "CAL", 17, "derby")  # a different match reusing moment ids from m001
        s.seek(25)
        release.set()
        await task
        assert goal.id not in s.story or s.story[goal.id]["narration"] == {}
        assert all(c.id != goal.id or "goal" not in str(c.model_dump()).lower() for c in s.cues if c.kind.value != "score_bug")
        # and a job queued before the reset is skipped outright
        before = len(s.story)
        await s._run_story(goal, s._gen - 1, {})
        assert len(s.story) == before
    asyncio.run(run())


def _moments_of(s):
    return [(m.kind, m.clock, tuple(m.players), json.dumps(m.facts, sort_keys=True, default=str)) for m in s.moments]


def test_live_feed_matches_replay_whatever_the_batch_size(match):
    until = 25 * 60.0

    async def replay_run():
        s = api.MatchSession()
        s.load("NOR", "CAL", 16, "derby")
        s.advance(until - s.clock_t, live=False)
        return _moments_of(s), s.state.snapshot()["teams"]

    async def live_run(step):
        s = api.MatchSession()
        s.start_live(match.info)
        for b in _batches(match, until, step=step):
            frames = [f for f in b["frames"] if f["t"] <= until]
            if not frames:
                break
            s.ingest(frames, [api.MatchEvent.model_validate(e) for e in b["events"]
                              if e["qualifiers"].get("t_end", e["t"]) <= frames[-1]["t"]])
        return _moments_of(s), s.state.snapshot()["teams"]

    ref = asyncio.run(replay_run())
    for step in (7, 150, 900):
        got = asyncio.run(live_run(step))
        assert got[0] == ref[0], f"moments differ with batches of {step} frames"
        assert got[1] == ref[1], f"team state differs with batches of {step} frames"


def test_changing_profile_recuts_what_is_on_air():
    """The client drops its cues on a profile change, so the server re-sends what is on air, cut for the new fan."""
    async def run():
        s = api.MatchSession()
        goal_event = next(e for e in s.events if e.type == "goal")
        s.advance(goal_event.t - s.clock_t + 2, live=False)
        goal = next(m for m in s.moments if m.kind == "goal")
        assert any(c.moment_id == goal.id for c in s.live_cues())
        v = s.connect(FanProfile())
        while not v.queue.empty():
            v.queue.get_nowait()
        opponent = s.state.away if goal.team == s.state.home else s.state.home
        s.set_profile(v.id, FanProfile(id=v.id, mode="analyst", language="es", favorite_team=opponent))
        msgs = [v.queue.get_nowait() for _ in range(v.queue.qsize())]
        cues = [m["cue"] for m in msgs if m["type"] == "cue"]
        assert msgs[0]["type"] == "profile" and any(c["kind"] == "score_bug" for c in cues)
        goal_cues = [c for c in cues if c.get("moment_id") == goal.id]
        assert goal_cues and goal_cues[0]["locale"] == "es" and goal_cues[0]["payload"].get("partisan") == "against"
    asyncio.run(run())


def test_explore_one_moment_shows_three_fans_without_touching_the_broadcast(client):
    client.post("/api/control", json={"action": "pause"})  # a paused shared broadcast must stay exactly where it is
    before = client.get("/api/state").json()
    out = client.get("/api/explore", params={"moment": "highlight"}).json()
    assert out["curated"] and out["moment"]["kind"] == "goal" and out["moments"]
    assert [f["name"] for f in out["fans"]] == ["Tom", "Amira", "Lucía", "Sam"]  # Sam: Tom's same-language pair
    assert [f["cue"]["locale"] for f in out["fans"]] == ["en", "ar", "es", "en"]
    tom, sam = out["fans"][0]["cue"], out["fans"][3]["cue"]
    assert tom["body"] != sam["body"] or tom["payload"]["explainer"] != sam["payload"]["explainer"]  # audience, not language
    assert all(d[-1]["status"] == "passed" and d[-1]["source"] == "model" for d in out["story"]["drafts"].values())
    assert out["story"]["verdict"]["ok"] and set(out["moment"]["fact_kinds"].values()) == {"observed", "model estimate"}
    assert out["fans"][1]["cue"]["payload"].get("partisan") == "against"  # Amira supports the side that conceded
    assert client.get("/api/explore", params={"moment": "highlight"}).json()["fans"] == out["fans"]
    assert out["moment"]["id"] == [m["id"] for m in out["moments"] if m["kind"] == "goal"][-1]
    assert client.get("/api/explore", params={"moment": "nope"}).status_code == 404
    assert client.get("/api/state").json()["clock"] == before["clock"]  # the shared broadcast did not move


def test_an_empty_room_puts_a_visitors_custom_match_back_to_the_demo():
    """A judge who loads another match in the Data lab must not leave it for the next judge."""
    from regista.runtime.session import DEMO

    async def run():
        s = api.MatchSession()
        s.autoplay = True
        await s.control("load", {"home": "ASH", "away": "KES", "seed": 3, "scenario": "press"})
        assert s.params != DEMO
        s._unwatched_since = time.monotonic() - s.empty_pause_s - 1
        await s._housekeeping()
        assert s.params == DEMO and not s.playing and s.control_state()["paused_for_empty_room"]
        s.connect(FanProfile())
        await s._housekeeping()
        assert s.playing  # the next judge gets the demo match, playing
    asyncio.run(run())


def test_explore_warms_the_demo_goals_without_blocking_the_broadcast():
    """After a cold start the goals are replayed ahead of the first visitor, in a worker thread: the shared
    broadcast's event loop keeps ticking while the match is replayed."""
    from regista.agents.config import LLMConfig
    from regista.runtime.explore import Explore

    async def run():
        ex = Explore(LLMConfig())
        ex._session()  # simulate the demo match once, as the live session already has in production
        gaps: list[float] = []
        last = time.monotonic()

        async def tick():
            nonlocal last
            while True:
                await asyncio.sleep(0.02)
                now = time.monotonic()
                gaps.append(now - last)
                last = now

        ticker = asyncio.create_task(tick())
        await ex.warm()
        ticker.cancel()
        goals = [m["id"] for m in await ex.catalogue() if m["kind"] == "goal"]
        assert len(goals) >= 2 and set(goals) <= set(ex.cache)
        assert max(gaps) < 1.0, max(gaps)
    asyncio.run(run())


def _seen(cue: dict) -> str:
    """What a fan actually reads on a cue."""
    return " ".join([cue.get("title") or "", cue.get("body") or "", cue["payload"].get("explainer") or ""])


def test_a_recovery_drill_retries_only_the_drilled_language(client):
    """The correction receipt, from a labelled drill: Arabic's first draft carries a planted wrong goal count, the
    Verifier rejects it with its real finding, only Arabic is rewritten, and nothing rejected reaches the fans."""
    out = client.get("/api/explore", params={"drill": "ar"}).json()
    drafts = out["story"]["drafts"]
    ar = drafts["ar"]
    assert [d["status"] for d in ar] == ["rejected", "passed"] and ar[0]["drill"] and "97" in ar[0]["copy"]["analyst"]["explainer"]
    assert any("goal count" in issue for issue in ar[0]["issues"])  # the finding comes from that attempt's own verdict
    assert all(len(drafts[lang]) == 1 and drafts[lang][0]["status"] == "passed" for lang in ("en", "es"))
    assert out["story"]["fallback_langs"] == [] and out["drill"]["lang"] == "ar"
    assert all("97" not in _seen(f["cue"]) for f in out["fans"])  # rejected text never airs


def test_an_exhausted_drill_ends_on_a_template_for_that_language_only(client):
    out = client.get("/api/explore", params={"drill": "ar2"}).json()
    ar = out["story"]["drafts"]["ar"]
    assert [(d["source"], d["status"]) for d in ar] == [("model", "rejected"), ("model", "rejected"), ("template", "passed")]
    assert out["story"]["fallback_langs"] == ["ar"] and out["story"]["verdict"]["ok"]
    assert all(out["story"]["drafts"][lang][-1]["source"] == "model" for lang in ("en", "es"))
    assert all("97" not in _seen(f["cue"]) for f in out["fans"])
    assert client.get("/api/explore", params={"drill": "zz"}).status_code == 404
