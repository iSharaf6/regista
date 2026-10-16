"""MatchState: the shared blackboard every agent reads from.

Consumes the live feed (events + 5 Hz frames) incrementally and keeps:
team and player aggregates, per-minute bins for windowed signals, live
speed/distance from tracking, and time series for win probability and
momentum. Each event is returned *enriched* with derived metrics and the
factors that explain them.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..schema.events import PITCH_LENGTH as L
from ..schema.events import PITCH_WIDTH as W
from ..schema.events import EventType, MatchEvent, MatchInfo, PlayerInfo
from .models import expected_goals, pass_difficulty, win_probability

GOAL_Y = W / 2
MAX_MIN = 130
SPRINT_KMH = 25.2
HSR_KMH = 19.8
SPEED_FLASH_KMH = 33.0
ON_BALL = {
    EventType.PASS, EventType.CARRY, EventType.DRIBBLE, EventType.SHOT, EventType.THROW_IN,
    EventType.GOAL_KICK, EventType.FREE_KICK, EventType.CORNER, EventType.KICK_OFF,
}


@dataclass
class TeamAgg:
    id: str
    goals: int = 0
    shots: int = 0
    on_target: int = 0
    xg: float = 0.0
    big_chances: int = 0
    passes: int = 0
    passes_complete: int = 0
    progressive_passes: int = 0
    final_third_entries: int = 0
    box_entries: int = 0
    crosses: int = 0
    corners: int = 0
    fouls: int = 0
    yellow: int = 0
    red: int = 0
    offsides: int = 0
    tackles: int = 0
    interceptions: int = 0
    pressures: int = 0
    high_regains: int = 0
    dribbles: int = 0
    dribbles_won: int = 0
    possession_s: float = 0.0
    difficulty_sum: float = 0.0
    packing: int = 0
    max_shot_speed: float = 0.0

    def view(self, total_poss: float) -> dict[str, Any]:
        return {
            "goals": self.goals,
            "shots": self.shots,
            "on_target": self.on_target,
            "xg": round(self.xg, 2),
            "big_chances": self.big_chances,
            "passes": self.passes,
            "pass_accuracy": round(100 * self.passes_complete / self.passes, 1) if self.passes else 0.0,
            "progressive_passes": self.progressive_passes,
            "final_third_entries": self.final_third_entries,
            "box_entries": self.box_entries,
            "crosses": self.crosses,
            "corners": self.corners,
            "fouls": self.fouls,
            "yellow_cards": self.yellow,
            "red_cards": self.red,
            "offsides": self.offsides,
            "tackles": self.tackles,
            "interceptions": self.interceptions,
            "pressures": self.pressures,
            "high_regains": self.high_regains,
            "dribbles_won": self.dribbles_won,
            "possession": round(100 * self.possession_s / total_poss, 1) if total_poss else 50.0,
            "avg_pass_difficulty": round(self.difficulty_sum / self.passes, 1) if self.passes else 0.0,
            "opponents_bypassed": self.packing,
            "max_shot_speed_kmh": round(self.max_shot_speed, 1),
        }


@dataclass
class PlayerAgg:
    info: PlayerInfo
    team: str
    on_pitch: bool
    touches: int = 0
    passes: int = 0
    passes_complete: int = 0
    key_passes: int = 0
    progressive_passes: int = 0
    difficulty_sum: float = 0.0
    hardest_pass: float = 0.0
    packing: int = 0
    xa: float = 0.0
    shots: int = 0
    xg: float = 0.0
    goals: int = 0
    assists: int = 0
    tackles: int = 0
    interceptions: int = 0
    pressures: int = 0
    dribbles_won: int = 0
    fouls: int = 0
    yellow: int = 0
    red: int = 0
    distance_m: float = 0.0
    hsr_m: float = 0.0
    top_speed: float = 0.0
    speed: float = 0.0
    sprints: int = 0
    in_sprint: bool = False
    sum_x: float = 0.0
    sum_y: float = 0.0
    n_pos: int = 0
    last_flash_t: float = -999.0
    km_announced: int = 0

    @property
    def rating(self) -> float:
        r = 6.0 + 1.0 * self.goals + 0.7 * self.assists + 0.8 * self.xg + 0.7 * self.xa + 0.15 * self.key_passes
        r += 0.06 * (self.tackles + self.interceptions + self.dribbles_won) + 0.004 * self.packing
        if self.passes >= 10:
            r += 1.5 * (self.passes_complete / self.passes - 0.8)
        r -= 0.25 * self.yellow + 1.5 * self.red
        return round(min(10.0, max(4.0, r)), 1)

    def view(self) -> dict[str, Any]:
        return {
            "id": self.info.id,
            "name": self.info.name,
            "short_name": self.info.short_name,
            "number": self.info.number,
            "position": self.info.position,
            "team": self.team,
            "on_pitch": self.on_pitch,
            "rating": self.rating,
            "touches": self.touches,
            "passes": self.passes,
            "pass_accuracy": round(100 * self.passes_complete / self.passes, 1) if self.passes else 0.0,
            "key_passes": self.key_passes,
            "progressive_passes": self.progressive_passes,
            "avg_pass_difficulty": round(self.difficulty_sum / self.passes, 1) if self.passes else 0.0,
            "hardest_completed_pass": round(self.hardest_pass, 1),
            "opponents_bypassed": self.packing,
            "xa": round(self.xa, 2),
            "shots": self.shots,
            "xg": round(self.xg, 2),
            "goals": self.goals,
            "assists": self.assists,
            "tackles": self.tackles,
            "interceptions": self.interceptions,
            "pressures": self.pressures,
            "dribbles_won": self.dribbles_won,
            "yellow_cards": self.yellow,
            "red_cards": self.red,
            "distance_km": round(self.distance_m / 1000, 2),
            "high_speed_km": round(self.hsr_m / 1000, 2),
            "top_speed_kmh": round(self.top_speed, 1),
            "current_speed_kmh": round(self.speed, 1),
            "sprints": self.sprints,
            "avg_position": [round(self.sum_x / self.n_pos, 1), round(self.sum_y / self.n_pos, 1)] if self.n_pos else None,
        }


@dataclass
class Enriched:
    event: MatchEvent
    data: dict[str, Any] = field(default_factory=dict)
    signals: list[dict[str, Any]] = field(default_factory=list)


class MatchState:
    def __init__(self, info: MatchInfo, prior_rates: tuple[float, float] = (1.5 / 92, 1.25 / 92)):
        self.info = info
        self.home, self.away = info.home.id, info.away.id
        self.team = {self.home: TeamAgg(self.home), self.away: TeamAgg(self.away)}
        self.names = {self.home: info.home.name, self.away: info.away.name}
        self.short = {self.home: info.home.short_name, self.away: info.away.short_name}
        self.players: dict[str, PlayerAgg] = {}
        for t in (info.home, info.away):
            for p in t.players:
                self.players[p.id] = PlayerAgg(info=p, team=t.id, on_pitch=p.starting)
        self.roster = info.roster
        self._idx = {
            t: np.array([i for i, pid in enumerate(self.roster) if self.players[pid].team == t]) for t in (self.home, self.away)
        }
        self._is_gk = np.array([self.players[pid].info.position == "GK" for pid in self.roster])
        self.t = 0.0
        self.clock = "0'"
        self.minute = 0
        self.period = 1
        self.status = "pre_match"
        self.score = {self.home: 0, self.away: 0}
        self.prior = {self.home: prior_rates[0], self.away: prior_rates[1]}
        self.red_cards = {self.home: 0, self.away: 0}
        self.events: dict[str, MatchEvent] = {}
        self.enriched: dict[str, dict[str, Any]] = {}
        self.timeline: list[dict[str, Any]] = []  # goals, cards, subs
        self.wp_series: list[dict[str, Any]] = []
        self.momentum_series: list[dict[str, Any]] = []
        self.ball_speed = 0.0
        self._poss_team: str | None = None
        self._poss_t = 0.0
        self._prev_frame: tuple[float, np.ndarray, np.ndarray] | None = None
        self.frames: deque[tuple[float, np.ndarray]] = deque(maxlen=150)
        self.last_frame: dict[str, Any] | None = None
        # per-minute bins: bins[team][metric][minute]
        metrics = ("xg", "shots", "passes", "passes_complete", "final_third", "box_entries", "pressures",
                   "pressures_high", "def_actions", "def_actions_high", "turnovers", "possession_s",
                   "duels", "opp_passes_own60", "regains_high",
                   "press_near_sum", "press_frames", "line_sum", "line_frames", "press_dist_sum")
        self.bins = {t: {m: np.zeros(MAX_MIN) for m in metrics} for t in (self.home, self.away)}
        self.match_bins = {m: np.zeros(MAX_MIN) for m in ("possession_changes", "ball_speed_sum", "ball_speed_n")}
        self.bin_clock: list[str] = [""] * MAX_MIN
        self._p1_bins = 0
        self._bin = 0
        self._momentum_ewma = {self.home: 0.0, self.away: 0.0}
        self._last_momentum_min = -1
        self.wp = (0.45, 0.28, 0.27)
        self._record_wp("kick-off")

    # ------------------------------------------------------------------ helpers
    def other(self, team: str) -> str:
        return self.away if team == self.home else self.home

    def att(self, team: str, x: float, y: float) -> tuple[float, float]:
        return (x, y) if team == self.home else (L - x, W - y)

    def match_minute(self, ev: MatchEvent | None = None) -> int:
        """Continuous play-minute index used for bins (first-half stoppage never collides with 46')."""
        if ev is None:
            return self._bin
        if ev.period == 1:
            idx = int(ev.t // 60)
            self._p1_bins = max(self._p1_bins, idx + 1)
        else:
            idx = self._p1_bins + int(max(0.0, ev.t - getattr(self, "_p2_start", ev.t)) // 60)
        idx = int(min(MAX_MIN - 1, max(0, idx)))
        if not self.bin_clock[idx]:
            self.bin_clock[idx] = f"{ev.minute + 1}'" if ev.clock.count("+") == 0 else ev.clock
        return idx

    def clock_at(self, idx: int) -> str:
        idx = int(min(MAX_MIN - 1, max(0, idx)))
        while idx > 0 and not self.bin_clock[idx]:
            idx -= 1
        return self.bin_clock[idx] or "1'"

    def minutes_played(self) -> float:
        if self.period == 1:
            return min(self.t / 60, 47)
        return 45 + max(0.0, (self.t - self._p2_start) / 60) if hasattr(self, "_p2_start") else 45

    def minutes_left(self) -> float:
        if self.status == "full_time":
            return 0.0
        return max(0.3, 94.0 - self.minutes_played())

    def player_name(self, pid: str | None) -> str:
        return self.players[pid].info.name if pid and pid in self.players else ""

    def frame_near(self, t: float) -> np.ndarray | None:
        best, bd = None, 1e9
        for ft, pos in reversed(self.frames):
            d = abs(ft - t)
            if d < bd:
                best, bd = pos, d
            if ft < t - 1:
                break
        return best

    # ------------------------------------------------------------------ frames
    def on_frame(self, frame: dict[str, Any]) -> list[dict[str, Any]]:
        t = float(frame["t"])
        pos = np.array([[np.nan, np.nan] if p is None else p for p in frame["p"]], dtype=float)
        ball = np.array(frame["b"], dtype=float)
        self.frames.append((t, pos))
        self.last_frame = frame
        signals: list[dict[str, Any]] = []
        if self._prev_frame is not None:
            pt, ppos, pball = self._prev_frame
            dt = t - pt
            if 0 < dt < 1.0:
                disp = np.linalg.norm(pos - ppos, axis=1)
                kmh = np.nan_to_num(disp / dt * 3.6, nan=0.0)
                self.ball_speed = float(np.linalg.norm(ball[:2] - pball[:2]) / dt * 3.6)
                m = self.match_minute()
                self.match_bins["ball_speed_sum"][m] += self.ball_speed
                self.match_bins["ball_speed_n"][m] += 1
                for i, pid in enumerate(self.roster):
                    if math.isnan(pos[i, 0]):
                        continue
                    pl = self.players[pid]
                    d = float(np.nan_to_num(disp[i]))
                    v = float(kmh[i])
                    pl.speed = 0.6 * pl.speed + 0.4 * v
                    pl.distance_m += d
                    if pl.speed > HSR_KMH:
                        pl.hsr_m += d
                    if pl.speed > pl.top_speed:
                        pl.top_speed = pl.speed
                    pl.sum_x += pos[i, 0]
                    pl.sum_y += pos[i, 1]
                    pl.n_pos += 1
                    if pl.speed > SPRINT_KMH and not pl.in_sprint:
                        pl.in_sprint = True
                        pl.sprints += 1
                    elif pl.speed < SPRINT_KMH - 3:
                        pl.in_sprint = False
                    if pl.speed >= SPEED_FLASH_KMH and t - pl.last_flash_t > 120:
                        pl.last_flash_t = t
                        signals.append({"type": "speed_flash", "t": t, "player": pid, "team": pl.team,
                                        "speed_kmh": round(pl.speed, 1), "top_speed_kmh": round(pl.top_speed, 1)})
                    km = int(pl.distance_m // 1000)
                    if km in (10, 12) and km > pl.km_announced:
                        pl.km_announced = km
                        signals.append({"type": "distance_milestone", "t": t, "player": pid, "team": pl.team,
                                        "km": km})
        self._track_shape(pos, ball)
        self._prev_frame = (t, pos, ball)
        self.t = t
        return signals

    def _track_shape(self, pos: np.ndarray, ball: np.ndarray) -> None:
        """Tracking-derived pressing and block metrics for the team out of possession."""
        if self._poss_team is None or self.status != "live":
            return
        d_team = self.other(self._poss_team)
        idx = self._idx[d_team]
        p = pos[idx]
        valid = ~np.isnan(p[:, 0]) & ~self._is_gk[idx]
        if valid.sum() < 6:
            return
        p = p[valid]
        m = self._bin
        bx_att = ball[0] if d_team == self.home else L - ball[0]
        if bx_att > 60:  # opponent building up deep in their own half: where a high press lives
            dists = np.sort(np.hypot(p[:, 0] - ball[0], p[:, 1] - ball[1]))
            near = int((dists < 8.0).sum())
            self.bins[d_team]["press_near_sum"][m] += near
            self.bins[d_team]["press_dist_sum"][m] += float(np.minimum(dists[:2], 25.0).mean())
            self.bins[d_team]["press_frames"][m] += 1
        if 35 < bx_att < 75:  # line height measured with the ball in midfield, so it is not just following the ball
            xs = p[:, 0] if d_team == self.home else L - p[:, 0]
            self.bins[d_team]["line_sum"][m] += float(np.sort(xs)[:4].mean())
            self.bins[d_team]["line_frames"][m] += 1

    # ------------------------------------------------------------------ events
    def _possession_tick(self, ev: MatchEvent) -> None:
        if self._poss_team is not None:
            dt = max(0.0, min(ev.t - self._poss_t, 60.0))
            self.team[self._poss_team].possession_s += dt
            self.bins[self._poss_team]["possession_s"][self.match_minute(ev)] += dt
        if ev.type in ON_BALL and ev.team:
            if self._poss_team is not None and ev.team != self._poss_team:
                self.match_bins["possession_changes"][self.match_minute(ev)] += 1
                self.bins[self._poss_team]["turnovers"][self.match_minute(ev)] += 1
            self._poss_team = ev.team
        self._poss_t = ev.t

    def on_event(self, ev: MatchEvent) -> Enriched:
        self.events[ev.id] = ev
        self.t = max(self.t, ev.t)
        self.clock = ev.clock
        self.minute = ev.minute
        if ev.type == EventType.SECOND_HALF:
            self.period = 2
            self._p2_start = ev.t
        self.period = ev.period
        self._bin = self.match_minute(ev)
        if self.status == "pre_match":
            self.status = "live"
        self._possession_tick(ev)
        out = Enriched(ev)
        m = self.match_minute(ev)
        team = self.team[ev.team] if ev.team else None
        pl = self.players.get(ev.player or "")
        if pl and ev.type in ON_BALL:
            pl.touches += 1
        handler = getattr(self, f"_on_{ev.type.value}", None)
        if handler:
            handler(ev, out, team, pl, m)
        self._update_momentum(m)
        self.enriched[ev.id] = out.data
        return out

    def _on_pass(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team and pl and ev.team
        ax, ay = self.att(ev.team, ev.x or 0, ev.y or 0)
        ex, ey = self.att(ev.team, ev.end_x or 0, ev.end_y or 0)
        length = math.hypot(ex - ax, ey - ay)
        fwd = ex - ax
        q = ev.qualifiers
        into_box = ex > L - 16.5 and abs(ey - GOAL_Y) < 20.16 and not (ax > L - 16.5 and abs(ay - GOAL_Y) < 20.16)
        final_third = ex > 70 and ax <= 70
        receiver_space = None
        packing = 0
        frame = self.frame_near(ev.t)
        if frame is not None:
            opp_idx = [i for i, pid in enumerate(self.roster) if self.players[pid].team != ev.team]
            if ev.receiver and ev.receiver in self.roster:
                r = self.roster.index(ev.receiver)
                rp = frame[r]
                ds = [math.hypot(*(frame[i] - rp)) for i in opp_idx if not math.isnan(frame[i, 0])]
                receiver_space = min(ds) if ds else None
            if fwd > 0:
                for i in opp_idx:
                    if math.isnan(frame[i, 0]) or self.players[self.roster[i]].info.position == "GK":
                        continue
                    ox, _ = self.att(ev.team, frame[i, 0], frame[i, 1])
                    if ax < ox < ex:
                        packing += 1
        diff, factors = pass_difficulty(length, ev.under_pressure, fwd, into_box, bool(q.get("cross")),
                                        bool(q.get("through_ball")), q.get("height", "ground"), receiver_space)
        complete = ev.outcome == "complete"
        progressive = complete and fwd >= 10 and ex > 52.5
        team.passes += 1
        pl.passes += 1
        team.difficulty_sum += diff
        pl.difficulty_sum += diff
        self.bins[ev.team]["passes"][m] += 1
        if ax < 63:
            self.bins[self.other(ev.team)]["opp_passes_own60"][m] += 1
        if q.get("cross"):
            team.crosses += 1
        if complete:
            team.passes_complete += 1
            pl.passes_complete += 1
            self.bins[ev.team]["passes_complete"][m] += 1
            team.packing += packing
            pl.packing += packing
            pl.hardest_pass = max(pl.hardest_pass, diff)
            if progressive:
                team.progressive_passes += 1
                pl.progressive_passes += 1
            if final_third:
                team.final_third_entries += 1
                self.bins[ev.team]["final_third"][m] += 1
            if into_box:
                team.box_entries += 1
                self.bins[ev.team]["box_entries"][m] += 1
        out.data = {
            "length_m": round(length, 1),
            "forward_m": round(fwd, 1),
            "difficulty": diff,
            "difficulty_factors": [f.as_dict() for f in factors],
            "opponents_bypassed": packing if complete else 0,
            "receiver_space_m": None if receiver_space is None else round(receiver_space, 1),
            "ball_speed_kmh": round(float(q.get("ball_speed_kmh", 0.0)), 1),
            "progressive": progressive,
            "into_box": into_box and complete,
            "final_third_entry": final_third and complete,
            "passer_accuracy": round(100 * pl.passes_complete / pl.passes, 1),
            "passer_passes": pl.passes,
            "complete": complete,
        }
        if pl.passes in (50, 100):
            out.signals.append({"type": "milestone", "player": pl.info.id, "team": ev.team,
                                "label": f"{pl.passes} passes", "value": pl.passes,
                                "accuracy": out.data["passer_accuracy"]})

    def _on_shot(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team and pl and ev.team
        ax, ay = self.att(ev.team, ev.x or 0, ev.y or 0)
        q = ev.qualifiers
        xg, factors = expected_goals(ax, ay, q.get("body_part") == "head", ev.under_pressure, q.get("set_piece"))
        dist = math.hypot(L - ax, GOAL_Y - ay)
        on_target = ev.outcome in {"goal", "saved"}
        team.shots += 1
        team.xg += xg
        pl.shots += 1
        pl.xg += xg
        if xg >= 0.3:
            team.big_chances += 1
        if on_target:
            team.on_target += 1
        speed = float(q.get("shot_speed_kmh", 0.0))
        team.max_shot_speed = max(team.max_shot_speed, speed)
        self.bins[ev.team]["xg"][m] += xg
        self.bins[ev.team]["shots"][m] += 1
        assist_pid = q.get("assist_player")
        if not assist_pid:
            assist_pid = self._previous_passer(ev)
        if assist_pid and assist_pid in self.players:
            self.players[assist_pid].xa += xg
            self.players[assist_pid].key_passes += 1
        out.data = {
            "xg": round(xg, 3),
            "xg_factors": [f.as_dict() for f in factors],
            "distance_m": round(dist, 1),
            "shot_speed_kmh": round(speed, 1),
            "on_target": on_target,
            "body_part": q.get("body_part"),
            "set_piece": q.get("set_piece"),
            "assist_player": assist_pid,
            "shooter_shots": pl.shots,
            "shooter_xg": round(pl.xg, 2),
            "team_xg": round(team.xg, 2),
        }

    def _previous_passer(self, ev: MatchEvent) -> str | None:
        ids = list(self.events)
        for eid in reversed(ids[-6:-1]):
            prev = self.events[eid]
            if prev.type == EventType.PASS and prev.team == ev.team and prev.receiver == ev.player and prev.outcome == "complete":
                return prev.player
            if prev.type == EventType.POSSESSION_CHANGE:
                return None
        return None

    def _on_goal(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team and pl and ev.team
        before = self.wp
        self.score[ev.team] += 1
        team.goals += 1
        pl.goals += 1
        assist = ev.qualifiers.get("assist_player")
        if assist and assist in self.players:
            self.players[assist].assists += 1
        shot = self.events.get(ev.related[0]) if ev.related else None
        shot_data = self.enriched.get(shot.id, {}) if shot else {}
        self._record_wp(f"Goal {self.short[ev.team]}")
        after = self.wp
        idx = 0 if ev.team == self.home else 2
        self.timeline.append({"t": ev.t, "clock": ev.clock, "type": "goal", "team": ev.team, "player": ev.player,
                              "assist": assist, "score": dict(self.score)})
        out.data = {
            "score": dict(self.score),
            "score_text": f"{self.score[self.home]}-{self.score[self.away]}",
            "wp_before": [round(v, 3) for v in before],
            "wp_after": [round(v, 3) for v in after],
            "wp_swing": round(after[idx] - before[idx], 3),
            "xg": shot_data.get("xg"),
            "shot_speed_kmh": shot_data.get("shot_speed_kmh"),
            "distance_m": shot_data.get("distance_m"),
            "assist_player": assist,
            "scorer_goals": pl.goals,
        }

    def _on_card(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team and pl and ev.team
        if ev.outcome == "yellow":
            team.yellow += 1
            pl.yellow += 1
        else:
            team.red += 1
            pl.red += 1
            pl.on_pitch = False
            self.red_cards[ev.team] += 1
            before = self.wp
            self._record_wp(f"Red card {self.short[ev.team]}")
            out.data = {"wp_before": [round(v, 3) for v in before], "wp_after": [round(v, 3) for v in self.wp]}
        self.timeline.append({"t": ev.t, "clock": ev.clock, "type": f"card_{ev.outcome}", "team": ev.team,
                              "player": ev.player})

    def _on_substitution(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert pl
        pl.on_pitch = True
        off = ev.qualifiers.get("replaced")
        if off in self.players:
            self.players[off].on_pitch = False
        self.timeline.append({"t": ev.t, "clock": ev.clock, "type": "substitution", "team": ev.team,
                              "player": ev.player, "replaced": off})

    def _on_tackle(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team and pl and ev.team
        team.tackles += 1
        pl.tackles += 1
        self._def_action(ev, m)

    def _on_interception(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team and pl and ev.team
        team.interceptions += 1
        pl.interceptions += 1
        self._def_action(ev, m)

    def _def_action(self, ev: MatchEvent, m: int) -> None:
        assert ev.team
        ax, _ = self.att(ev.team, ev.x or 0, ev.y or 0)
        self.bins[ev.team]["def_actions"][m] += 1
        self.bins[ev.team]["duels"][m] += 1
        if ax > 42:  # in the opponent's defensive 60%
            self.bins[ev.team]["def_actions_high"][m] += 1
        if ax > 60:
            self.team[ev.team].high_regains += 1
            self.bins[ev.team]["regains_high"][m] += 1

    def _on_pressure(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team and pl and ev.team
        team.pressures += 1
        pl.pressures += 1
        self.bins[ev.team]["pressures"][m] += 1
        ax, _ = self.att(ev.team, ev.x or 0, ev.y or 0)
        if ax > 52.5:
            self.bins[ev.team]["pressures_high"][m] += 1

    def _on_foul(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team and pl and ev.team
        team.fouls += 1
        pl.fouls += 1
        self.bins[ev.team]["duels"][m] += 1
        ax, _ = self.att(ev.team, ev.x or 0, ev.y or 0)
        if ax > 42:
            self.bins[ev.team]["def_actions_high"][m] += 1

    def _on_dribble(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team and pl and ev.team
        team.dribbles += 1
        self.bins[ev.team]["duels"][m] += 1
        if ev.outcome == "won":
            team.dribbles_won += 1
            pl.dribbles_won += 1

    def _on_corner(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team
        team.corners += 1

    def _on_offside(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        assert team
        team.offsides += 1

    def _on_full_time(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        self.status = "full_time"
        self._record_wp("Full time")

    def _on_half_time(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        self.status = "half_time"

    def _on_second_half(self, ev: MatchEvent, out: Enriched, team: TeamAgg | None, pl: PlayerAgg | None, m: int) -> None:
        self.status = "live"

    # ------------------------------------------------------------------ live models
    def scoring_rates(self) -> dict[str, float]:
        played = max(1.0, self.minutes_played())
        k = 35.0  # prior strength, in minutes
        rates = {}
        for team in (self.home, self.away):
            rate = (self.prior[team] * k + self.team[team].xg) / (k + played)
            rate *= 0.75 ** self.red_cards[team] * 1.2 ** self.red_cards[self.other(team)]
            rates[team] = rate
        return rates

    def _record_wp(self, label: str) -> None:
        if self.status == "full_time":
            h, a = self.score[self.home], self.score[self.away]
            self.wp = (1.0, 0.0, 0.0) if h > a else ((0.0, 1.0, 0.0) if h == a else (0.0, 0.0, 1.0))
        else:
            rates = self.scoring_rates()
            self.wp = win_probability(self.score[self.home], self.score[self.away], self.minutes_left(),
                                      rates[self.home], rates[self.away])
        self.wp_series.append({"t": round(self.t, 1), "clock": self.clock, "label": label,
                               "home": round(self.wp[0], 3), "draw": round(self.wp[1], 3), "away": round(self.wp[2], 3)})

    def _update_momentum(self, m: int) -> None:
        if m <= self._last_momentum_min:
            return
        for mm in range(self._last_momentum_min + 1, m):
            for team in (self.home, self.away):
                b = self.bins[team]
                threat = b["xg"][mm] + 0.04 * b["box_entries"][mm] + 0.008 * b["final_third"][mm] + 0.01 * b["regains_high"][mm]
                self._momentum_ewma[team] = 0.78 * self._momentum_ewma[team] + 0.22 * threat
            h, a = self._momentum_ewma[self.home], self._momentum_ewma[self.away]
            val = 100 * (h - a) / (h + a + 0.02)
            self.momentum_series.append({"minute": mm, "clock": self.clock_at(mm), "value": round(val, 1)})
            if mm % 5 == 4:
                self._record_wp(f"{mm + 1}'")
        self._last_momentum_min = m - 1

    @property
    def momentum(self) -> float:
        return self.momentum_series[-1]["value"] if self.momentum_series else 0.0

    # ------------------------------------------------------------------ views
    def team_view(self, team: str) -> dict[str, Any]:
        total = self.team[self.home].possession_s + self.team[self.away].possession_s
        return {"id": team, "name": self.names[team], **self.team[team].view(total)}

    def player_view(self, pid: str) -> dict[str, Any]:
        return self.players[pid].view()

    def top_players(self, key: str = "rating", n: int = 5, team: str | None = None) -> list[dict[str, Any]]:
        views = [p.view() for p in self.players.values() if (team is None or p.team == team) and (p.on_pitch or p.touches)]
        return sorted(views, key=lambda v: v.get(key, 0) or 0, reverse=True)[:n]

    def snapshot(self) -> dict[str, Any]:
        return {
            "match_id": self.info.match_id,
            "t": round(self.t, 1),
            "clock": self.clock,
            "period": self.period,
            "status": self.status,
            "score": dict(self.score),
            "teams": {t: self.team_view(t) for t in (self.home, self.away)},
            "win_probability": {"home": round(self.wp[0], 3), "draw": round(self.wp[1], 3), "away": round(self.wp[2], 3)},
            "momentum": self.momentum,
            "ball_speed_kmh": round(self.ball_speed, 1),
            "timeline": self.timeline[-20:],
            "top_players": self.top_players(),
        }
