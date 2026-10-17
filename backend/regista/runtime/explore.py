"""Explore one moment: a curated replay of a demo-match moment, as three different fans see it, with its evidence.

Judges should not have to wait in the shared 90-minute broadcast for something to happen, so this replays the demo
match privately up to the chosen moment, runs the same story workflow on it (Analyst, Narrator and Localizers,
Verifier) and shows what Tom, Amira and Lucía would each get. It never touches the shared broadcast, and each moment is
computed once per process, so it costs at most one story job per moment.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..agents.config import LLMConfig
from ..schema.profiles import FanProfile, Mode
from .bus import InMemoryBus
from .session import MatchSession

FANS: list[tuple[str, str, FanProfile]] = [
    ("Tom", "analyst · English", FanProfile(id="tom", mode=Mode.ANALYST, language="en", focus_metric="pressing")),
    ("Amira", "Port Calder fan · Arabic", FanProfile(id="amira", mode=Mode.CASUAL, language="ar", favorite_team="CAL")),
    ("Lucía", "first match · Spanish", FanProfile(id="lucia", mode=Mode.NEW_FAN, language="es", favorite_team="NOR",
                                                   focus_metric="xg")),
]


class Explore:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.cache: dict[str, dict[str, Any]] = {}
        self.lock = asyncio.Lock()
        self._catalogue: list[dict[str, Any]] | None = None

    def _session(self) -> MatchSession:
        return MatchSession(self.cfg, story_workers=0, bus=InMemoryBus())  # private: never the shared broadcast

    def catalogue(self) -> list[dict[str, Any]]:
        """The demo match's story moments, in match order: what the page can explore."""
        if self._catalogue is None:
            s = self._session()
            s.advance(float(s.res.frame_t[-1]) - s.clock_t + 1, live=False)
            self._catalogue = [{"id": m.id, "kind": m.kind, "clock": m.clock, "headline": m.headline}
                               for m in s.moments if m.lane == "story" and m.kind not in {"half_time", "full_time"}]
        return self._catalogue

    async def get(self, moment_id: str | None = None) -> dict[str, Any] | None:
        cat = self.catalogue()
        if moment_id is None:
            moment_id = next((m["id"] for m in cat if m["kind"] == "goal"), cat[0]["id"] if cat else None)
        if moment_id not in {m["id"] for m in cat}:
            return None
        async with self.lock:  # one replay at a time; every later visit is served from the cache
            if moment_id not in self.cache:
                self.cache[moment_id] = await self._build(moment_id)
        return {**self.cache[moment_id], "moments": cat}

    async def _build(self, moment_id: str) -> dict[str, Any]:
        s = self._session()
        viewers = [s.connect(profile) for _, _, profile in FANS]  # so the story is written in their languages
        while s.fi < len(s.res.frame_t) and not any(m.id == moment_id for m in s.moments):
            s.advance(5.0, live=False)
        m = next(x for x in s.moments if x.id == moment_id)
        await s._run_story(m, s._gen, s._context())
        cue = s.producer.by_moment.get(m.id)
        fans = []
        for (name, label, profile), v in zip(FANS, viewers, strict=True):
            out, aired = v.director.preview(cue) if cue is not None else (None, False)
            fans.append({"name": name, "label": label, "profile": profile.model_dump(), "aired": aired,
                         "cue": out.model_dump() if out is not None else None})
        story = s.story.get(m.id) or {}
        return {"curated": True, "match": s.res.info.model_dump(), "moment": s._moment_summary(m), "fans": fans,
                "story": {k: story.get(k) for k in ("verdict", "attempts", "fallback_langs", "models", "trace", "insight",
                                                    "narration", "latency_ms")},
                "evidence": m.evidence,
                "note": "A curated replay of one moment from the demo match, run privately: the live broadcast is unaffected."}
