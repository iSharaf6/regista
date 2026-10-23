"""Synthetic match engine.

A possession-chain simulator coupled to a 5 Hz tracking-lite model:

* every action (pass, carry, take-on, shot, cross, clearance, set piece) is
  chosen from the carrier's context - zone, nearest-opponent pressure, team
  style and match state - and its outcome is drawn from an explicit model;
* all 22 players move every frame towards tactical targets (formation anchor,
  ball-side shift, block height, pressing triggers) under speed and
  acceleration limits, so speed, distance and sprint metrics are physical;
* a hidden ground-truth log records what the engine *knows* (true xG, the
  exact minute a team changed its press) so downstream explainers can be
  scored against reality - something real feeds can never offer.

The engine is deterministic for a given (home, away, seed, scenario).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

from ..schema.events import PITCH_LENGTH as L
from ..schema.events import PITCH_WIDTH as W
from ..schema.events import EventType, MatchEvent, MatchInfo, PlayerInfo, TeamInfo
from .scenarios import Scenario, get_scenario
from .squads import FORMATIONS, Player, Style, Team, load_team

DT = 0.2  # 5 Hz
HALF = 45 * 60
GOAL_Y = W / 2
BACK_LINE = {"RB", "CB", "LB"}
# furthest a role pushes up (attacking frame) when its team has the ball
ATTACK_CAP = {"ST": 95.0, "LW": 93.0, "RW": 93.0, "AM": 90.0, "LM": 90.0, "RM": 90.0,
              "CM": 84.0, "DM": 74.0, "RB": 78.0, "LB": 78.0, "CB": 64.0}


def _native(v: Any) -> Any:
    """Plain JSON types only in the feed (numpy scalars leak in from the physics)."""
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return round(float(v), 3)
    return v


def sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def goal_angle(dx: float, dy: float) -> float:
    """Angle subtended by the goal mouth (7.32 m) from a shooting position."""
    half = 3.66
    a = math.atan2(half - dy, dx) - math.atan2(-half - dy, dx)
    return abs(a)


def true_xg(dist: float, angle: float, header: bool, pressure: bool, big_chance: bool) -> float:
    z = -1.45 - 0.1 * dist + 1.2 * angle
    if header:
        z -= 1.0
    if pressure:
        z -= 0.3
    if big_chance:
        z += 0.5
    return min(0.92, sigmoid(z))


@dataclass
class SimResult:
    info: MatchInfo
    events: list[MatchEvent]
    frame_t: np.ndarray  # (F,)
    frame_ball: np.ndarray  # (F, 3)
    frame_pos: np.ndarray  # (F, N, 2) NaN when off pitch
    truth: list[dict[str, Any]]
    summary: dict[str, Any] = field(default_factory=dict)

    def frame(self, k: int) -> dict[str, Any]:
        pos = self.frame_pos[k]
        return {
            "t": round(float(self.frame_t[k]), 2),
            "b": [round(float(v), 2) for v in self.frame_ball[k]],
            "p": [None if math.isnan(x) else [round(float(x), 2), round(float(y), 2)] for x, y in pos],
        }


class MatchSimulator:
    def __init__(self, home: str = "NOR", away: str = "CAL", seed: int = 7, scenario: str | Scenario = "derby"):
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.home: Team = load_team(home)
        self.away: Team = load_team(away)
        if self.home.id == self.away.id:
            raise ValueError("home and away must differ")
        self.scenario = get_scenario(scenario) if isinstance(scenario, str) else scenario
        self.match_id = f"{self.home.abbr}-{self.away.abbr}-{seed}"
        self.teams = {self.home.id: self.home, self.away.id: self.away}
        self.style: dict[str, Style] = {t.id: t.style.copy() for t in (self.home, self.away)}

        self.roster: list[Player] = (
            self.home.starters + self.home.bench + self.away.starters + self.away.bench
        )
        self.N = len(self.roster)
        self.idx = {p.id: i for i, p in enumerate(self.roster)}
        self.team_of = np.array([0 if p.id.startswith(self.home.id) else 1 for p in self.roster])
        self.slot = np.array([p.slot for p in self.roster])
        self.on = np.array([p.starting for p in self.roster])
        self.maxspd = np.array([p.top_speed_kmh / 3.6 for p in self.roster])
        self.pos = np.zeros((self.N, 2))
        self.vel = np.zeros((self.N, 2))
        self.dist = np.zeros(self.N)
        self.energy = np.ones(self.N)
        self.yellow: set[int] = set()
        self.gone: set[int] = set()
        self.subs_made = {self.home.id: 0, self.away.id: 0}
        self._on_lists: dict[str, list[int]] = {}
        self._refresh_on()

        self.t = 0.0
        self.period = 1
        self.p2_start = 0.0
        self.stoppage = [0.0, 0.0]
        self.score = {self.home.id: 0, self.away.id: 0}
        self.poss: str = self.home.id
        self.carrier: int | None = None
        self.ball = np.array([L / 2, W / 2, 0.0])
        self.attached: int | None = None
        self.kickoff_mode = False

        self.events: list[MatchEvent] = []
        self.truth: list[dict[str, Any]] = []
        self._ft: list[float] = []
        self._fb: list[tuple[float, float, float]] = []
        self._fp: list[np.ndarray] = []
        self._applied_shifts: set[int] = set()
        self._adapted: set[str] = set()
        self._seq = 0
        self._place_kickoff_shape()

    # ------------------------------------------------------------------ geometry
    def other(self, team: str) -> str:
        return self.away.id if team == self.home.id else self.home.id

    def tid(self, i: int) -> str:
        return self.home.id if self.team_of[i] == 0 else self.away.id

    def to_pitch(self, team: str, ax: float, ay: float) -> tuple[float, float]:
        return (ax, ay) if team == self.home.id else (L - ax, W - ay)

    to_att = to_pitch  # the transform is its own inverse

    def _refresh_on(self) -> None:
        for k, team in enumerate((self.home.id, self.away.id)):
            self._on_lists[team] = [i for i in range(self.N) if self.on[i] and self.team_of[i] == k]

    def on_team(self, team: str) -> list[int]:
        return self._on_lists[team]

    def nearest(self, team: str, x: float, y: float, exclude: int | None = None) -> tuple[int, float]:
        best, bd = -1, 1e9
        for i in self.on_team(team):
            if i == exclude:
                continue
            d = math.hypot(self.pos[i, 0] - x, self.pos[i, 1] - y)
            if d < bd:
                best, bd = i, d
        return best, bd

    def role(self, i: int) -> str:
        team = self.teams[self.tid(i)]
        return FORMATIONS[team.formation][self.slot[i]][0]

    # ------------------------------------------------------------------ clock
    def clock(self, t: float | None = None) -> tuple[int, int, int, str]:
        t = self.t if t is None else t
        if self.period == 1 or t < self.p2_start:
            el, base, period = t, 0, 1
        else:
            el, base, period = t - self.p2_start + HALF, HALF, 2
        # Use the same precision as the event timestamp. Repeated 0.2 s steps
        # otherwise label e.g. t=60.0 as 0:59 at floating-point boundaries.
        el = round(el, 2)
        cap = base + HALF
        minute = int(el // 60)
        second = int(el % 60)
        if el >= cap:
            extra = int((el - cap) // 60) + 1
            label = f"{cap // 60}+{extra}'"
        else:
            label = f"{minute + 1}'"
        return period, minute, second, label

    # ------------------------------------------------------------------ events
    def emit(self, etype: EventType, team: str | None = None, player: int | None = None, *,
             x: float | None = None, y: float | None = None, end: tuple[float, float] | None = None,
             outcome: str | None = None, receiver: int | None = None, pressure: bool = False,
             t: float | None = None, related: list[str] | None = None, **q: Any) -> MatchEvent:
        t = self.t if t is None else t
        period, minute, second, label = self.clock(t)
        self._seq += 1
        ev = MatchEvent(
            id=f"e{self._seq:05d}",
            match_id=self.match_id,
            seq=self._seq,
            t=round(t, 2),
            period=period,
            minute=minute,
            second=second,
            clock=label,
            type=etype,
            team=team,
            player=self.roster[player].id if player is not None else None,
            x=None if x is None else round(x, 2),
            y=None if y is None else round(y, 2),
            end_x=None if end is None else round(end[0], 2),
            end_y=None if end is None else round(end[1], 2),
            outcome=outcome,
            receiver=self.roster[receiver].id if receiver is not None else None,
            under_pressure=pressure,
            qualifiers={k: _native(v) for k, v in q.items()},
            related=related or [],
        )
        self.events.append(ev)
        return ev

    # ------------------------------------------------------------------ movement
    def _place_kickoff_shape(self) -> None:
        for team in (self.home, self.away):
            shape = FORMATIONS[team.formation]
            for i in self.on_team(team.id):
                _, ax, ay = shape[self.slot[i]]
                ax = min(ax * 0.5, L / 2 - 1.5)
                self.pos[i] = self.to_pitch(team.id, ax, ay)
        self.vel[:] = 0

    def _targets(self, ball: tuple[float, float], roles: dict[int, tuple[float, float]], press: bool,
                 dead: bool) -> tuple[np.ndarray, np.ndarray]:
        tgt = self.pos.copy()
        urg = np.full(self.N, 0.44)
        for team in (self.home, self.away):
            st = self.style[team.id]
            bx, by = self.to_att(team.id, ball[0], ball[1])
            in_poss = team.id == self.poss
            shape = FORMATIONS[team.formation]
            for i in self.on_team(team.id):
                role, ax, ay = shape[self.slot[i]]
                if role == "GK":
                    tx = 4.0 + max(0.0, bx - 35.0) * 0.14
                    ty = GOAL_Y + (by - GOAL_Y) * 0.22
                elif self.kickoff_mode:
                    tx = min(ax * 0.5, L / 2 - 1.5)
                    ty = ay
                elif in_poss:
                    tx = ax + (bx - 50.0) * 0.42 + 6.0 * st.line_height
                    ty = GOAL_Y + (ay - GOAL_Y) * (0.78 + 0.4 * st.width) + (by - GOAL_Y) * 0.15
                    tx = min(tx, ATTACK_CAP.get(role, 88.0))
                else:
                    tx = ax + (bx - 50.0) * 0.5 - 18.0 + 24.0 * st.line_height
                    ty = GOAL_Y + (ay - GOAL_Y) * 0.66 + (by - GOAL_Y) * 0.36
                    if role in BACK_LINE:
                        tx = min(tx, max(bx - 4.0, 7.0))
                    tx = max(tx, 6.5 if role in BACK_LINE else 13.0)
                tx = min(max(tx, 1.5), L - 1.5)
                ty = min(max(ty, 1.5), W - 1.5)
                tgt[i] = self.to_pitch(team.id, tx, ty)
        if press and not dead:
            dteam = self.other(self.poss)
            st = self.style[dteam]
            bx_att, _ = self.to_att(dteam, ball[0], ball[1])
            # how far up the pitch the defending team is willing to engage
            engage_line = 105.0 - 40.0 - 45.0 * st.press_intensity
            n_press = 0
            if bx_att >= engage_line:
                n_press = 1 + int(st.press_intensity > 0.6) + int(st.press_intensity > 0.85 and bx_att > 55) \
                    + int(st.press_intensity > 0.92 and bx_att > 70)
            elif bx_att < 40 or st.press_intensity >= 0.3:
                n_press = 1  # always engage near our own goal; a deep block lets midfield build-up go
            near = sorted(self.on_team(dteam), key=lambda i: (self.pos[i, 0] - ball[0]) ** 2 + (self.pos[i, 1] - ball[1]) ** 2)
            for k, i in enumerate(near[:n_press]):
                if self.role(i) == "GK":
                    continue
                gx, gy = self.to_pitch(dteam, 0.0, GOAL_Y)
                v = np.array([gx - ball[0], gy - ball[1]])
                v = v / (np.linalg.norm(v) + 1e-6)
                off = 1.2 + 1.8 * k
                tgt[i] = (ball[0] + v[0] * off, ball[1] + v[1] * off)
                urg[i] = min(1.0, 0.7 + 0.4 * st.press_intensity)
        for i, xy in roles.items():
            tgt[i] = xy
            urg[i] = 1.0
        if dead:
            urg *= 0.6
        return tgt, urg

    def _step(self, tgt: np.ndarray, urg: np.ndarray) -> None:
        on = self.on
        previous = self.pos.copy()
        d = tgt - self.pos
        desired = d / 0.9
        if self.attached is not None:
            a = self.attached
            feet = self.ball[:2] + np.array([-0.6 if self.team_of[a] == 0 else 0.6, 0.2])
            # Follow the ball through the same physical limits as every other
            # player. Snapping here and then integrating velocity moved carriers
            # twice per frame and invented speed/distance in the tracking feed.
            desired[a] = (feet - self.pos[a]) / DT
        sp = np.linalg.norm(desired, axis=1) + 1e-9
        cap = self.maxspd * urg * self.energy
        if self.attached is not None:
            # A carrier follows the ball at running effort, not the lower
            # urgency used to drift towards a formation anchor.
            cap[self.attached] = self.maxspd[self.attached] * self.energy[self.attached]
        desired *= np.minimum(1.0, cap / sp)[:, None]
        dv = desired - self.vel
        dvn = np.linalg.norm(dv, axis=1) + 1e-9
        dv *= np.minimum(1.0, (4.2 * DT) / dvn)[:, None]
        self.vel = np.where(on[:, None], self.vel + dv, 0.0)
        self.pos = np.where(on[:, None], self.pos + self.vel * DT, self.pos)
        np.clip(self.pos[:, 0], 0.5, L - 0.5, out=self.pos[:, 0])
        np.clip(self.pos[:, 1], 0.5, W - 0.5, out=self.pos[:, 1])
        displacement = np.where(on[:, None], self.pos - previous, 0.0)
        self.vel = displacement / DT
        self.dist += np.linalg.norm(displacement, axis=1)
        stamina = np.array([p.stamina for p in self.roster])
        self.energy = np.clip(1.0 - (self.dist / 12500.0) * (1.15 - stamina) * 0.6, 0.8, 1.0)

    def _record(self) -> None:
        self._ft.append(self.t)
        self._fb.append((float(self.ball[0]), float(self.ball[1]), float(self.ball[2])))
        p = self.pos.copy()
        p[~self.on] = np.nan
        self._fp.append(p.astype(np.float32))

    def _end_time(self, duration: float) -> float:
        """Completion timestamp on the same 5 Hz grid used by advance()."""
        return round(self.t + max(1, int(round(duration / DT))) * DT, 2)

    def advance(self, duration: float, ball_fn: Callable[[float], tuple[float, float, float]] | None = None,
                roles_fn: Callable[[float], dict[int, tuple[float, float]]] | None = None,
                press: bool = True, dead: bool = False, attach: int | None = None) -> None:
        n = max(1, int(round(duration / DT)))
        start = self.ball.copy()
        self.attached = attach
        for k in range(1, n + 1):
            frac = k / n
            if ball_fn is not None:
                self.ball = np.array(ball_fn(frac), dtype=float)
            else:
                self.ball = start
            roles = roles_fn(frac) if roles_fn else {}
            tgt, urg = self._targets((self.ball[0], self.ball[1]), roles, press, dead)
            self._step(tgt, urg)
            self.t += DT
            self._record()
            self._maybe_tactics()
        self.attached = None

    def walk_ball(self, a: tuple[float, float], b: tuple[float, float], speed: float, z_peak: float = 0.0
                  ) -> tuple[Callable[[float], tuple[float, float, float]], float]:
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        dur = max(DT, d / max(speed, 0.1))

        def fn(f: float) -> tuple[float, float, float]:
            return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, z_peak * 4 * f * (1 - f))

        return fn, dur

    # ------------------------------------------------------------------ tactics / truth
    def _maybe_tactics(self) -> None:
        period, minute, _, _ = self.clock()
        for k, shift in enumerate(self.scenario.shifts):
            if k in self._applied_shifts or minute < shift.minute or minute > shift.minute + shift.window:
                continue
            team = self.home.id if shift.team == "home" else self.away.id
            mine, theirs = self.score[team], self.score[self.other(team)]
            if (shift.when == "trailing" and mine >= theirs) or (shift.when == "leading" and mine <= theirs) \
                    or (shift.when == "not_winning" and mine > theirs):
                continue
            self._applied_shifts.add(k)
            before = dict(self.style[team].__dict__)
            for key, val in shift.changes.items():
                setattr(self.style[team], key, val)
            self.truth.append({
                "type": "tactical_shift", "t": round(self.t, 1), "clock": self.clock()[3], "team": team,
                "label": shift.label, "before": before, "after": dict(self.style[team].__dict__),
            })
        if self.scenario.auto_adapt and minute >= 65:
            for team in (self.home.id, self.away.id):
                if team in self._adapted:
                    continue
                deficit = self.score[self.other(team)] - self.score[team]
                if deficit > 0:
                    st = self.style[team]
                    before = dict(st.__dict__)
                    st.press_intensity = min(1.0, st.press_intensity + 0.3)
                    st.directness = min(1.0, st.directness + 0.15)
                    st.line_height = min(1.0, st.line_height + 0.15)
                    self._adapted.add(team)
                    self.truth.append({
                        "type": "tactical_shift", "t": round(self.t, 1), "clock": self.clock()[3], "team": team,
                        "label": "Chasing the game: higher press, more direct", "before": before,
                        "after": dict(st.__dict__),
                    })

    # ------------------------------------------------------------------ helpers
    def pressure_on(self, i: int) -> tuple[int, float]:
        return self.nearest(self.other(self.tid(i)), self.pos[i, 0], self.pos[i, 1])

    def att_xy(self, i: int | None = None) -> tuple[float, float]:
        team = self.poss if i is None else self.tid(i)
        return self.to_att(team, self.ball[0], self.ball[1])

    def change_possession(self, new_team: str, new_carrier: int | None, reason: str, at: tuple[float, float]) -> None:
        if new_team != self.poss:
            self.emit(EventType.POSSESSION_CHANGE, new_team, new_carrier, x=at[0], y=at[1], outcome=reason)
        self.poss = new_team
        self.carrier = new_carrier

    def receive(self, i: int, settle: float) -> None:
        """Receiver runs onto the ball; the ball rolls to meet them."""
        self.carrier = i
        elapsed = 0.0
        while True:
            b = (float(self.ball[0]), float(self.ball[1]))
            gap = math.hypot(self.pos[i, 0] - b[0], self.pos[i, 1] - b[1])
            if (elapsed >= settle and gap < 1.2) or elapsed > settle + 3.0:
                break
            self.advance(DT, roles_fn=lambda f, b=b: {i: b})
            elapsed += DT
        # take the touch: ball comes to the player's feet
        self.ball = np.array([self.pos[i, 0], self.pos[i, 1], 0.0])

    # ------------------------------------------------------------------ restarts
    def restart(self, kind: EventType, team: str, at: tuple[float, float], delay: float) -> None:
        self.ball = np.array([at[0], at[1], 0.0])
        taker = self._pick_taker(team, kind, at)
        if team != self.poss and kind != EventType.KICK_OFF:
            self.emit(EventType.POSSESSION_CHANGE, team, taker, x=at[0], y=at[1], outcome=kind.value)
        self.poss = team
        self.carrier = taker
        self.advance(delay, roles_fn=lambda f: {taker: at}, press=False, dead=True)
        extra = 0.0
        while math.hypot(*(self.pos[taker] - np.array(at))) > 1.5 and extra < 12.0:
            self.advance(DT, roles_fn=lambda f: {taker: at}, press=False, dead=True)
            extra += DT
        if kind == EventType.CORNER:
            self.emit(EventType.CORNER, team, taker, x=at[0], y=at[1])
            self.corner_delivery(taker)
        elif kind == EventType.FREE_KICK:
            ax, ay = self.att_xy(taker)
            dist = math.hypot(L - ax, GOAL_Y - ay)
            self.emit(EventType.FREE_KICK, team, taker, x=at[0], y=at[1], distance_to_goal=dist)
            if dist < 29 and abs(ay - GOAL_Y) < 20 and self.rng.random() < 0.45:
                self.shoot(taker, set_piece="direct_free_kick")
            else:
                self.pass_action(taker, restart="free_kick")
        elif kind == EventType.THROW_IN:
            self.emit(EventType.THROW_IN, team, taker, x=at[0], y=at[1])
            self.pass_action(taker, restart="throw_in")
        elif kind == EventType.GOAL_KICK:
            self.emit(EventType.GOAL_KICK, team, taker, x=at[0], y=at[1])
            self.pass_action(taker, restart="goal_kick")
        elif kind == EventType.KICK_OFF:
            self.emit(EventType.KICK_OFF, team, taker, x=at[0], y=at[1])
            self.pass_action(taker, restart="kick_off")

    def _pick_taker(self, team: str, kind: EventType, at: tuple[float, float]) -> int:
        squad = self.on_team(team)
        if kind == EventType.GOAL_KICK:
            return next((i for i in squad if self.role(i) == "GK"), squad[0])
        if kind == EventType.CORNER or kind == EventType.FREE_KICK:
            ranked = sorted((i for i in squad if self.role(i) != "GK"), key=lambda i: -self.roster[i].passing)
            return ranked[0] if self.rng.random() < 0.7 else ranked[1]
        if kind == EventType.KICK_OFF:
            fw = [i for i in squad if self.role(i) in {"ST", "AM", "CM"}]
            return fw[0] if fw else squad[-1]
        i, _ = self.nearest(team, at[0], at[1])
        if self.role(i) == "GK":
            i = sorted(squad, key=lambda j: math.hypot(*(self.pos[j] - at)))[1]
        return i

    # ------------------------------------------------------------------ actions
    def choose_and_act(self) -> None:
        i = self.carrier
        assert i is not None
        team = self.tid(i)
        st = self.style[team]
        pl = self.roster[i]
        ax, ay = self.att_xy(i)
        dg = math.hypot(L - ax, GOAL_Y - ay)
        opp, dp = self.pressure_on(i)
        in_box = ax > L - 16.5 and abs(ay - GOAL_Y) < 20.16

        w: dict[str, float] = {"pass": 1.0}
        if dg < 32 and self.role(i) != "GK":
            w["shot"] = 0.062 * math.exp(-(dg - 12) / 12.0) * (0.5 + pl.finishing) * (1.2 if in_box else 1.0)
        if dp > 5 and self.role(i) != "GK":
            w["carry"] = 0.42 * (0.6 + pl.dribbling) * (1.25 - st.tempo * 0.4)
        if dp < 3.2 and self.role(i) not in {"GK", "CB"}:
            w["dribble"] = 0.22 * pl.dribbling ** 2 * (1.4 if ax > 60 else 0.6)
        if ax > 80 and abs(ay - GOAL_Y) > 17:
            w["cross"] = 0.3 * (0.5 + st.width)
        if ax < 28 and dp < 2.5:
            w["clearance"] = 0.55
        keys = list(w)
        probs = np.array([w[k] for k in keys])
        action = keys[int(self.rng.choice(len(keys), p=probs / probs.sum()))]

        if dp < 3.0 and self.rng.random() < 0.35 + 0.4 * self.style[self.other(team)].press_intensity:
            pr = self.emit(EventType.PRESSURE, self.other(team), opp, x=self.pos[opp, 0], y=self.pos[opp, 1],
                           distance=dp, target=pl.id)
            if dp < 1.8 and self.rng.random() < 0.05 + 0.06 * self.style[self.other(team)].press_intensity:
                at = (float(self.ball[0]), float(self.ball[1]))
                foul = self.emit(EventType.FOUL, self.other(team), opp, x=at[0], y=at[1], related=[pr.id], victim=pl.id)
                self.card_check(opp, foul)
                self.restart(EventType.FREE_KICK, team, at, delay=float(self.rng.uniform(15, 30)))
                return

        if action == "pass":
            self.pass_action(i)
        elif action == "shot":
            self.shoot(i)
        elif action == "carry":
            self.carry(i)
        elif action == "dribble":
            self.take_on(i, opp)
        elif action == "cross":
            self.pass_action(i, cross=True)
        else:
            self.clearance(i)

    def _pass_candidates(self, i: int, cross: bool, restart: str | None) -> tuple[list[int], np.ndarray]:
        team = self.tid(i)
        st = self.style[team]
        ax, ay = self.att_xy(i)
        cands, scores = [], []
        for j in self.on_team(team):
            if j == i:
                continue
            jx, jy = self.to_att(team, *self.pos[j])
            d = math.hypot(jx - ax, jy - ay)
            if d < 4 or d > 58:
                continue
            if self.role(j) == "GK" and (ax > 45 or restart == "goal_kick"):
                continue
            fwd = jx - ax
            _, openness = self.nearest(self.other(team), *self.pos[j])
            s = 0.9 * min(openness, 9) / 9
            s += (0.35 + 1.1 * st.directness) * fwd / 25
            s -= 0.028 * max(0.0, d - 18) * (1.2 - st.directness)
            if cross:
                in_box = jx > L - 17 and abs(jy - GOAL_Y) < 16
                s += 2.2 if in_box else -2.0
            if restart == "goal_kick" and st.directness < 0.5:
                s += 0.8 if self.role(j) in BACK_LINE or self.role(j) == "DM" else -0.3
            if restart == "kick_off":
                s += 0.8 if fwd < 0 else -1.0
            if restart == "throw_in":
                s -= 0.15 * max(0.0, d - 15)
            cands.append(j)
            scores.append(s)
        return cands, np.array(scores)

    def pass_action(self, i: int, cross: bool = False, restart: str | None = None) -> None:
        team = self.tid(i)
        st = self.style[team]
        pl = self.roster[i]
        cands, scores = self._pass_candidates(i, cross, restart)
        if not cands:
            self.carry(i)
            return
        temp = 0.55
        p = np.exp((scores - scores.max()) / temp)
        j = cands[int(self.rng.choice(len(cands), p=p / p.sum()))]
        ax, ay = self.att_xy(i)
        jx, jy = self.to_att(team, *self.pos[j])
        _, dp = self.pressure_on(i)
        _, openness = self.nearest(self.other(team), *self.pos[j])
        fwd = jx - ax

        # where the ball is played: into the receiver's run
        lead = 0.0
        through = False
        if fwd > 8 and jx > 60 and not cross and self.rng.random() < 0.12 + 0.18 * st.directness:
            lead = float(self.rng.uniform(5, 11))
            through = True
        elif fwd > 0:
            lead = float(self.rng.uniform(0, 3))
        tx = min(jx + lead, L - 9.0 if through else L - 6.0)
        ty = min(max(jy + self.rng.normal(0, 1.2), 1), W - 1)
        if cross:
            tx = float(self.rng.uniform(L - 14, L - 4))
            ty = float(self.rng.uniform(GOAL_Y - 9, GOAL_Y + 9))
        d = math.hypot(tx - ax, ty - ay)
        lofted = cross or d > 32 or (restart == "goal_kick" and st.directness >= 0.5)
        switch = abs(ty - ay) > 30
        height = "high" if lofted else ("low" if d > 18 else "ground")

        into_box = tx > L - 16.5 and abs(ty - GOAL_Y) < 20.16
        z = 3.7 - 0.043 * d - 1.1 * into_box - 0.8 * (tx > L - 11) - 0.75 * (dp < 2.0) - 0.35 * (dp < 4.0) - 0.22 * max(0.0, 4.0 - openness)
        z += 2.2 * (pl.passing - 0.72) + 0.012 * max(0.0, -fwd) - 0.008 * max(0.0, fwd)
        z -= 0.7 * through + 1.4 * cross + 0.25 * switch
        z += 1.4 if restart in {"throw_in", "kick_off", "free_kick"} else 0.0
        opp_press = self.style[self.other(team)].press_intensity
        z -= 0.9 * max(0.0, opp_press - 0.45) * (ax < 50)
        p_ok = sigmoid(z)
        ok = self.rng.random() < p_ok

        speed = float(self.rng.uniform(17, 25) if lofted else self.rng.uniform(9, 17) + d * 0.08)
        start = (float(self.ball[0]), float(self.ball[1]))
        end_pitch = self.to_pitch(team, tx, ty)
        outcome = "complete"
        intercept_by: int | None = None
        offside = False
        out_kind: EventType | None = None
        if not ok:
            r = self.rng.random()
            if through and r < 0.28:
                offside = True
                outcome = "offside"
            elif dp < 2.2 and r < 0.35 and restart is None:
                outcome = "tackled"
            elif r < 0.84 or cross:
                # cut out by the nearest defender to the landing spot / passing lane
                f = float(self.rng.uniform(0.45, 1.0))
                mid = (start[0] + (end_pitch[0] - start[0]) * f, start[1] + (end_pitch[1] - start[1]) * f)
                intercept_by, _ = self.nearest(self.other(team), *mid)
                end_pitch = mid
                outcome = "intercepted" if self.rng.random() < 0.16 else "incomplete"
            else:
                outcome = "out"
                if tx > L - 8:
                    out_kind = EventType.GOAL_KICK
                    end_pitch = self.to_pitch(team, L, ty)
                else:
                    out_kind = EventType.THROW_IN
                    ox = min(max(tx + float(self.rng.normal(0, 3)), 1.0), L - 1.0)
                    end_pitch = self.to_pitch(team, ox, 0.0 if ty < GOAL_Y else W)

        if outcome == "tackled":
            opp, _ = self.pressure_on(i)
            self.duel(i, opp, None)
            return
        fn, dur = self.walk_ball(start, end_pitch, speed, z_peak=min(12.0, d * 0.16) if lofted else 0.0)
        ev = self.emit(
            EventType.PASS, team, i, x=start[0], y=start[1], end=end_pitch, outcome=outcome,
            receiver=j, pressure=dp < 3.0, height=height, cross=cross, through_ball=through, switch=switch,
            restart=restart, ball_speed_kmh=speed * 3.6, duration=dur, t_end=self._end_time(dur),
            length=d,
        )
        target_for = intercept_by if intercept_by is not None else j
        self.advance(dur, ball_fn=fn, roles_fn=lambda f: {target_for: end_pitch})

        if ok:
            if cross and self.rng.random() < 0.62:
                self.carrier = j
                self.ball = np.array([end_pitch[0], end_pitch[1], 1.8])
                self.shoot(j, header=True, assist=ev)
                return
            self.receive(j, float(self.rng.uniform(0.4, 1.6) * (1.3 - 0.5 * st.tempo)))
            return
        if cross and not offside and self.rng.random() < 0.14:
            corner = self.to_pitch(team, L - 0.5, 0.5 if ty < GOAL_Y else W - 0.5)
            self.restart(EventType.CORNER, team, corner, delay=float(self.rng.uniform(20, 32)))
            return
        if offside:
            self.emit(EventType.OFFSIDE, team, j, x=self.pos[j, 0], y=self.pos[j, 1], related=[ev.id])
            self.restart(EventType.FREE_KICK, self.other(team), (float(self.pos[j, 0]), float(self.pos[j, 1])),
                         delay=float(self.rng.uniform(12, 20)))
            return
        if intercept_by is not None:
            reason = "loose_ball"
            if outcome == "intercepted":
                self.emit(EventType.INTERCEPTION, self.other(team), intercept_by, x=end_pitch[0], y=end_pitch[1],
                          related=[ev.id])
                reason = "interception"
            self.change_possession(self.other(team), intercept_by, reason, end_pitch)
            self.receive(intercept_by, float(self.rng.uniform(0.3, 0.9)))
            return
        assert out_kind is not None
        at = end_pitch
        if out_kind == EventType.GOAL_KICK:
            at = self.to_pitch(self.other(team), 5.5, GOAL_Y + float(self.rng.choice([-9, 9])))
        self.restart(out_kind, self.other(team), at, delay=float(self.rng.uniform(8, 16)))

    def carry(self, i: int) -> None:
        team = self.tid(i)
        ax, ay = self.att_xy(i)
        length = float(self.rng.uniform(4, 14))
        ang = float(self.rng.normal(0, 0.55))
        tx = min(ax + length * math.cos(ang), L - 7)
        ty = min(max(ay + length * math.sin(ang) + (GOAL_Y - ay) * 0.1, 2), W - 2)
        end = self.to_pitch(team, tx, ty)
        start = (float(self.ball[0]), float(self.ball[1]))
        speed = float(self.rng.uniform(3.8, 6.2))
        fn, dur = self.walk_ball(start, end, speed)
        opp, dp = self.pressure_on(i)
        tackler_skill = self.roster[opp].tackling
        p_lose = 0.05 + (0.22 * (tackler_skill + 0.3 - self.roster[i].dribbling * 0.6) if dp < 3.0 else 0.0)
        p_lose += 0.18 if tx > L - 16.5 and abs(ty - GOAL_Y) < 20.16 else 0.0
        lose = self.rng.random() < max(0.02, p_lose)
        if lose:
            f = float(self.rng.uniform(0.3, 0.8))
            end = (start[0] + (end[0] - start[0]) * f, start[1] + (end[1] - start[1]) * f)
            fn, dur = self.walk_ball(start, end, speed)
        ev = self.emit(EventType.CARRY, team, i, x=start[0], y=start[1], end=end, pressure=dp < 3.0,
                       duration=dur, t_end=self._end_time(dur), length=math.hypot(end[0] - start[0], end[1] - start[1]))
        self.advance(dur, ball_fn=fn, attach=i)
        if lose:
            self.duel(i, opp, ev)

    def take_on(self, i: int, opp: int) -> None:
        team = self.tid(i)
        pl, df = self.roster[i], self.roster[opp]
        p_win = sigmoid(0.2 + 3.2 * (pl.dribbling - df.tackling))
        win = self.rng.random() < p_win
        start = (float(self.ball[0]), float(self.ball[1]))
        ax, ay = self.att_xy(i)
        end = self.to_pitch(team, min(ax + float(self.rng.uniform(3, 7)), L - 3), ay + float(self.rng.normal(0, 3)))
        end = (end[0], min(max(end[1], 1), W - 1))
        fn, dur = self.walk_ball(start, end if win else start, 5.0)
        ev = self.emit(EventType.DRIBBLE, team, i, x=start[0], y=start[1], end=end if win else None,
                       outcome="won" if win else "lost", pressure=True, opponent=df.id, duration=dur)
        self.advance(max(dur, 0.6), ball_fn=fn, attach=i)
        if not win:
            self.duel(i, opp, ev)

    def duel(self, carrier: int, opp: int, cause: MatchEvent | None) -> None:
        team = self.tid(carrier)
        dteam = self.other(team)
        at = (float(self.ball[0]), float(self.ball[1]))
        foul_p = 0.2 + 0.08 * self.style[dteam].press_intensity
        if self.rng.random() < foul_p:
            foul = self.emit(EventType.FOUL, dteam, opp, x=at[0], y=at[1], related=[cause.id] if cause else [], victim=self.roster[carrier].id)
            self.card_check(opp, foul)
            ax, _ = self.att_xy(carrier)
            in_box = ax > L - 16.5 and abs(self.att_xy(carrier)[1] - GOAL_Y) < 20.16
            if in_box and self.rng.random() < 0.2:
                self.penalty(team)
            else:
                self.restart(EventType.FREE_KICK, team, at, delay=float(self.rng.uniform(15, 30)))
            return
        self.emit(EventType.TACKLE, dteam, opp, x=at[0], y=at[1], outcome="won", related=[cause.id] if cause else [],
                  victim=self.roster[carrier].id)
        self.change_possession(dteam, opp, "tackle", at)
        self.receive(opp, float(self.rng.uniform(0.3, 0.8)))

    def card_check(self, i: int, foul: MatchEvent) -> None:
        if self.rng.random() < 0.13:
            if i in self.yellow:
                self.emit(EventType.CARD, self.tid(i), i, outcome="second_yellow", related=[foul.id])
                self.send_off(i)
            else:
                self.yellow.add(i)
                self.emit(EventType.CARD, self.tid(i), i, outcome="yellow", related=[foul.id])
        elif self.rng.random() < 0.004:
            self.emit(EventType.CARD, self.tid(i), i, outcome="red", related=[foul.id])
            self.send_off(i)

    def send_off(self, i: int) -> None:
        team = self.tid(i)
        was_keeper = self.role(i) == "GK"
        self.on[i] = False
        self.gone.add(i)
        self._refresh_on()
        if self.carrier == i:
            self.carrier = None
        self.truth.append({"type": "red_card", "t": round(self.t, 1), "player": self.roster[i].id})
        if was_keeper:
            self._replace_keeper(team, self.slot[i])

    def _replace_keeper(self, team: str, gk_slot: int) -> None:
        bench_gk = [j for j in range(self.N) if self.tid(j) == team and not self.on[j] and j not in self.gone
                    and self.roster[j].position == "GK"]
        outfield = [j for j in self.on_team(team) if j != self.carrier]
        if bench_gk and self.subs_made[team] < 5 and outfield:
            off = min(outfield, key=lambda j: self.energy[j])
            inc = bench_gk[0]
            self.on[off], self.on[inc] = False, True
            self.gone.add(off)
            self.slot[inc] = gk_slot
            self.pos[inc] = self.to_pitch(team, 5.0, GOAL_Y)
            self.vel[inc] = 0.0
            self.subs_made[team] += 1
            self._refresh_on()
            self.emit(EventType.SUBSTITUTION, team, inc, outcome="on", replaced=self.roster[off].id, forced=True)
        elif outfield:
            stand_in = max(outfield, key=lambda j: self.roster[j].aerial)
            self.slot[stand_in] = gk_slot
            self.truth.append({"type": "emergency_keeper", "t": round(self.t, 1), "player": self.roster[stand_in].id})

    def clearance(self, i: int) -> None:
        team = self.tid(i)
        ax, ay = self.att_xy(i)
        tx = float(self.rng.uniform(55, 80))
        ty = float(self.rng.uniform(5, W - 5))
        end = self.to_pitch(team, tx, ty)
        start = (float(self.ball[0]), float(self.ball[1]))
        fn, dur = self.walk_ball(start, end, float(self.rng.uniform(20, 27)), z_peak=12)
        self.emit(EventType.CLEARANCE, team, i, x=start[0], y=start[1], end=end, pressure=True,
                  ball_speed_kmh=float(self.rng.uniform(70, 95)), duration=dur, t_end=self._end_time(dur))
        self.advance(dur, ball_fn=fn)
        # 50/50 for the second ball
        a, da = self.nearest(team, *end)
        b, db = self.nearest(self.other(team), *end)
        win_team, winner = (team, a) if (da - db + self.rng.normal(0, 4)) < 0 else (self.other(team), b)
        self.change_possession(win_team, winner, "second_ball", end)
        self.receive(winner, float(self.rng.uniform(0.6, 1.4)))

    def corner_delivery(self, taker: int) -> None:
        team = self.tid(taker)
        start = (float(self.ball[0]), float(self.ball[1]))
        tx = float(self.rng.uniform(L - 12, L - 4))
        ty = float(self.rng.uniform(GOAL_Y - 8, GOAL_Y + 8))
        end = self.to_pitch(team, tx, ty)
        fn, dur = self.walk_ball(start, end, float(self.rng.uniform(19, 25)), z_peak=6)
        att = sorted((j for j in self.on_team(team) if j != taker and self.role(j) != "GK"),
                     key=lambda j: -self.roster[j].aerial)[:4]
        defn = sorted(self.on_team(self.other(team)), key=lambda j: -self.roster[j].aerial)[:4]
        a = att[int(self.rng.integers(len(att)))]
        d = defn[int(self.rng.integers(len(defn)))]
        p_att = sigmoid(-0.55 + 2.6 * (self.roster[a].aerial - self.roster[d].aerial))
        ev = self.emit(EventType.PASS, team, taker, x=start[0], y=start[1], end=end, outcome="complete",
                       receiver=a, height="high", cross=True, restart="corner", ball_speed_kmh=80.0,
                       duration=dur, t_end=self._end_time(dur), length=math.hypot(end[0] - start[0], end[1] - start[1]))
        self.advance(dur, ball_fn=fn, roles_fn=lambda f: {a: end, d: end})
        if self.rng.random() < p_att:
            self.carrier = a
            self.shoot(a, header=True, assist=ev)
        else:
            ev.outcome = "cleared"
            self.carrier = d
            self.poss = self.other(team)
            self.emit(EventType.CLEARANCE, self.other(team), d, x=end[0], y=end[1], outcome="headed_clear",
                      related=[ev.id])
            self.change_possession(self.other(team), d, "clearance", end)
            self.clearance(d)

    def penalty(self, team: str) -> None:
        taker = max(self.on_team(team), key=lambda j: self.roster[j].finishing)
        spot = self.to_pitch(team, L - 11, GOAL_Y)
        self.ball = np.array([spot[0], spot[1], 0.0])
        self.advance(float(self.rng.uniform(40, 70)), roles_fn=lambda f: {taker: spot}, press=False, dead=True)
        self.carrier = taker
        self.poss = team
        self.shoot(taker, set_piece="penalty")

    def shoot(self, i: int, header: bool = False, set_piece: str | None = None, assist: MatchEvent | None = None) -> None:
        team = self.tid(i)
        pl = self.roster[i]
        ax, ay = self.att_xy(i)
        dx, dy = L - ax, abs(GOAL_Y - ay)
        dist = math.hypot(dx, dy)
        ang = goal_angle(dx, dy)
        _, dp = self.pressure_on(i)
        defenders_goal_side = sum(
            1 for j in self.on_team(self.other(team))
            if self.to_att(team, *self.pos[j])[0] > ax and self.role(j) != "GK"
        )
        big = set_piece is None and not header and dist < 12 and defenders_goal_side == 0
        xg = 0.76 if set_piece == "penalty" else true_xg(dist, ang, header, dp < 2.0, big)
        if set_piece == "direct_free_kick":
            xg = min(xg, 0.07)
        mod = 0.8 + 0.36 * pl.finishing
        u = self.rng.random()
        if u < xg * mod:
            outcome = "goal"
        else:
            r = self.rng.random()
            outcome = "blocked" if (r < 0.26 and set_piece != "penalty") else ("saved" if r < 0.6 else "off_target")
        speed_kmh = float(np.clip(
            (48 + self.rng.normal(0, 6)) if header else (78 + 1.25 * dist + self.rng.normal(0, 9)), 38, 132))
        gx, gy = self.to_pitch(team, L, GOAL_Y + float(self.rng.normal(0, 2.2)))
        if outcome == "off_target":
            gy = gy + float(self.rng.choice([-1, 1])) * float(self.rng.uniform(4, 9))
        start = (float(self.ball[0]), float(self.ball[1]))
        end = (gx, gy)
        if outcome == "blocked":
            end = (start[0] + (gx - start[0]) * 0.18, start[1] + (gy - start[1]) * 0.18)
        fn, dur = self.walk_ball(start, end, speed_kmh / 3.6, z_peak=1.4 if not header else 2.4)
        ev = self.emit(
            EventType.SHOT, team, i, x=start[0], y=start[1], end=end, outcome=outcome, pressure=dp < 2.0,
            body_part="head" if header else "foot", set_piece=set_piece, shot_speed_kmh=speed_kmh,
            duration=dur, t_end=self._end_time(dur), related=[assist.id] if assist else [],
            assist_player=assist.player if assist else None,
        )
        self.truth.append({"type": "shot", "event": ev.id, "t": round(self.t, 1), "true_xg": round(xg, 4),
                           "big_chance": big})
        self.advance(dur, ball_fn=fn)
        dteam = self.other(team)
        gk = next((j for j in self.on_team(dteam) if self.role(j) == "GK"), None)
        if outcome == "goal":
            self.score[team] += 1
            self.emit(EventType.GOAL, team, i, x=start[0], y=start[1], related=[ev.id], t=max(self.t, ev.qualifiers["t_end"]),
                      score=f"{self.score[self.home.id]}-{self.score[self.away.id]}",
                      assist_player=self._last_passer(team, i))
            self.ball = np.array([gx, gy, 0.0])
            self.advance(float(self.rng.uniform(8, 14)), press=False, dead=True)
            self.ball = np.array([L / 2, W / 2, 0.0])
            self.kickoff_mode = True
            self.advance(float(self.rng.uniform(35, 55)), press=False, dead=True)
            self.kickoff_mode = False
            self.restart(EventType.KICK_OFF, dteam, (L / 2, W / 2), delay=2.0)
            return
        if outcome == "saved" and gk is not None:
            self.emit(EventType.SAVE, dteam, gk, x=end[0], y=end[1], related=[ev.id], shot_speed_kmh=speed_kmh,
                      t=max(self.t, ev.qualifiers["t_end"]))
            r = self.rng.random()
            if r < 0.33:
                corner = self.to_pitch(team, L - 0.5, 0.5 if self.rng.random() < 0.5 else W - 0.5)
                self.restart(EventType.CORNER, team, corner, delay=float(self.rng.uniform(20, 32)))
            elif r < 0.5:
                # parried into the box: rebound
                reb = self.to_pitch(team, L - float(self.rng.uniform(6, 13)), GOAL_Y + float(self.rng.normal(0, 7)))
                a, da = self.nearest(team, *reb)
                b, db = self.nearest(dteam, *reb)
                fn2, d2 = self.walk_ball(end, reb, 9.0)
                self.advance(d2, ball_fn=fn2)
                if da + self.rng.normal(0, 2) < db:
                    self.carrier, self.poss = a, team
                    self.shoot(a)
                else:
                    self.change_possession(dteam, b, "rebound", reb)
                    self.receive(b, 0.6)
            else:
                self.change_possession(dteam, gk, "save", end)
                self.ball = np.array([self.pos[gk, 0], self.pos[gk, 1], 0.0])
                self.receive(gk, float(self.rng.uniform(3, 7)))
            return
        if outcome == "blocked":
            if self.rng.random() < 0.38:
                corner = self.to_pitch(team, L - 0.5, 0.5 if self.rng.random() < 0.5 else W - 0.5)
                self.restart(EventType.CORNER, team, corner, delay=float(self.rng.uniform(20, 32)))
            else:
                b, _ = self.nearest(dteam, *end)
                self.change_possession(dteam, b, "block", end)
                self.receive(b, 0.6)
            return
        gk_spot = self.to_pitch(dteam, 5.5, GOAL_Y + float(self.rng.choice([-9, 9])))
        self.restart(EventType.GOAL_KICK, dteam, gk_spot, delay=float(self.rng.uniform(16, 28)))

    def _last_passer(self, team: str, scorer: int) -> str | None:
        for ev in reversed(self.events[-8:]):
            if ev.type == EventType.PASS and ev.team == team and ev.outcome == "complete" and ev.receiver == self.roster[scorer].id:
                return ev.player
            if ev.type == EventType.POSSESSION_CHANGE:
                break
        return None

    # ------------------------------------------------------------------ substitutions
    def maybe_subs(self) -> None:
        period, minute, _, _ = self.clock()
        if period != 2 or minute < 56:
            return
        for team in (self.home, self.away):
            made = self.subs_made[team.id]
            if made >= 5:
                continue
            window = 56 + made * 7
            if minute < window or self.rng.random() > 0.25:
                continue
            out_pool = [i for i in self.on_team(team.id) if self.role(i) != "GK" and i != self.carrier]
            bench = [i for i in range(self.N) if self.tid(i) == team.id and not self.roster[i].starting
                     and not self.on[i] and i not in self.gone and self.roster[i].position != "GK"]
            if not out_pool or not bench:
                continue
            trailing = self.score[team.id] < self.score[self.other(team.id)]
            out = min(out_pool, key=lambda i: self.energy[i] - (0.05 if self.role(i) in {"ST", "LW", "RW"} and trailing else 0))
            pref = {"ST", "LW", "RW"} if trailing else {self.roster[out].position}
            inc = next((b for b in bench if self.roster[b].position in pref), bench[0])
            self.on[out] = False
            self.on[inc] = True
            self.gone.add(out)
            self.slot[inc] = self.slot[out]
            self.pos[inc] = self.to_pitch(team.id, 52.5, 0.5)
            self.vel[inc] = 0.0
            self._refresh_on()
            self.subs_made[team.id] += 1
            self.emit(EventType.SUBSTITUTION, team.id, inc, outcome="on", replaced=self.roster[out].id)

    # ------------------------------------------------------------------ main loop
    def run(self) -> SimResult:
        self.stoppage[0] = float(self.rng.uniform(1.0, 4.0)) * 60
        self.restart(EventType.KICK_OFF, self.home.id, (L / 2, W / 2), delay=1.0)
        self._play_until(HALF + self.stoppage[0])
        self.emit(EventType.HALF_TIME, outcome=f"{self.score[self.home.id]}-{self.score[self.away.id]}")
        self.period = 2
        self.t += 15 * 60
        self.p2_start = self.t
        self.ball = np.array([L / 2, W / 2, 0.0])
        self._place_kickoff_shape()
        self.emit(EventType.SECOND_HALF)
        self.restart(EventType.KICK_OFF, self.away.id, (L / 2, W / 2), delay=1.0)
        goals = sum(self.score.values())
        self.stoppage[1] = float(min(9.0, self.rng.uniform(3.0, 5.5) + 0.4 * goals)) * 60
        self._play_until(self.p2_start + HALF + self.stoppage[1])
        self.emit(EventType.FULL_TIME, outcome=f"{self.score[self.home.id]}-{self.score[self.away.id]}")
        return self._result()

    def _play_until(self, t_end: float) -> None:
        while self.t < t_end:
            if self.carrier is None or not self.on[self.carrier]:
                i, _ = self.nearest(self.poss, self.ball[0], self.ball[1])
                self.carrier = i
                self.receive(i, 0.6)
            self.choose_and_act()
            self.maybe_subs()

    def _result(self) -> SimResult:
        info = self._info()
        pos = np.stack(self._fp)
        return SimResult(
            info=info,
            events=self.events,
            frame_t=np.array(self._ft, dtype=np.float32),
            frame_ball=np.array(self._fb, dtype=np.float32),
            frame_pos=pos,
            truth=self.truth,
            summary={
                "score": dict(self.score),
                "distance_km": {p.id: round(float(self.dist[i]) / 1000, 2) for i, p in enumerate(self.roster)},
                "duration_s": round(self.t, 1),
            },
        )

    def _info(self) -> MatchInfo:
        def team_info(t: Team) -> TeamInfo:
            return TeamInfo(
                id=t.id, name=t.name, short_name=t.short_name, abbr=t.abbr, primary=t.primary,
                secondary=t.secondary, formation=t.formation, style=t.style_label,
                players=[PlayerInfo(
                    id=p.id, name=p.name, short_name=p.short_name, number=p.number, position=p.position,
                    nationality=p.nationality, age=p.age, starting=p.starting, top_speed_kmh=p.top_speed_kmh,
                ) for p in t.players],
            )

        kickoff = datetime(2026, 10, 24, 14, 0, tzinfo=UTC) + timedelta(days=int(self.seed % 7))
        venues = ["Harrow Lane", "The Calder Dock", "Millbank Park", "Kestrel Fields"]
        refs = ["Alex Morrow", "Priya Raman", "Tomasz Wilk", "Grace Adeyinka"]
        weather = ["Clear, 14°C", "Light rain, 11°C", "Overcast, 12°C", "Windy, 9°C"]
        return MatchInfo(
            match_id=self.match_id,
            competition="Regista Synthetic League · Matchday 9",
            venue=venues[self.seed % len(venues)],
            kickoff_utc=kickoff.isoformat(),
            referee=refs[self.seed % len(refs)],
            weather=weather[(self.seed // 3) % len(weather)],
            seed=self.seed,
            home=team_info(self.home),
            away=team_info(self.away),
            roster=[p.id for p in self.roster],
        )


def simulate(home: str = "NOR", away: str = "CAL", seed: int = 7, scenario: str = "derby") -> SimResult:
    return MatchSimulator(home, away, seed, scenario).run()
