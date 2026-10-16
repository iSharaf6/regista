"""Live mode: an external provider pushes the feed, and production tools poll what is on air.

`LiveRecording` stands in for a simulated match while a data provider streams events and tracking frames into
`POST /api/feed`; the pipeline downstream is identical. `CaptureViewer` is a server-side viewer whose Director
output is kept as "currently on air", so tools like vMix, CasparCG or OBS data sources can poll
`GET /api/onair` and drive their own title templates without running our web app.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..agents.director import Director
from ..schema.events import MatchEvent, MatchInfo
from ..schema.profiles import FanProfile

# minimum wall-clock seconds a graphic stays "on air", so a 1-2 s polling interval never misses it
MIN_WALL = {"lower_third": 7.0, "side_panel": 8.0, "upper_right": 5.0, "ticker": 5.0, "follow": 2.5}
SLOT_ORDER = ["lower_third", "side_panel", "upper_right", "ticker", "follow", "upper_left"]


class LiveRecording:
    """Same surface as SimResult (info, events, frame_t, frame()), filled as the provider pushes data."""

    def __init__(self, info: MatchInfo):
        self.info = info
        self.events: list[MatchEvent] = []
        self.frames: list[dict[str, Any]] = []
        self.truth: list[dict[str, Any]] = []

    @property
    def frame_t(self) -> list[float]:
        return [f["t"] for f in self.frames] or [0.0]

    def frame(self, k: int) -> dict[str, Any]:
        if self.frames:
            return self.frames[min(k, len(self.frames) - 1)]
        return {"t": 0.0, "b": [52.5, 34.0, 0.0], "p": [None] * len(self.info.roster)}


@dataclass
class CaptureViewer:
    """A viewer with no socket: keeps the Director's decisions as the current on-air graphics."""

    profile: FanProfile
    director: Director
    ops: bool = False
    id: str = field(default_factory=lambda: "onair-" + uuid.uuid4().hex[:6])
    on_air: dict[str, tuple[float, dict[str, Any]]] = field(default_factory=dict)
    last_access: float = field(default_factory=time.monotonic)

    def send(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        if kind in {"cue", "cue_update"}:
            cue = msg["cue"]
            first_seen = self.on_air.get(cue["id"], (time.monotonic(), {}))[0]
            self.on_air[cue["id"]] = (first_seen, cue)
        elif kind in {"hello", "reset"}:
            self.on_air.clear()

    def active(self, clock: float) -> list[dict[str, Any]]:
        now = time.monotonic()
        live = []
        for cue_id, (seen, cue) in list(self.on_air.items()):
            persistent = cue["kind"] in {"score_bug", "momentum"}
            in_window = cue["t_in"] <= clock + 0.6 and clock <= cue["t_out"]
            held = now - seen < MIN_WALL.get(cue["slot"], 3.0)
            if persistent or in_window or held:
                live.append(cue)
            elif now - seen > 60:
                del self.on_air[cue_id]
        return live


def profile_key(p: FanProfile) -> str:
    return f"{p.mode.value}|{p.language}|{p.favorite_team}|{p.favorite_player}|{p.focus_metric}"


def onair_payload(viewer: CaptureViewer, clock_t: float, snapshot: dict[str, Any], info: MatchInfo) -> dict[str, Any]:
    cues = [c for c in viewer.active(clock_t) if c["kind"] not in {"score_bug", "momentum"}]
    cues.sort(key=lambda c: (SLOT_ORDER.index(c["slot"]) if c["slot"] in SLOT_ORDER else 9, -c["priority"]))
    items = [{
        "slot": c["slot"], "kind": c["kind"], "moment": c["payload"].get("moment_kind"), "title": c["title"], "body": c["body"],
        "explainer": c["payload"].get("explainer", ""), "team": c["payload"].get("team"), "player": c.get("follow"),
        "priority": c["priority"], "verified": c["provenance"]["verified"], "agent": c["provenance"]["agent"],
        "evidence": c["evidence"], "until_clock_s": c["t_out"], "rtl": c["payload"].get("rtl", False),
    } for c in cues]

    def first(slot: str) -> dict[str, Any]:
        return next((i for i in items if i["slot"] == slot), {})

    score = snapshot["score"]
    wp = snapshot["win_probability"]
    lower, card, side, ticker = first("lower_third"), first("upper_right"), first("side_panel"), first("ticker")
    return {
        "match": f"{info.home.name} v {info.away.name}",
        "clock": snapshot["clock"],
        "status": snapshot["status"],
        "score": f"{score[info.home.id]}-{score[info.away.id]}",
        "home": info.home.abbr,
        "away": info.away.abbr,
        "win_probability": wp,
        "on_air": items,
        # one flat row: vMix Data Sources / CasparCG templates can bind these fields directly
        "flat": {
            "home": info.home.abbr, "away": info.away.abbr, "home_score": score[info.home.id], "away_score": score[info.away.id],
            "clock": snapshot["clock"], "home_win_pct": round(100 * wp["home"]), "draw_pct": round(100 * wp["draw"]),
            "away_win_pct": round(100 * wp["away"]),
            "lower_title": lower.get("title", ""), "lower_body": lower.get("body", ""), "lower_explainer": lower.get("explainer", ""),
            "card_title": card.get("title", ""), "card_body": card.get("body", ""),
            "side_title": side.get("title", ""), "side_body": side.get("body", ""),
            "ticker": ticker.get("body", "") or ticker.get("title", ""),
        },
    }
