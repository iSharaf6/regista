"""The Producer: turns intelligence into timed Graphics Cue Protocol cues.

Fast-lane cues (shot cards, player tags, speed flashes, pass cards, score
bug, momentum) are built deterministically within milliseconds of the event.
Story-lane cues first appear with grounded template copy and are upgraded
in place (same cue id) when the agent-written, verified copy arrives.
"""

from __future__ import annotations

from typing import Any

from ..intel.moments import Moment
from ..intel.state import Enriched, MatchState
from ..schema.cues import Cue, CueKind, CueSlot, Provenance
from ..schema.events import EventType

PLAN: dict[str, tuple[CueKind, CueSlot, float, int]] = {
    # moment kind -> (cue kind, slot, seconds on screen, priority)
    "goal": (CueKind.MOMENT, CueSlot.LOWER_THIRD, 14.0, 95),
    "red_card": (CueKind.MOMENT, CueSlot.LOWER_THIRD, 12.0, 88),
    "big_chance": (CueKind.SHOT_CARD, CueSlot.UPPER_RIGHT, 8.0, 70),
    "thunderbolt": (CueKind.SHOT_CARD, CueSlot.UPPER_RIGHT, 7.0, 62),
    "master_pass": (CueKind.PASS_CARD, CueSlot.UPPER_RIGHT, 7.0, 52),
    "speed": (CueKind.SPEED_FLASH, CueSlot.FOLLOW, 4.5, 46),
    "milestone": (CueKind.MILESTONE, CueSlot.TICKER, 6.0, 30),
    "press_shift": (CueKind.TACTICAL, CueSlot.SIDE_PANEL, 18.0, 68),
    "control_chaos": (CueKind.TACTICAL, CueSlot.SIDE_PANEL, 14.0, 56),
    "rhythm": (CueKind.TACTICAL, CueSlot.SIDE_PANEL, 12.0, 50),
    "momentum_swing": (CueKind.TACTICAL, CueSlot.SIDE_PANEL, 12.0, 58),
    "half_time": (CueKind.RECAP, CueSlot.SIDE_PANEL, 40.0, 97),
    "full_time": (CueKind.RECAP, CueSlot.SIDE_PANEL, 120.0, 99),
}


class Producer:
    def __init__(self, state: MatchState):
        self.st = state
        self.n = 0
        self.by_moment: dict[str, Cue] = {}
        self._last_tag: dict[str, float] = {}

    def _id(self) -> str:
        self.n += 1
        return f"c{self.n:05d}"

    def _team_colors(self, tid: str | None) -> dict[str, str]:
        info = self.st.info.home if tid == self.st.home else self.st.info.away
        return {"primary": info.primary, "secondary": info.secondary} if tid else {}

    # ------------------------------------------------------------------ fast lane
    def from_event(self, en: Enriched) -> list[Cue]:
        ev, d = en.event, en.data
        out: list[Cue] = []
        if ev.type == EventType.SHOT and d:
            t = ev.qualifiers.get("t_end", ev.t)
            out.append(Cue(
                id=self._id(), match_id=ev.match_id, kind=CueKind.SHOT_CARD, slot=CueSlot.UPPER_RIGHT, t_in=t, t_out=t + 6.0,
                priority=48, title=self.st.player_name(ev.player), body="",
                payload={"player": ev.player, "team": ev.team, "players": [ev.player], "xg": d["xg"], "outcome": ev.outcome,
                         "shot_speed_kmh": d["shot_speed_kmh"], "distance_m": d["distance_m"], "body_part": d["body_part"],
                         "xg_factors": d["xg_factors"], "colors": self._team_colors(ev.team)},
                evidence=[ev.id], provenance=Provenance(agent="Producer", verified=True),
            ))
            out.append(self._tag(ev.player, ev.team, t - 1.5, 4.0, [ev.id]))
        elif ev.type == EventType.GOAL:
            out.append(self.score_bug(ev.t, [ev.id]))
            out.append(self._tag(ev.player, ev.team, ev.t, 6.0, [ev.id], priority=70))
        elif ev.type in {EventType.KICK_OFF, EventType.SECOND_HALF, EventType.FULL_TIME, EventType.HALF_TIME}:
            out.append(self.score_bug(ev.t, [ev.id]))
        elif ev.type == EventType.PASS and d.get("complete") and d.get("difficulty", 0) >= 55 and d.get("forward_m", 0) >= 8:
            t = ev.qualifiers.get("t_end", ev.t)
            out.append(Cue(
                id=self._id(), match_id=ev.match_id, kind=CueKind.PASS_CARD, slot=CueSlot.UPPER_RIGHT, t_in=t, t_out=t + 6.0,
                priority=42, title=f"{self.st.players[ev.player].info.short_name} → {self.st.player_name(ev.receiver).split()[-1]}",
                payload={"team": ev.team, "players": [ev.player, ev.receiver], "colors": self._team_colors(ev.team),
                         "facts": {"difficulty": d["difficulty"], "length_m": d["length_m"], "opponents_bypassed": d["opponents_bypassed"],
                                   "ball_speed_kmh": d["ball_speed_kmh"], "passer_accuracy": d["passer_accuracy"],
                                   "difficulty_factors": d["difficulty_factors"]}},
                evidence=[ev.id], provenance=Provenance(agent="Producer", verified=True),
            ))
        if ev.type in {EventType.PASS, EventType.CARRY, EventType.DRIBBLE} and ev.player:
            last = self._last_tag.get(ev.player, -99.0)
            if ev.t - last >= 10.0:
                self._last_tag[ev.player] = ev.t
                out.append(self._tag(ev.player, ev.team, ev.t, 3.0, [ev.id], priority=36))
        return out

    def _tag(self, pid: str | None, team: str | None, t: float, dur: float, evidence: list[str], priority: int = 32) -> Cue:
        p = self.st.players.get(pid or "")
        payload: dict[str, Any] = {"player": pid, "team": team, "players": [pid] if pid else []}
        if p:
            payload |= {"name": p.info.name, "short_name": p.info.short_name, "number": p.info.number,
                        "speed_kmh": round(p.speed, 1), "distance_km": round(p.distance_m / 1000, 2),
                        "colors": self._team_colors(team),
                        # threshold-triggered indicators (sprint band, distance milestones)
                        "show_speed": p.speed >= 25.2, "show_distance": p.distance_m >= 9000}
        return Cue(id=self._id(), match_id=self.st.info.match_id, kind=CueKind.PLAYER_TAG, slot=CueSlot.FOLLOW, t_in=t,
                   t_out=t + dur, priority=priority, title=p.info.short_name if p else "", follow=pid, payload=payload,
                   evidence=evidence, provenance=Provenance(agent="Producer", verified=True))

    def score_bug(self, t: float, evidence: list[str]) -> Cue:
        st = self.st
        return Cue(
            id="score-bug", match_id=st.info.match_id, kind=CueKind.SCORE_BUG, slot=CueSlot.UPPER_LEFT, t_in=t, t_out=t + 1e7,
            priority=100, title=f"{st.info.home.abbr} {st.score[st.home]}-{st.score[st.away]} {st.info.away.abbr}",
            payload={"score": dict(st.score), "clock": st.clock, "status": st.status,
                     "home": {"id": st.home, "abbr": st.info.home.abbr, **self._team_colors(st.home)},
                     "away": {"id": st.away, "abbr": st.info.away.abbr, **self._team_colors(st.away)}},
            evidence=evidence, provenance=Provenance(agent="Producer", verified=True),
        )

    def momentum(self, t: float) -> Cue:
        st = self.st
        return Cue(
            id="momentum", match_id=st.info.match_id, kind=CueKind.MOMENTUM, slot=CueSlot.UPPER_LEFT, t_in=t, t_out=t + 1e7,
            priority=20, payload={"value": st.momentum, "series": st.momentum_series[-30:],
                                  "win_probability": {"home": st.wp[0], "draw": st.wp[1], "away": st.wp[2]}},
            provenance=Provenance(agent="Producer", verified=True),
        )

    # ------------------------------------------------------------------ moments
    def from_moment(self, m: Moment, i18n: dict[str, Any], provenance: Provenance) -> Cue | None:
        plan = PLAN.get(m.kind)
        if not plan:
            return None
        kind, slot, dur, prio = plan
        payload: dict[str, Any] = {"moment_kind": m.kind, "team": m.team, "players": m.players, "facts": m.facts,
                                   "why": m.why, "i18n": i18n, "lane": m.lane, "colors": self._team_colors(m.team)}
        cue = Cue(
            id=self._id(), match_id=self.st.info.match_id, kind=kind, slot=slot, t_in=m.t, t_out=m.t + dur, priority=prio,
            title=m.headline, body="", payload=payload, evidence=m.evidence, moment_id=m.id,
            follow=m.players[0] if slot == CueSlot.FOLLOW and m.players else None, provenance=provenance,
        )
        self.by_moment[m.id] = cue
        return cue

    def upgrade(self, moment_id: str, i18n: dict[str, Any], provenance: Provenance, verdict: dict[str, Any],
                trace: list[dict[str, Any]]) -> Cue | None:
        """Replace a provisional cue's copy with agent-written, verified copy (same id, same timing)."""
        base = self.by_moment.get(moment_id)
        if base is None:
            return None
        cue = base.model_copy(deep=True)
        cue.payload["i18n"] = i18n
        cue.payload["verdict"] = verdict
        cue.payload["trace"] = trace
        cue.provenance = provenance
        self.by_moment[moment_id] = cue
        return cue
