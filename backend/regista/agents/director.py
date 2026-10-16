"""The Director: one match feed, a different broadcast for every fan.

For each connected viewer the Director scores every candidate cue against
their profile (mode, favourite club and player, focus metric), enforces a
cue budget and screen-slot scheduling so overlays never collide, then picks
the copy in their language and voice - including partisan captions for
goals ("GET IN!" vs "Port Calder score").
"""

from __future__ import annotations

from collections import deque
from typing import Any

from ..intel.state import MatchState
from ..schema.cues import Cue, CueKind, CueSlot, Provenance
from ..schema.profiles import FanProfile, Mode
from .templates import Names, narrate

PERSONA = {Mode.CASUAL: "casual", Mode.ANALYST: "analyst", Mode.NEW_FAN: "new_fan", Mode.PLAYER_CAM: "casual"}
THRESHOLD = {Mode.CASUAL: 48, Mode.ANALYST: 34, Mode.NEW_FAN: 44, Mode.PLAYER_CAM: 40}
MODE_BIAS: dict[Mode, dict[CueKind, int]] = {
    Mode.CASUAL: {CueKind.MOMENT: 10, CueKind.SPEED_FLASH: 10, CueKind.MILESTONE: 12, CueKind.PASS_CARD: -14,
                  CueKind.TACTICAL: -8, CueKind.PLAYER_TAG: 8},
    Mode.ANALYST: {CueKind.TACTICAL: 18, CueKind.PASS_CARD: 16, CueKind.SHOT_CARD: 14, CueKind.SPEED_FLASH: -8},
    Mode.NEW_FAN: {CueKind.MOMENT: 12, CueKind.TACTICAL: 6, CueKind.PASS_CARD: -12, CueKind.SHOT_CARD: -6,
                   CueKind.PLAYER_TAG: 10},
    Mode.PLAYER_CAM: {CueKind.PASS_CARD: -10, CueKind.TACTICAL: -6},
}
FOCUS: dict[str, dict[CueKind, int]] = {
    "pass_difficulty": {CueKind.PASS_CARD: 28},
    "speed": {CueKind.SPEED_FLASH: 28, CueKind.SHOT_CARD: 10},
    "xg": {CueKind.SHOT_CARD: 26},
    "pressing": {CueKind.TACTICAL: 26},
    "distance": {CueKind.MILESTONE: 24, CueKind.PLAYER_TAG: 10},
}
PERSISTENT = {CueKind.SCORE_BUG, CueKind.MOMENTUM}


class Director:
    def __init__(self, profile: FanProfile, state: MatchState, names: Names):
        self.profile = profile
        self.st = state
        self.names = names
        self.slots: dict[str, tuple[str, float, int]] = {}
        self.recent: deque[float] = deque()
        self.shown_moments: dict[str, str] = {}
        self.last_focus_t = -999.0
        self.decisions = {"shown": 0, "filtered": 0, "rate_limited": 0, "slot_busy": 0}

    def update_profile(self, profile: FanProfile) -> None:
        self.profile = profile
        self.slots.clear()
        self.recent.clear()

    # ------------------------------------------------------------------ scoring
    def relevance(self, cue: Cue) -> tuple[int, list[str]]:
        p = self.profile
        score = cue.priority
        reasons = [f"base {cue.priority}"]
        players = cue.payload.get("players") or ([cue.follow] if cue.follow else [])
        if p.favorite_team and cue.payload.get("team") == p.favorite_team:
            score += 14
            reasons.append("your club +14")
        if p.favorite_player and p.favorite_player in players:
            bonus = 45 if p.mode == Mode.PLAYER_CAM else 28
            score += bonus
            reasons.append(f"your player +{bonus}")
        elif p.mode == Mode.PLAYER_CAM and cue.kind in {CueKind.PLAYER_TAG, CueKind.SPEED_FLASH, CueKind.PASS_CARD}:
            score -= 25
            reasons.append("other player -25")
        bias = MODE_BIAS.get(p.mode, {}).get(cue.kind, 0)
        if bias:
            score += bias
            reasons.append(f"{p.mode.value} {bias:+d}")
        focus = FOCUS.get(p.focus_metric, {}).get(cue.kind, 0)
        if focus:
            score += focus
            reasons.append(f"focus {p.focus_metric} +{focus}")
        return score, reasons

    # ------------------------------------------------------------------ decide
    def decide(self, cue: Cue) -> Cue | None:
        if cue.kind in PERSISTENT:
            return self._localize(cue, cue.priority, ["persistent"])
        if cue.moment_id and cue.moment_id in self.shown_moments and cue.id == self.shown_moments[cue.moment_id]:
            return self._localize(cue, cue.priority, ["upgrade"])  # verified copy replacing provisional copy
        score, reasons = self.relevance(cue)
        ambient = cue.slot == CueSlot.FOLLOW  # pinned tags: own threshold, outside the cue budget
        if score < (30 if ambient else THRESHOLD[self.profile.mode]):
            self.decisions["filtered"] += 1
            return None
        while self.recent and self.recent[0] < cue.t_in - 60:
            self.recent.popleft()
        if not ambient and score < 85 and len(self.recent) >= self.profile.max_cues_per_minute:
            self.decisions["rate_limited"] += 1
            return None
        slot_key = f"{cue.slot.value}:{cue.follow}" if cue.slot == CueSlot.FOLLOW else cue.slot.value
        busy = self.slots.get(slot_key)
        if busy and busy[1] > cue.t_in and cue.slot != CueSlot.TICKER:
            if score <= busy[2]:
                self.decisions["slot_busy"] += 1
                return None
            reasons.append(f"pre-empts {busy[0]}")
        self.slots[slot_key] = (cue.id, cue.t_out, score)
        if not ambient:
            self.recent.append(cue.t_in)
        if cue.moment_id:
            self.shown_moments[cue.moment_id] = cue.id
        self.decisions["shown"] += 1
        return self._localize(cue, score, reasons)

    def _localize(self, cue: Cue, score: int, reasons: list[str]) -> Cue:
        p = self.profile
        out = cue.model_copy(deep=True)
        out.audience = p.id
        out.locale = p.language
        out.payload["relevance"] = {"score": score, "reasons": reasons}
        out.payload["rtl"] = p.rtl
        i18n = out.payload.pop("i18n", None)
        if i18n:
            persona = PERSONA[p.mode]
            block = (i18n.get(p.language) or i18n.get("en") or {}).get(persona) or {}
            out.title = block.get("caption", out.title)
            out.body = block.get("line", "")
            out.payload["explainer"] = block.get("explainer", "")
            if out.payload.get("moment_kind") == "goal" and p.favorite_team in {self.st.home, self.st.away}:
                m = {"kind": "goal", "team": out.payload.get("team"), "players": out.payload.get("players", []),
                     "facts": out.payload.get("facts", {})}
                fan = narrate(m, self.names, p.language, persona, self.st.home, self.st.away, fan_team=p.favorite_team)
                out.title = fan["caption"]
                out.payload["partisan"] = "for" if p.favorite_team == out.payload.get("team") else "against"
            out.payload["languages_available"] = sorted(i18n)
        return out

    # ------------------------------------------------------------------ player cam
    def player_focus(self, t: float) -> Cue | None:
        pid = self.profile.favorite_player
        if self.profile.mode != Mode.PLAYER_CAM or not pid or pid not in self.st.players or t - self.last_focus_t < 45:
            return None
        self.last_focus_t = t
        view = self.st.player_view(pid)
        return Cue(id=f"focus-{pid}", match_id=self.st.info.match_id, kind=CueKind.PLAYER_FOCUS, slot=CueSlot.SIDE_PANEL,
                   t_in=t, t_out=t + 12, priority=70, title=view["name"], audience=self.profile.id,
                   locale=self.profile.language, follow=pid, payload={"player": view, "players": [pid], "team": view["team"],
                                                                      "rtl": self.profile.rtl},
                   provenance=Provenance(agent="Director", verified=True))

    def stats(self) -> dict[str, Any]:
        return {"profile": self.profile.model_dump(), **self.decisions}
