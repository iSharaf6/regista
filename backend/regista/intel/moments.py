"""Key-moment detection.

Turns enriched events and windowed signals into Moments. A moment is a
structured, language-neutral fact pattern: what happened, the numbers, the
factors that explain why it matters, and the event ids that prove it. The
Explain stage narrates moments; it never invents them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..schema.events import EventType
from .signals import RegimeDetector, control_chaos, rhythm
from .state import Enriched, MatchState

STORY_THRESHOLD = 45


@dataclass
class Moment:
    """A detected moment. Its facts are either observed (counted or measured from events and tracking) or model
    estimates (xG, win probability, momentum, pass difficulty, press-shift statistics): fact_kinds says which, so a
    receipt can show the difference. Generated copy is the third layer, interpretation, and lives in the story lane."""

    id: str
    t: float
    clock: str
    kind: str
    team: str | None
    players: list[str]
    importance: int
    headline: str
    facts: dict[str, Any]
    why: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    @property
    def lane(self) -> str:
        return "story" if self.importance >= STORY_THRESHOLD else "fast"

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["lane"] = self.lane
        d["fact_kinds"] = {k: fact_kind(k) for k in self.facts}
        return d


ESTIMATES = ("xg", "wp", "momentum", "difficulty", "z_", "onset", "series", "label")


def fact_kind(key: str) -> str:
    """'model estimate' for figures a model produced, 'observed' for what the feed counted or measured."""
    k = key.lower()
    return "model estimate" if any(k.startswith(e) or f"_{e}" in k for e in ESTIMATES) else "observed"


class MomentDetector:
    def __init__(self, state: MatchState):
        self.state = state
        self.regimes = RegimeDetector()
        self._n = 0
        self._last_minute = -1
        self._cci_label = "balanced"
        self._cci_pending: tuple[str, int] = ("balanced", 0)
        self._cci_last_change = -99
        self._rhythm_label = "balanced"
        self._momentum_sign = 0
        self._momentum_peak: dict[int, tuple[int, float]] = {}
        self.moments: list[Moment] = []
        self.signals_log: list[dict[str, Any]] = []

    def _new(self, **kw: Any) -> Moment:
        self._n += 1
        m = Moment(id=f"m{self._n:03d}", **kw)
        self.moments.append(m)
        return m

    def _name(self, pid: str | None) -> str:
        return self.state.players[pid].info.short_name if pid and pid in self.state.players else ""

    def _team(self, tid: str | None) -> str:
        return self.state.short.get(tid or "", "")

    # ------------------------------------------------------------------ events
    def on_enriched(self, en: Enriched) -> list[Moment]:
        ev, d, st = en.event, en.data, self.state
        out: list[Moment] = []
        if ev.type == EventType.GOAL:
            shot = st.events.get(ev.related[0]) if ev.related else None
            shot_d = st.enriched.get(shot.id, {}) if shot else {}
            swing = abs(d["wp_swing"])
            xg = shot_d.get("xg") or 0.0
            why = [
                {"label": "Win probability swing", "value": round(100 * d["wp_swing"], 1), "unit": "pp",
                 "detail": f"{self._team(ev.team)} {100 * (d['wp_before'][0 if ev.team == st.home else 2]):.0f}% -> "
                           f"{100 * (d['wp_after'][0 if ev.team == st.home else 2]):.0f}%"},
                {"label": "Chance quality", "value": round(xg, 2), "unit": "xG",
                 "detail": "against the odds" if xg < 0.08 else ("a big chance taken" if xg >= 0.3 else "a half-chance")},
            ]
            if shot_d.get("xg_factors"):
                why.append({"label": "Shot factors", "value": None, "factors": shot_d["xg_factors"]})
            if d.get("assist_player"):
                why.append({"label": "Assist", "value": None, "detail": self._name(d["assist_player"])})
            ctx = self._score_context(ev.team)
            out.append(self._new(
                t=ev.t, clock=ev.clock, kind="goal", team=ev.team,
                players=[p for p in (ev.player, d.get("assist_player")) if p],
                importance=min(100, int(70 + 60 * swing)),
                headline=f"GOAL {self._team(ev.team)} - {self._name(ev.player)} ({d['score_text']})",
                facts={"score": d["score"], "score_text": d["score_text"], "xg": xg, "wp_before": d["wp_before"],
                       "wp_after": d["wp_after"], "wp_swing": d["wp_swing"], "shot_speed_kmh": shot_d.get("shot_speed_kmh"),
                       "distance_m": shot_d.get("distance_m"), "body_part": shot_d.get("body_part"),
                       "scorer": ev.player, "assist": d.get("assist_player"), "scorer_goals": d["scorer_goals"],
                       "context": ctx, "set_piece": shot_d.get("set_piece")},
                why=why, evidence=[ev.id] + ev.related,
            ))
        elif ev.type == EventType.SHOT and ev.outcome != "goal":
            xg = d["xg"]
            saved = ev.outcome == "saved"
            if xg >= 0.22 or (saved and d["shot_speed_kmh"] >= 105):
                kind = "big_chance" if xg >= 0.22 else "thunderbolt"
                keeper = None
                if saved:
                    nxt = [e for e in st.events.values() if e.type == EventType.SAVE and ev.id in e.related]
                    keeper = nxt[0].player if nxt else None
                out.append(self._new(
                    t=ev.t, clock=ev.clock, kind=kind, team=ev.team,
                    players=[p for p in (ev.player, keeper) if p],
                    importance=int(35 + 55 * xg),
                    headline=f"{'Big chance' if kind == 'big_chance' else 'Rocket'}: {self._name(ev.player)} "
                             f"({ev.outcome.replace('_', ' ')})",
                    facts={"xg": xg, "outcome": ev.outcome, "shot_speed_kmh": d["shot_speed_kmh"],
                           "distance_m": d["distance_m"], "keeper": keeper, "body_part": d["body_part"],
                           "team_xg": d["team_xg"], "team_goals": st.score[ev.team]},
                    why=[{"label": "Chance quality", "value": xg, "unit": "xG", "factors": d["xg_factors"]},
                         {"label": "Shot speed", "value": d["shot_speed_kmh"], "unit": "km/h"}],
                    evidence=[ev.id],
                ))
        elif ev.type == EventType.PASS and d.get("complete"):
            if (d["difficulty"] >= 72 and d["forward_m"] > 5) or d["opponents_bypassed"] >= 9:
                out.append(self._new(
                    t=ev.t, clock=ev.clock, kind="master_pass", team=ev.team,
                    players=[p for p in (ev.player, ev.receiver) if p],
                    importance=int(18 + d["difficulty"] / 4 + 2 * d["opponents_bypassed"]),
                    headline=f"Pass of quality: {self._name(ev.player)} to {self._name(ev.receiver)}",
                    facts={"difficulty": d["difficulty"], "length_m": d["length_m"],
                           "opponents_bypassed": d["opponents_bypassed"], "ball_speed_kmh": d["ball_speed_kmh"],
                           "passer_accuracy": d["passer_accuracy"], "passer_passes": d["passer_passes"]},
                    why=[{"label": "Difficulty", "value": d["difficulty"], "unit": "/100", "factors": d["difficulty_factors"]},
                         {"label": "Opponents bypassed", "value": d["opponents_bypassed"]}],
                    evidence=[ev.id],
                ))
        elif ev.type == EventType.CARD and ev.outcome in {"red", "second_yellow"}:
            out.append(self._new(
                t=ev.t, clock=ev.clock, kind="red_card", team=ev.team, players=[ev.player] if ev.player else [],
                importance=75, headline=f"Red card: {self._name(ev.player)} ({self._team(ev.team)})",
                facts={"wp_before": d.get("wp_before"), "wp_after": d.get("wp_after"), "reason": ev.outcome},
                why=[{"label": "Numerical disadvantage", "value": 10, "detail": "Scoring rate drops ~25% with ten men"}],
                evidence=[ev.id] + ev.related,
            ))
        elif ev.type in {EventType.HALF_TIME, EventType.FULL_TIME}:
            kind = "half_time" if ev.type == EventType.HALF_TIME else "full_time"
            snap = st.snapshot()
            out.append(self._new(
                t=ev.t, clock=ev.clock, kind=kind, team=None, players=[p["id"] for p in snap["top_players"][:3]],
                importance=80, headline=f"{kind.replace('_', ' ').title()}: {self._team(st.home)} "
                                        f"{st.score[st.home]}-{st.score[st.away]} {self._team(st.away)}",
                facts={"score": dict(st.score), "teams": snap["teams"], "top_players": snap["top_players"][:3],
                       "win_probability": snap["win_probability"]},
                evidence=[ev.id],
            ))
        for sig in en.signals:
            out.extend(self.on_signal(sig, ev.t, ev.clock))
        idx = st.match_minute()
        if idx > self._last_minute:
            for m in range(self._last_minute + 1, idx + 1):
                out.extend(self.on_minute(m, ev.t, ev.clock))
            self._last_minute = idx
        return out

    def _score_context(self, team: str) -> str:
        st = self.state
        mine, theirs = st.score[team], st.score[st.other(team)]
        if mine == theirs:
            return "equaliser"
        if mine == 1 and theirs == 0:
            return "opener"
        if mine == theirs + 1:
            return "go_ahead"
        if mine > theirs + 1:
            return "extends_lead"
        return "pulls_one_back"

    # ------------------------------------------------------------------ signals
    def on_signal(self, sig: dict[str, Any], t: float, clock: str) -> list[Moment]:
        self.signals_log.append(sig)
        st = self.state
        if sig["type"] == "speed_flash":
            pl = st.players[sig["player"]]
            return [self._new(
                t=sig["t"], clock=st.clock, kind="speed", team=sig["team"], players=[sig["player"]],
                importance=22, headline=f"{pl.info.short_name} clocks {sig['speed_kmh']:.1f} km/h",
                facts={"speed_kmh": sig["speed_kmh"], "top_speed_kmh": sig["top_speed_kmh"], "sprints": pl.sprints,
                       "distance_km": round(pl.distance_m / 1000, 2)},
                why=[{"label": "Threshold", "value": 33.0, "unit": "km/h", "detail": "Elite sprint band"}],
            )]
        if sig["type"] == "distance_milestone":
            pl = st.players[sig["player"]]
            return [self._new(
                t=sig["t"], clock=st.clock, kind="milestone", team=sig["team"], players=[sig["player"]],
                importance=18, headline=f"{pl.info.short_name} passes {sig['km']} km covered",
                facts={"distance_km": sig["km"], "sprints": pl.sprints, "top_speed_kmh": round(pl.top_speed, 1)},
            )]
        if sig["type"] == "milestone":
            pl = st.players[sig["player"]]
            return [self._new(
                t=t, clock=clock, kind="milestone", team=sig["team"], players=[sig["player"]],
                importance=16, headline=f"{pl.info.short_name}: {sig['label']} at {sig['accuracy']:.0f}%",
                facts={"label": sig["label"], "value": sig["value"], "accuracy": sig["accuracy"]},
            )]
        return []

    # ------------------------------------------------------------------ minute ticks
    def on_minute(self, minute: int, t: float, clock: str) -> list[Moment]:
        st = self.state
        out: list[Moment] = []
        m = minute - 1  # the minute that just completed
        if m < 4:
            return out
        for team in (st.home, st.away):
            shift = self.regimes.check(st, team, m)
            if shift:
                verb = "cranked up" if shift["direction"] == "up" else "dialled down"
                out.append(self._new(
                    t=t, clock=clock, kind="press_shift", team=team, players=[],
                    importance=58,
                    headline=f"{self._team(team)} have {verb} their press since {shift['onset_clock']}",
                    facts=shift,
                    why=[
                        {"label": "Players within 8 m of the ball in the opponent's build-up",
                         "value": shift["players_near_ball_after"],
                         "detail": f"was {shift['players_near_ball_before']} before {shift['onset_clock']}"},
                        {"label": "Defensive line height (m from own goal)", "value": shift["line_height_after_m"],
                         "detail": f"was {shift['line_height_before_m']}"},
                        {"label": "PPDA (lower = more aggressive)", "value": shift["ppda_after"],
                         "detail": f"was {shift['ppda_before']}"},
                        {"label": "High regains in window", "value": shift["high_regains_recent"]},
                    ],
                ))
        cci = control_chaos(st, m)
        pend_label, pend_n = self._cci_pending
        self._cci_pending = (cci["label"], pend_n + 1 if cci["label"] == pend_label else 1)
        stable = self._cci_pending[1] >= 2
        if (stable and cci["label"] != self._cci_label and cci["label"] != "balanced" and m >= 8
                and m - self._cci_last_change >= 6):
            self._cci_label = cci["label"]
            self._cci_last_change = m
            ctrl = self._team(cci["controller"]) if cci["controller"] else None
            out.append(self._new(
                t=t, clock=clock, kind="control_chaos", team=cci["controller"], players=[],
                importance=40 if cci["label"] == "chaos" else 36,
                headline=(f"{ctrl} have taken control" if cci["label"] == "control" and ctrl
                          else "The game has descended into chaos"),
                facts=cci, why=cci["factors"],
            ))
        elif stable and cci["label"] == "balanced":
            self._cci_label = "balanced"
        if m % 3 == 0 and m >= 10:
            rh = rhythm(st, m)
            if rh["label"] != self._rhythm_label and rh["label"] in {"siege", "end_to_end", "sterile_possession"}:
                self._rhythm_label = rh["label"]
                tname = self._team(rh["team"]) if rh["team"] else ""
                headline = {
                    "siege": f"{tname} are laying siege",
                    "end_to_end": "End-to-end: chances at both ends",
                    "sterile_possession": f"{tname} have the ball but no bite",
                }[rh["label"]]
                out.append(self._new(
                    t=t, clock=clock, kind="rhythm", team=rh["team"], players=[], importance=38,
                    headline=headline, facts=rh,
                    why=[{"label": "Field tilt", "value": rh["field_tilt"]},
                         {"label": "Shots in last 8 min", "value": rh["shots"]},
                         {"label": "xG in last 8 min", "value": rh["xg"]}],
                ))
            elif rh["label"] in {"balanced", "cagey"}:
                self._rhythm_label = rh["label"]
        mom = st.momentum
        sign = 1 if mom > 45 else (-1 if mom < -45 else 0)
        if sign and sign != self._momentum_sign and m >= 10:
            prev = self._momentum_sign
            self._momentum_sign = sign
            if prev == -sign:
                team = st.home if sign > 0 else st.away
                out.append(self._new(
                    t=t, clock=clock, kind="momentum_swing", team=team, players=[], importance=46,
                    headline=f"Momentum has swung to {self._team(team)}",
                    facts={"momentum": mom, "series": st.momentum_series[-12:]},
                    why=[{"label": "Momentum (threat EWMA)", "value": mom, "detail": "-100 away dominance .. +100 home"}],
                ))
        elif sign:
            self._momentum_sign = sign
        return out
