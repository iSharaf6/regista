"""MatchSession: the live pipeline.

    feed (5 Hz tracking + events) --bus--> Interpret (MatchState, MomentDetector)
        fast lane:  Producer cues in milliseconds, template copy in 5 languages
        story lane: Agent Framework workflow (Analyst > Narrator > Localizer > Verifier) upgrades copy in place
    --> Director per viewer --> WebSocket (overlay, fan app, control room) / MCP / REST

The session replays a seeded synthetic match on a real-time clock that can be
paused, sped up and scrubbed, so a full 95-minute story fits in a demo.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..agents.config import LLMConfig, load_config
from ..agents.director import Director
from ..agents.producer import Producer
from ..agents.pundit import Pundit
from ..agents.recap import (
    normalize_recap,
    offline_recap,
    recap_evidence,
    recap_fields,
    recap_payload,
    recap_shape_problems,
)
from ..agents.story import AgentFailure, AgentRuntime, StoryJob, run_story
from ..agents.telemetry import Span, Telemetry
from ..agents.templates import LANGS, PERSONAS, Names, narrate
from ..agents.tools import MatchTools
from ..agents.verifier import verify_texts
from ..intel.moments import Moment, MomentDetector
from ..intel.state import MatchState
from ..schema.cues import Cue, Provenance
from ..schema.profiles import FanProfile
from ..sim.engine import SimResult, simulate
from .bus import make_bus
from .live import CaptureViewer, LiveRecording, onair_payload, profile_key
from .webhooks import Webhooks

log = logging.getLogger("regista.session")
DEMO = {"home": "NOR", "away": "CAL", "seed": 16, "scenario": "derby"}
_SIM_CACHE: dict[tuple[str, str, int, str], SimResult] = {}


def get_sim(home: str, away: str, seed: int, scenario: str) -> SimResult:
    key = (home, away, seed, scenario)
    if key not in _SIM_CACHE:
        _SIM_CACHE[key] = simulate(home, away, seed, scenario)
    return _SIM_CACHE[key]


@dataclass
class Viewer:
    profile: FanProfile
    director: Director
    ops: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=lambda: asyncio.Queue(maxsize=2000))

    def send(self, msg: dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(msg)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
            self.queue.put_nowait(msg)


def match_context(state: MatchState) -> dict[str, Any]:
    """The live CONTEXT a story job sees: the match as it stands at the moment, frozen when the job is queued."""
    s = state.snapshot()
    return {"clock": s["clock"], "score": s["score"], "win_probability": s["win_probability"], "momentum": s["momentum"],
            "players_on_pitch": {t: 11 - n for t, n in state.red_cards.items()},
            "teams": {t: {k: v for k, v in s["teams"][t].items() if k in {"name", "xg", "shots", "possession", "pass_accuracy",
                                                                          "pressures", "high_regains"}}
                      for t in s["teams"]}}


def _event_order(e: Any) -> tuple[float, int]:
    """Events take effect when they complete (a pass when it arrives), then by sequence: replay and live agree."""
    return (float(e.qualifiers.get("t_end", e.t)), e.seq)


class MatchSession:
    def __init__(self, cfg: LLMConfig | None = None, story_workers: int = 4, bus: Any = None):
        self.cfg = cfg or load_config()
        self.telemetry = Telemetry()
        self.rt = AgentRuntime(self.cfg, self.telemetry)
        self.bus = bus or make_bus()
        self.viewers: dict[str, Viewer] = {}
        self.speed = 4.0
        self.playing = False
        self.story_workers = story_workers
        self._tasks: list[asyncio.Task[Any]] = []
        self._last_state_push = 0.0
        self.telemetry.listeners.append(self._on_span)
        # created once: story workers block on this queue, so it must survive pipeline resets
        self.queue: asyncio.Queue[tuple[int, Moment, dict[str, Any]]] = asyncio.Queue()
        self._gen = 0  # timeline generation: bumped on every reset so late model results cannot land on a new timeline
        self._pending_events: list[Any] = []
        self.mode = "replay"  # or "live": an external provider pushes the feed
        self.virtual: dict[str, CaptureViewer] = {}
        self.webhooks = Webhooks()
        self.autoplay = os.getenv("REGISTA_AUTOPLAY", "0") == "1"
        self._chaos_until = 0.0
        self._ended_at: float | None = None
        self._paused_at: float | None = None
        self._last_ingest = 0.0
        self.live_idle_s = float(os.getenv("REGISTA_LIVE_IDLE_S", "120"))
        self.empty_pause_s = float(os.getenv("REGISTA_EMPTY_PAUSE_S", "90"))
        self._unwatched_since: float | None = None
        self._empty_paused = False
        self.load(**DEMO)

    # ------------------------------------------------------------------ lifecycle
    def load(self, home: str, away: str, seed: int, scenario: str) -> None:
        self.params = {"home": home, "away": away, "seed": seed, "scenario": scenario}
        self.res = get_sim(home, away, seed, scenario)
        self.events = sorted(self.res.events, key=_event_order)
        self._reset_pipeline()

    def _reset_pipeline(self) -> None:
        info = self.res.info
        self.state = MatchState(info)
        self.detector = MomentDetector(self.state)
        self.producer = Producer(self.state)
        self.names = Names({pid: p.info.short_name for pid, p in self.state.players.items()}, dict(self.state.short))
        self.names_dict = {"players": self.names.players, "teams": self.names.teams}
        self.roster_names = {pid: p.info.short_name for pid, p in self.state.players.items()}
        self.tools = MatchTools(self)
        self.pundit = Pundit(self.rt, self.tools)
        self.fi = 0
        self.ei = 0
        self.clock_t = float(self.res.frame_t[0]) - 0.2
        self.cues: list[Cue] = []
        self.story: dict[str, dict[str, Any]] = {}
        self.recaps: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._ht_base: dict[str, Any] | None = None  # the match as it stood at the half-time whistle
        self._live_recaps: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}  # (lang, persona) -> (clock, recap)
        self._gen += 1
        self._pending_events = []
        while not self.queue.empty():  # stale story jobs belong to the previous timeline
            self.queue.get_nowait()
        for v in self.viewers.values():
            v.director = Director(v.profile, self.state, self.names)

    @property
    def moments(self) -> list[Moment]:
        return self.detector.moments

    async def start(self) -> None:
        if self._tasks:
            return
        self._tasks.append(asyncio.create_task(self._ticker()))
        for _ in range(self.story_workers):
            self._tasks.append(asyncio.create_task(self._story_worker()))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        await self.bus.close()

    # ------------------------------------------------------------------ viewers
    def connect(self, profile: FanProfile, ops: bool = False) -> Viewer:
        v = Viewer(profile, Director(profile, self.state, self.names), ops)
        self.viewers[v.id] = v
        v.send(self.hello(v))
        return v

    def disconnect(self, vid: str) -> None:
        self.viewers.pop(vid, None)

    def set_profile(self, vid: str, profile: FanProfile) -> None:
        v = self.viewers.get(vid)
        if v:
            v.profile = profile
            v.director.update_profile(profile)
            v.send({"type": "profile", "profile": profile.model_dump()})
            # the client drops its non-persistent cues on a profile change: re-cut what is on air now for the new profile
            for cue in self.live_cues():
                out = v.director.decide(cue)
                if out is not None:
                    v.send({"type": "cue", "cue": out.model_dump()})

    def live_cues(self) -> list[Cue]:
        """The cues on air at the current clock (latest, verified version where the story lane upgraded one)."""
        on_air = []
        for c in self.cues:
            if c.t_in <= self.clock_t <= c.t_out:
                upgraded = self.producer.by_moment.get(c.moment_id) if c.moment_id else None
                on_air.append(upgraded if upgraded is not None and upgraded.id == c.id else c)
        return [self.producer.score_bug(self.clock_t, []), *on_air]

    def languages(self) -> list[str]:
        langs = {"en"} | {v.profile.language for v in self.viewers.values() if v.profile.language in LANGS}
        return sorted(langs)

    def hello(self, v: Viewer) -> dict[str, Any]:
        return {"type": "hello", "viewer": v.id, "match": self.res.info.model_dump(), "profile": v.profile.model_dump(),
                "snapshot": self.state.snapshot(), "moments": [self._moment_summary(m) for m in self.moments[-40:]],
                "control": self.control_state(), "frame": self.state.last_frame or self.res.frame(0), "llm": self.llm_info()}

    def broadcast(self, msg: dict[str, Any], ops_only: bool = False) -> None:
        for v in self.viewers.values():
            if not ops_only or v.ops:
                v.send(msg)

    def _on_span(self, span: Span) -> None:
        self.broadcast({"type": "span", "span": span.as_dict()}, ops_only=True)

    # ------------------------------------------------------------------ control
    def control_state(self) -> dict[str, Any]:
        return {"playing": self.playing, "speed": self.speed, "clock": self.state.clock, "t": round(self.clock_t, 1),
                "t_end": float(self.res.frame_t[-1]), "params": self.params, "mode": self.mode,
                "chaos_expires_in_s": round(max(0.0, self._chaos_until - time.monotonic()), 0) if self._chaos_until else 0,
                "chaos": {"fail_rate": self.telemetry.chaos_fail_rate, "latency_ms": self.telemetry.chaos_latency_ms},
                "breaker": self.rt.breaker.as_dict(), "bus": self.bus.name, "paused_for_empty_room": self._empty_paused}

    def llm_info(self) -> dict[str, Any]:
        return {"provider": self.cfg.provider, "model": self.rt.model_name, "offline": self.cfg.is_offline}

    async def control(self, action: str, value: Any = None) -> dict[str, Any]:
        if self.mode == "live" and action in {"play", "pause", "speed", "seek", "restart", "load"}:
            return self.control_state()  # the provider drives the clock in live mode
        if action == "play":
            self.playing = True
            self._paused_at = None
            self._empty_paused = False
        elif action == "pause":
            self.playing = False
            self._paused_at = time.monotonic()
        elif action == "speed":
            self.speed = float(max(0.5, min(60.0, float(value))))
        elif action == "seek":
            self.seek(float(value))
        elif action == "restart":
            self._reset_pipeline()
            self.broadcast({"type": "reset", "snapshot": self.state.snapshot(), "moments": []})
        elif action == "load":
            self.playing = False
            self.load(value.get("home", "NOR"), value.get("away", "CAL"), int(value.get("seed", 7)),
                      value.get("scenario", "derby"))
            for v in self.viewers.values():
                v.send(self.hello(v))
        elif action == "chaos":
            self.telemetry.chaos_fail_rate = float(max(0.0, min(1.0, value.get("fail_rate", 0.0))))
            self.telemetry.chaos_latency_ms = float(max(0.0, min(8000.0, value.get("latency_ms", 0.0))))
            active = self.telemetry.chaos_fail_rate > 0 or self.telemetry.chaos_latency_ms > 0
            self._chaos_until = time.monotonic() + 90.0 if active else 0.0  # fault injection always switches itself off
        self.broadcast({"type": "control", "control": self.control_state()})
        return self.control_state()

    def seek(self, minute: float) -> None:
        target = self._t_for_minute(minute)
        if target < self.clock_t:
            self._reset_pipeline()
        self.advance(target - self.clock_t, live=False)
        self.broadcast({"type": "reset", "snapshot": self.state.snapshot(),
                        "moments": [self._moment_summary(m) for m in self.moments[-40:]], "frame": self.state.last_frame})
        self.broadcast({"type": "cue", "cue": self.producer.score_bug(self.clock_t, []).model_dump()})

    def _t_for_minute(self, minute: float) -> float:
        p2 = next((e.t for e in self.events if e.type == "second_half"), None)
        if minute <= 45 or p2 is None:
            return minute * 60
        return p2 + (minute - 45) * 60

    # ------------------------------------------------------------------ the loop
    async def _ticker(self) -> None:
        last = time.perf_counter()
        while True:
            await asyncio.sleep(0.1)
            now = time.perf_counter()
            dt, last = now - last, now
            if self.playing and self.mode == "replay":
                try:
                    self.advance(dt * self.speed, live=True)
                except Exception:  # noqa: BLE001
                    log.exception("pipeline tick failed")
            await self._housekeeping()
            if now - self._last_state_push > 1.0:
                self._last_state_push = now
                self.broadcast({"type": "state", "snapshot": self.state.snapshot(), "control": self.control_state()})
                self.broadcast({"type": "ops", "telemetry": self.telemetry.summary(), "breaker": self.rt.breaker.as_dict(),
                                "queue": self.queue.qsize(), "bus": {"name": self.bus.name, "published": self.bus.published},
                                "directors": {v.id: v.director.stats() for v in self.viewers.values()}}, ops_only=True)

    async def _housekeeping(self) -> None:
        mono = time.monotonic()
        if self._chaos_until and mono > self._chaos_until:
            await self.control("chaos", {"fail_rate": 0.0, "latency_ms": 0.0})
        if self.autoplay and self.mode == "live" and mono - self._last_ingest > self.live_idle_s:
            self.stop_live()  # an abandoned live feed must not park the public demo
            await self.control("play")
        if self.autoplay and self.mode == "replay":
            if self.viewers:
                self._unwatched_since = None
            elif self._unwatched_since is None:
                self._unwatched_since = mono
            empty = self._unwatched_since is not None and mono - self._unwatched_since > self.empty_pause_s
            if empty and self.params != DEMO:
                # a visitor's custom match (Data lab) must not greet the next judge: an empty room returns to the demo
                self.load(**DEMO)
                self.playing, self._paused_at, self._empty_paused = False, None, True
            elif self.playing and empty:
                # nobody is watching: an always-on replica idles instead of spending model calls on an empty room
                await self.control("pause")
                self._paused_at, self._empty_paused = None, True
            elif not self.playing and self.viewers:
                ended = self._ended_at is not None and mono - self._ended_at > 45
                idle = self._paused_at is not None and mono - self._paused_at > 300
                if ended or idle or self._empty_paused:  # loop after full time, resume abandoned or empty-room pauses
                    if ended:
                        await self.control("restart")
                        self._ended_at = None
                    await self.control("play")
        for key, v in list(self.virtual.items()):
            if mono - v.last_access > 600:
                self.virtual.pop(key, None)
                self.viewers.pop(v.id, None)

    def advance(self, dt: float, live: bool = True) -> None:
        ft = self.res.frame_t
        n = len(ft)
        target = self.clock_t + dt
        if self.fi < n and float(ft[self.fi]) > target + 3.0:  # half-time break in the feed: jump it
            target = float(ft[self.fi])
        batch: list[dict[str, Any]] = []
        while self.fi < n and float(ft[self.fi]) <= target:
            frame = self.res.frame(self.fi)
            t = frame["t"]
            self._process_frame(frame, live)
            while self.ei < len(self.events) and self.events[self.ei].qualifiers.get("t_end", self.events[self.ei].t) <= t:
                self._on_event(self.events[self.ei], live)
                self.ei += 1
            batch.append(frame)
            self.fi += 1
        if self.fi >= n:
            while self.ei < len(self.events):
                self._on_event(self.events[self.ei], live)
                self.ei += 1
            if self.playing:
                self._ended_at = time.monotonic()
            self.playing = False
        self.clock_t = target
        self._after_batch(batch, live)

    def _process_frame(self, frame: dict[str, Any], live: bool) -> None:
        t = frame["t"]
        for sig in self.state.on_frame(frame):
            for m in self.detector.on_signal(sig, t, self.state.clock):
                self._on_moment(m, live)

    def _after_batch(self, batch: list[dict[str, Any]], live: bool) -> None:
        if live and batch:
            self.broadcast({"type": "frames", "frames": batch[-12:]})
            for v in self.viewers.values():
                focus = v.director.player_focus(self.clock_t)
                if focus:
                    v.send({"type": "cue", "cue": focus.model_dump()})
        if live and self.state.momentum_series and int(self.clock_t) % 20 == 0:
            self._distribute([self.producer.momentum(self.clock_t)], live)

    # ------------------------------------------------------------------ live feeds from real providers
    def start_live(self, info: Any) -> dict[str, Any]:
        """Switch from the demo replay to a feed pushed by an external provider (POST /api/feed)."""
        self.mode = "live"
        self.playing = False
        self.params = {"live": True, "match_id": info.match_id, "home": info.home.id, "away": info.away.id}
        self.res = LiveRecording(info)
        self.events = []
        self._last_ingest = time.monotonic()
        self._reset_pipeline()
        for v in self.viewers.values():
            v.send(self.hello(v))
        return self.control_state()

    def ingest(self, frames: list[dict[str, Any]], events: list[Any]) -> dict[str, Any]:
        if self.mode != "live":
            raise RuntimeError("call /api/feed/start first")
        rec = self.res
        self._last_ingest = time.monotonic()
        before = len(self.moments)
        accepted = 0
        queued = {e.id for e in self._pending_events}
        for ev in events:
            if ev.id in self.state.events or ev.id in queued:
                continue  # idempotent: providers may resend
            queued.add(ev.id)
            rec.events.append(ev)
            self._pending_events.append(ev)
            accepted += 1
        self._pending_events.sort(key=_event_order)
        # Same order as replay, whatever the batch size: each frame, then the events it completes.
        # Late events (ending at or before the newest frame already processed) apply on arrival.
        self._apply_events_until(rec.frames[-1]["t"] if rec.frames else float("-inf"))
        batch = []
        for f in sorted(frames, key=lambda f: f["t"]):
            if rec.frames and f["t"] <= rec.frames[-1]["t"]:
                continue  # duplicate or late frame
            rec.frames.append(f)
            self.clock_t = f["t"]
            self._process_frame(f, True)
            self._apply_events_until(f["t"])
            batch.append(f)
        if not frames or any(e.type.value == "full_time" for e in self._pending_events):
            self._apply_events_until(float("inf"))  # event-only feeds and the final whistle don't wait for tracking
        self._after_batch(batch, True)
        return {"accepted_frames": len(batch), "accepted_events": accepted, "clock": self.state.clock,
                "score": dict(self.state.score), "new_moments": [m.headline for m in self.moments[before:]]}

    def _apply_events_until(self, t: float) -> None:
        while self._pending_events and _event_order(self._pending_events[0])[0] <= t:
            self._on_event(self._pending_events.pop(0), True)

    def stop_live(self) -> dict[str, Any]:
        self.mode = "replay"
        self.load(**DEMO)
        for v in self.viewers.values():
            v.send(self.hello(v))
        return self.control_state()

    def onair(self, profile: FanProfile) -> dict[str, Any]:
        """What a viewer with this profile would see right now, as plain JSON for production tools."""
        key = profile_key(profile)
        v = self.virtual.get(key)
        if v is None:
            v = CaptureViewer(profile, Director(profile, self.state, self.names))
            self.virtual[key] = v
            self.viewers[v.id] = v  # type: ignore[assignment]
        v.last_access = time.monotonic()
        return onair_payload(v, self.clock_t, self.state.snapshot(), self.res.info)

    def _on_event(self, ev: Any, live: bool) -> None:
        if live:
            asyncio.get_running_loop().create_task(self.bus.publish("event", ev.model_dump(mode="json")))
        en = self.state.on_event(ev)
        moments = self.detector.on_enriched(en)
        self._distribute(self.producer.from_event(en), live)
        if live and en.event.type.value in {"goal", "shot", "card", "substitution", "half_time", "full_time", "second_half"}:
            self.broadcast({"type": "event", "event": ev.model_dump(mode="json"), "data": _slim(en.data)})
        for m in moments:
            self._on_moment(m, live)

    def _on_moment(self, m: Moment, live: bool) -> None:
        if m.kind == "half_time":
            self._ht_base = recap_payload(self.state, list(self.moments), self.names_dict, "en", "casual", "half_time")
        i18n = {lang: {p: narrate(m.as_dict(), self.names, lang, p, self.state.home, self.state.away) for p in PERSONAS}
                for lang in LANGS}
        prov = Provenance(agent="Producer", model="deterministic-templates", verified=True)
        cue = self.producer.from_moment(m, i18n, prov)
        if cue is not None:
            self._distribute([cue], live)
        if not live:
            return
        self.broadcast({"type": "moment", "moment": self._moment_summary(m)})
        if self.webhooks.wants(m):
            info = self.res.info
            msg = self.webhooks.message(m, self.names, self.state.home, self.state.away, f"{info.home.name} v {info.away.name}")
            asyncio.get_running_loop().create_task(self.webhooks.post(msg))
        if m.lane == "story" and m.kind not in {"half_time", "full_time"}:
            self.queue.put_nowait((self._gen, m, self._context()))  # context frozen at the moment, not at dequeue
        if m.kind in {"half_time", "full_time"}:
            for lang in self.languages():
                asyncio.get_running_loop().create_task(self.recap(lang, "casual", m.kind))

    def _distribute(self, cues: list[Cue], live: bool) -> None:
        for cue in cues:
            if cue.kind.value not in {"score_bug", "momentum"}:
                self.cues.append(cue)
            if not live:
                continue
            for v in self.viewers.values():
                out = v.director.decide(cue)
                if out is not None:
                    v.send({"type": "cue", "cue": out.model_dump()})

    def _moment_summary(self, m: Moment) -> dict[str, Any]:
        d = m.as_dict()
        d["copy"] = {lang: narrate(d, self.names, lang, "casual", self.state.home, self.state.away) for lang in ("en",)}
        d["story"] = self.story.get(m.id)
        return d

    # ------------------------------------------------------------------ story lane
    async def _story_worker(self) -> None:
        while True:
            gen, m, ctx = await self.queue.get()
            try:
                await self._run_story(m, gen, ctx)
            except Exception:  # noqa: BLE001
                log.exception("story job failed for %s", m.id)

    async def _run_story(self, m: Moment, gen: int | None = None, ctx: dict[str, Any] | None = None) -> None:
        gen = self._gen if gen is None else gen
        if gen != self._gen:
            return  # queued before a seek, restart or new match
        t0 = time.perf_counter()
        job = StoryJob(moment=m.as_dict(), context=ctx or self._context(), languages=self.languages(), names=self.names_dict,
                       roster_names=self.roster_names, home=self.state.home, away=self.state.away,
                       shirts={pid: p.info.number for pid, p in self.state.players.items()})
        job = await run_story(self.rt, job)
        if gen != self._gen:
            log.info("discarded story for %s: the timeline changed while it was being written", m.id)
            return
        latency = (time.perf_counter() - t0) * 1000
        i18n = {lang: {p: narrate(job.moment, self.names, lang, p, self.state.home, self.state.away) for p in PERSONAS}
                for lang in LANGS}
        i18n.update(job.narration)
        llm_langs = [lang for lang in job.narration if lang not in job.fallback_langs]
        prov = Provenance(
            agent="Narrator" if llm_langs and not self.cfg.is_offline else "Narrator(template)",
            model=job.models.get("Narrator", self.rt.model_name), verified=bool(job.verdict and job.verdict.get("ok")),
            fallback=bool(job.fallback_langs), latency_ms=round(latency, 1), attempts=job.attempts,
        )
        self.story[m.id] = {"job": job.id, "insight": job.insight, "verdict": job.verdict, "attempts": job.attempts,
                            "fallback_langs": job.fallback_langs, "latency_ms": round(latency, 1), "models": job.models,
                            "trace": job.trace, "narration": job.narration if job.verdict_ok else {}}  # never show unchecked copy
        self.broadcast({"type": "story", "moment_id": m.id, "story": self.story[m.id]})
        if not job.verdict_ok:
            return  # unverified copy never reaches air: the deterministic fast-lane cue stays up
        cue = self.producer.upgrade(m.id, i18n, prov, job.verdict or {}, job.trace)
        if cue is None:
            return
        for v in self.viewers.values():
            out = v.director.decide(cue)
            if out is not None:
                v.send({"type": "cue_update", "cue": out.model_dump()})

    def _context(self) -> dict[str, Any]:
        return match_context(self.state)

    # ------------------------------------------------------------------ recap & Q&A
    def _revision(self) -> tuple[Any, ...]:
        """What a report depends on: the timeline, the minute, the score, the moments so far and the manpower."""
        return (self._gen, self.state.clock, tuple(self.state.score.values()), len(self.moments),
                tuple(self.state.red_cards.values()))

    def _check_recap(self, data: dict[str, Any], payload: dict[str, Any], lang: str, persona: str
                     ) -> tuple[dict[str, Any], Any]:
        data = normalize_recap(data, payload, self.roster_names)
        fields, problems = recap_fields(data, payload, self.roster_names)
        allowed = {p["id"] for p in payload["top_players"]} | {pid for m in payload["moments"] for pid in m["players"]}
        verdict = verify_texts({lang: {persona: fields}}, recap_evidence(payload), allowed, self.roster_names)
        if problems:  # a figure-perfect report about the wrong player or a minute that never happened is not verified
            verdict.ok = False
            verdict.issues = problems + verdict.issues
        return data, verdict

    def _recap_period(self, period: str | None) -> str:
        # default to what is true now: full time, half time (only during the break) or a live report
        period = period or ("full_time" if self.state.status == "full_time" else
                            "half_time" if self.state.status == "half_time" else "live")
        if period == "half_time" and self._ht_base is None:
            period = "live"  # no half time yet: report the match so far instead of inventing one
        if period == "full_time" and self.state.status != "full_time":
            period = "live"
        return period

    def _recap_input(self, period: str, lang: str, persona: str) -> dict[str, Any]:
        if period == "half_time":
            payload = {**self._ht_base, "language": lang, "persona": persona}  # type: ignore[dict-item]
        else:
            payload = recap_payload(self.state, self.moments, self.names_dict, lang, persona, period)
        payload["live"] = period == "live"
        payload["match_id"] = self.res.info.match_id  # identity travels with the input, never re-read afterwards
        return payload

    def _snapshot_recap(self, lang: str, persona: str) -> dict[str, Any]:
        """The match as it stands right now, written deterministically: instant, so nothing can overtake it."""
        period = self._recap_period(None)
        payload = self._recap_input(period, lang, persona)
        data, verdict = self._check_recap(offline_recap(payload), payload, lang, persona)
        return {"period": period, "language": lang, "persona": persona,
                "source": "deterministic (the match changed while the model was writing)", "verdict": verdict.as_dict(),
                "recap": data, "ms": 0.0, "match_id": payload["match_id"],
                "as_of": {"clock": payload.get("clock"), "score": payload.get("score"), "phase": payload.get("phase")}}

    async def recap(self, lang: str, persona: str, period: str | None = None, _retry: bool = True) -> dict[str, Any]:
        period = self._recap_period(period)
        key = (period, lang, persona)
        if key in self.recaps and period != "live":
            return self.recaps[key]
        rev = self._revision()
        cached = self._live_recaps.get((lang, persona))
        if period == "live" and cached and cached[0] == rev:
            return cached[1]  # one model call per state of the match, however many viewers ask; a goal makes a new one
        payload = self._recap_input(period, lang, persona)
        gen = self._gen
        t0 = time.perf_counter()
        source = "deterministic"
        try:
            if self.cfg.is_offline:
                raise AgentFailure("offline")
            import json

            data = await self.rt.call(self.rt.recapper, "Recap", json.dumps(payload, ensure_ascii=False, default=str))
            shape = recap_shape_problems(data)
            if shape:  # validated before anything normalises it: a malformed reply is a failed call, not a crash
                raise AgentFailure(f"recap has the wrong shape: {shape[0]}")
            source = self.rt.model_name
        except AgentFailure:
            data = offline_recap(payload)
            self.telemetry.record(Span("Recap", "ok" if self.cfg.is_offline else "fallback",
                                       (time.perf_counter() - t0) * 1000, "deterministic", detail=f"{period}/{lang}/{persona}"))
        data, verdict = self._check_recap(data, payload, lang, persona)
        if not verdict.ok and source != "deterministic":
            data, verdict = self._check_recap(offline_recap(payload), payload, lang, persona)
            source = "deterministic (verifier rejected model recap)"
        out = {"period": period, "language": lang, "persona": persona, "source": source, "verdict": verdict.as_dict(),
               "recap": data, "ms": round((time.perf_counter() - t0) * 1000, 1),
               "match_id": payload["match_id"],
               "as_of": {"clock": payload.get("clock"), "score": payload.get("score"), "phase": payload.get("phase")}}
        if gen != self._gen or (period == "live" and self._revision() != rev):
            # the match moved on while the model wrote (a seek, a new match, a goal): never cache, broadcast or hand
            # back the old report as current - write it again for the match as it stands now
            if _retry:
                return await self.recap(lang, persona, None if period == "live" else period, _retry=False)
            return self._snapshot_recap(lang, persona)  # moved again: the current match, never another match's report
        if period == "live":
            self._live_recaps[(lang, persona)] = (rev, out)
        if period != "live":
            self.recaps[key] = out
            self.broadcast({"type": "recap", "recap": out})
        return out

    async def ask(self, question: str, language: str, persona: str) -> dict[str, Any]:
        return await self.pundit.ask(question, language, persona)


def _slim(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if not k.endswith("_factors")}
