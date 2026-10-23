"""Explore one moment: a curated replay of a demo-match moment, as three different fans see it, with its evidence.

Judges should not have to wait in the shared 90-minute broadcast for something to happen, so this replays the demo
match privately up to the chosen moment, runs the same story workflow on it (Analyst, Narrator and Localizers,
Verifier) and shows what Tom, Amira and Lucía would each get. It never touches the shared broadcast, and each moment is
computed once per process, so it costs at most one story job per moment. The replay itself is CPU work, so it runs in a
worker thread (never with live=False side effects on the event loop) and the shared broadcast keeps streaming meanwhile.
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
    # Tom's same-language pair: the difference from Tom is the audience, not the language
    ("Sam", "first match · English", FanProfile(id="sam", mode=Mode.NEW_FAN, language="en")),
]

# Labelled recovery drills: a wrong goal count is planted in one language's draft(s) so the Verifier really rejects it.
# "ar": the first Arabic draft only (rewritten, then passes); "ar2": both drafts (Arabic ends on its template).
DRILLS = {f"{lang}{'2' if n == 2 else ''}": {"lang": lang, "drafts": n} for lang in ("ar", "es") for n in (1, 2)}


def cache_key(moment_id: str, drill: str | None) -> str:
    return f"{moment_id}|{drill}" if drill else moment_id


class Explore:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.cache: dict[str, dict[str, Any]] = {}
        self.lock = asyncio.Lock()
        self._catalogue: list[dict[str, Any]] | None = None

    def _session(self) -> MatchSession:
        return MatchSession(self.cfg, story_workers=0, bus=InMemoryBus())  # private: never the shared broadcast

    async def catalogue(self) -> list[dict[str, Any]]:
        """The demo match's story moments, in match order: what the page can explore."""
        if self._catalogue is None:
            s = self._session()
            await asyncio.to_thread(s.advance, float(s.res.frame_t[-1]) - s.clock_t + 1, live=False)
            self._catalogue = [{"id": m.id, "kind": m.kind, "clock": m.clock, "headline": m.headline}
                               for m in s.moments if m.lane == "story" and m.kind not in {"half_time", "full_time"}]
        return self._catalogue

    async def warm(self) -> None:
        """Replay the demo's goals before anyone asks, so the judges' fast path answers at once even after a cold start:
        the default moment first, then the late winner the submission links to, then the rest (a few story jobs)."""
        goals = [m["id"] for m in await self.catalogue() if m["kind"] == "goal"]
        for moment_id in dict.fromkeys(goals[:1] + goals[-1:] + goals[1:-1]):
            await self.get(moment_id)
        for drill in ("ar", "ar2"):  # the correction receipts the submission links to, on the late winner
            if goals:
                await self.get(goals[-1], drill)

    async def resolve(self, moment_id: str | None) -> str | None:
        """Stable entry links survive changes to the simulator's moment numbering."""
        cat = await self.catalogue()
        if moment_id == "highlight":
            return next((m["id"] for m in reversed(cat) if m["kind"] == "goal"), None)
        if moment_id is None:
            return next((m["id"] for m in cat if m["kind"] == "goal"), cat[0]["id"] if cat else None)
        return moment_id

    async def get(self, moment_id: str | None = None, drill: str | None = None) -> dict[str, Any] | None:
        cat = await self.catalogue()
        moment_id = await self.resolve(moment_id)
        if moment_id not in {m["id"] for m in cat} or (drill is not None and drill not in DRILLS):
            return None
        moment = next(m for m in cat if m["id"] == moment_id)
        if drill is not None and moment["kind"] != "goal":
            return None  # the drill plants a scorer's goal tally, which requires a goal
        key = cache_key(moment_id, drill)
        if key not in self.cache:
            async with self.lock:  # only cold builds wait; a warm judge link never queues behind another model call
                if key not in self.cache:
                    self.cache[key] = await self._build(moment_id, drill)
        return {**self.cache[key], "moments": cat, "drills": sorted(DRILLS) if moment["kind"] == "goal" else []}

    @staticmethod
    def _replay_to(s: MatchSession, moment_id: str) -> None:
        while s.fi < len(s.res.frame_t) and not any(m.id == moment_id for m in s.moments):
            s.advance(5.0, live=False)

    async def _build(self, moment_id: str, drill: str | None = None) -> dict[str, Any]:
        s = self._session()
        viewers = [s.connect(profile) for _, _, profile in FANS]  # so the story is written in their languages
        await asyncio.to_thread(self._replay_to, s, moment_id)
        m = next(x for x in s.moments if x.id == moment_id)
        await s._run_story(m, s._gen, s._context(), drill=DRILLS.get(drill or ""))
        cue = s.producer.by_moment.get(m.id)
        fans = []
        for (name, label, profile), v in zip(FANS, viewers, strict=True):
            out, aired = v.director.preview(cue) if cue is not None else (None, False)
            fans.append({"name": name, "label": label, "profile": profile.model_dump(), "aired": aired,
                         "cue": out.model_dump() if out is not None else None})
        story = s.story.get(m.id) or {}
        return {"curated": True, "match": s.res.info.model_dump(), "moment": s._moment_summary(m), "fans": fans,
                "story": {k: story.get(k) for k in ("verdict", "attempts", "fallback_langs", "models", "trace", "insight",
                                                    "narration", "latency_ms", "drafts")},
                "drill": None if drill is None else {
                    **DRILLS[drill], "name": drill,
                    "note": "Controlled drill: a wrong goal count was planted in this language's draft(s) to show targeted "
                            "recovery. Every other language and the rest of the run are untouched."},
                "evidence": m.evidence,
                "note": "A curated replay of one moment from the demo match, run privately: the live broadcast is unaffected."}
