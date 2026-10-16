"""Windowed match signals: control vs chaos, pressing regimes and game rhythm.

These are the explainability primitives. Each returns the number *and* the
named inputs that produced it, compared against a league reference computed
from 20 simulated matches (see `regista calibrate`), so an agent can say
"chaotic because turnovers are running at twice the league rate" rather
than "the chaos index is -62".
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .state import MatchState

# League reference per 5-minute window (mean, std), produced by `regista calibrate`.
REFERENCE = {
    "pass_completion": (0.79, 0.07),
    "turnovers_per_min": (3.2, 1.0),
    "passes_per_possession": (4.2, 1.6),
    "duels_per_min": (1.25, 0.6),
    "pressures_high_per_min": (0.85, 0.5),
}


def _window(state: MatchState, team: str | None, metric: str, end: int, size: int) -> float:
    lo = max(0, end - size + 1)
    if team is None:
        return float(sum(state.bins[t][metric][lo:end + 1].sum() for t in (state.home, state.away)))
    return float(state.bins[team][metric][lo:end + 1].sum())


def _z(name: str, value: float) -> float:
    mu, sd = REFERENCE[name]
    return (value - mu) / sd


def control_chaos(state: MatchState, minute: int, size: int = 5) -> dict[str, Any]:
    lo = max(0, minute - size + 1)
    span = max(1, minute - lo + 1)
    passes = _window(state, None, "passes", minute, size)
    comp = _window(state, None, "passes_complete", minute, size)
    changes = float(state.match_bins["possession_changes"][lo:minute + 1].sum())
    duels = _window(state, None, "duels", minute, size)
    pc = comp / passes if passes else REFERENCE["pass_completion"][0]
    tpm = changes / span
    ppp = passes / max(1.0, changes)
    dpm = duels / span
    feats = [
        ("Pass completion", pc, _z("pass_completion", pc), +1, f"{pc * 100:.0f}% (league {REFERENCE['pass_completion'][0] * 100:.0f}%)"),
        ("Turnovers per minute", tpm, _z("turnovers_per_min", tpm), -1, f"{tpm:.1f} (league {REFERENCE['turnovers_per_min'][0]:.1f})"),
        ("Passes per possession", ppp, _z("passes_per_possession", ppp), +1, f"{ppp:.1f} (league {REFERENCE['passes_per_possession'][0]:.1f})"),
        ("Duels per minute", dpm, _z("duels_per_min", dpm), -1, f"{dpm:.1f} (league {REFERENCE['duels_per_min'][0]:.1f})"),
    ]
    score = sum(sign * z for _, _, z, sign, _ in feats) / 2.2
    index = round(100 * math.tanh(score), 1)
    label = "control" if index >= 35 else ("chaos" if index <= -35 else "balanced")
    poss = {t: _window(state, t, "possession_s", minute, size) for t in (state.home, state.away)}
    tot = sum(poss.values()) or 1.0
    share = {t: poss[t] / tot for t in poss}
    controller = max(share, key=share.get) if label == "control" else None
    factors = sorted(
        ({"label": n, "value": round(v, 2), "z": round(z, 2), "pushes": "control" if sign * z > 0 else "chaos", "detail": d}
         for n, v, z, sign, d in feats),
        key=lambda f: -abs(f["z"]),
    )
    return {
        "clock": state.clock_at(minute),
        "index": index,
        "label": label,
        "controller": controller,
        "possession_share": {t: round(100 * s, 1) for t, s in share.items()},
        "factors": factors,
    }


def press_series(state: MatchState, team: str, upto: int) -> tuple[np.ndarray, np.ndarray]:
    """Per-minute pressing actions and pressing *opportunities*.

    Actions: pressures and defensive actions in the opponent's half.
    Opportunities: opponent passes from their own 60% of the pitch.
    The ratio is game-state neutral - a team that only presses more because
    the opponent keeps the ball deeper does not look like it changed plan.
    """
    b = state.bins[team]
    actions = (b["pressures_high"][: upto + 1] + b["def_actions_high"][: upto + 1]).astype(float)
    opps = b["opp_passes_own60"][: upto + 1].astype(float)
    return actions, opps


def ppda(state: MatchState, team: str, minute: int, size: int) -> float:
    opp_passes = _window(state, team, "opp_passes_own60", minute, size)
    actions = _window(state, team, "def_actions_high", minute, size)
    return round(opp_passes / max(1.0, actions), 1)


def closing_series(state: MatchState, team: str, upto: int) -> np.ndarray:
    """Per-minute mean distance (m) of the two nearest defenders to the ball in the opponent's build-up."""
    b = state.bins[team]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(b["press_frames"][: upto + 1] >= 5, b["press_dist_sum"][: upto + 1] / b["press_frames"][: upto + 1], np.nan)


def shape_series(state: MatchState, team: str, upto: int) -> tuple[np.ndarray, np.ndarray]:
    """Per-minute tracking metrics: players within 8 m of the ball in the opponent's build-up,
    and defensive line height (metres from own goal). NaN where there was too little data."""
    b = state.bins[team]
    with np.errstate(invalid="ignore", divide="ignore"):
        near = np.where(b["press_frames"][: upto + 1] >= 5, b["press_near_sum"][: upto + 1] / b["press_frames"][: upto + 1], np.nan)
        line = np.where(b["line_frames"][: upto + 1] >= 5, b["line_sum"][: upto + 1] / b["line_frames"][: upto + 1], np.nan)
    return near, line


def _change_point(series: np.ndarray, min_seg: int = 3) -> int:
    """Index where a two-segment piecewise-constant fit has the lowest squared error."""
    x = np.nan_to_num(series, nan=float(np.nanmean(series)) if np.any(~np.isnan(series)) else 0.0)
    best, best_k = float("inf"), len(x) // 2
    for k in range(min_seg, len(x) - min_seg + 1):
        a, b = x[:k], x[k:]
        sse = float(((a - a.mean()) ** 2).sum() + ((b - b.mean()) ** 2).sum())
        if sse < best:
            best, best_k = sse, k
    return best_k


@dataclass
class RegimeDetector:
    """Detects sustained changes in how hard a team presses, from tracking data.

    Compares the mean players-near-ball in the opponent's build-up over a
    recent window against a baseline window (z-test on per-minute means),
    requires the change to persist, then estimates onset with a CUSUM.
    """

    recent: int = 5
    baseline: int = 20
    ratio: float = 1.2
    z_min: float = 3.0
    persist: int = 2
    cooldown: int = 15

    def __post_init__(self) -> None:
        self.last_fire: dict[str, int] = {}
        self.streak: dict[str, int] = {}

    def check(self, state: MatchState, team: str, minute: int) -> dict[str, Any] | None:
        if minute < self.recent + 10:
            return None
        if minute - self.last_fire.get(team, -999) < self.cooldown:
            return None
        near, line = shape_series(state, team, minute)
        close = closing_series(state, team, minute)
        lo = max(0, minute - self.recent - self.baseline + 1)
        cut = minute - self.recent + 1
        base, rec = near[lo:cut], near[cut:]
        base, rec = base[~np.isnan(base)], rec[~np.isnan(rec)]
        cbase, crec = close[lo:cut], close[cut:]
        cbase, crec = cbase[~np.isnan(cbase)], crec[~np.isnan(crec)]
        lbase, lrec = line[lo:cut], line[cut:]
        lbase, lrec = lbase[~np.isnan(lbase)], lrec[~np.isnan(lrec)]
        if len(base) < 6 or len(rec) < 3 or len(lbase) < 6 or len(lrec) < 3:
            return None
        mb, mr = float(base.mean()), float(rec.mean())
        if len(cbase) < 3 or len(crec) < 2:
            return None
        cb, cr = float(cbase.mean()), float(crec.mean())
        z_near = (mr - mb) / (max(float(base.std(ddof=1)), 0.12) / math.sqrt(len(rec)))
        lb, lr = float(lbase.mean()), float(lrec.mean())
        z_line = (lr - lb) / (max(float(lbase.std(ddof=1)), 1.5) / math.sqrt(len(lrec)))
        z = (z_near + z_line) / math.sqrt(2)
        up = z >= self.z_min and (mr >= mb * self.ratio or lr - lb >= 4.0)
        down = z <= -self.z_min and (mr <= mb / self.ratio or lb - lr >= 4.0)
        if not (up or down):
            self.streak[team] = 0
            return None
        self.streak[team] = self.streak.get(team, 0) + 1
        if self.streak[team] < self.persist:
            return None
        onset = _change_point(near[lo:] / max(mb, 0.1) + line[lo:] / max(lb, 1.0)) + lo
        line_before, line_after = lb, lr
        act, opp = press_series(state, team, minute)
        rate_b = 100 * act[lo:cut].sum() / max(1.0, opp[lo:cut].sum())
        rate_r = 100 * act[cut:].sum() / max(1.0, opp[cut:].sum())
        self.last_fire[team] = minute
        return {
            "type": "press_shift",
            "team": team,
            "direction": "up" if up else "down",
            "detected_index": minute,
            "onset_index": onset,
            "detected_clock": state.clock_at(minute),
            "onset_clock": state.clock_at(onset),
            "z_score": round(z, 2),
            "z_press": round(z_near, 2),
            "z_line": round(z_line, 2),
            "players_near_ball_before": round(mb, 2),
            "players_near_ball_after": round(mr, 2),
            "change_pct": round(100 * (mr - mb) / max(mb, 0.1), 0),
            "closing_distance_before_m": round(cb, 1),
            "closing_distance_after_m": round(cr, 1),
            "line_height_before_m": None if line_before is None else round(line_before, 1),
            "line_height_after_m": None if line_after is None else round(line_after, 1),
            "press_rate_before": round(rate_b, 1),
            "press_rate_after": round(rate_r, 1),
            "ppda_before": ppda(state, team, minute - self.recent, self.baseline),
            "ppda_after": ppda(state, team, minute, self.recent),
            "high_regains_recent": int(_window(state, team, "regains_high", minute, self.recent)),
        }


def rhythm(state: MatchState, minute: int, size: int = 8) -> dict[str, Any]:
    teams = (state.home, state.away)
    shots = {t: _window(state, t, "shots", minute, size) for t in teams}
    xg = {t: _window(state, t, "xg", minute, size) for t in teams}
    ft = {t: _window(state, t, "final_third", minute, size) for t in teams}
    poss = {t: _window(state, t, "possession_s", minute, size) for t in teams}
    tot_ft = sum(ft.values()) or 1.0
    tot_poss = sum(poss.values()) or 1.0
    tilt = {t: ft[t] / tot_ft for t in teams}
    share = {t: poss[t] / tot_poss for t in teams}
    span = max(1, min(size, minute + 1))
    tpm = float(state.match_bins["possession_changes"][max(0, minute - size + 1): minute + 1].sum()) / span
    lead = max(teams, key=lambda t: tilt[t])
    if tilt[lead] >= 0.7 and shots[lead] >= 2:
        label, team = "siege", lead
    elif min(shots.values()) >= 2 and tpm >= 3.4:
        label, team = "end_to_end", None
    elif max(share.values()) >= 0.64 and xg[max(share, key=share.get)] < 0.15:
        label, team = "sterile_possession", max(share, key=share.get)
    elif sum(shots.values()) == 0 and tpm < 3.2:
        label, team = "cagey", None
    else:
        label, team = "balanced", None
    return {
        "clock": state.clock_at(minute),
        "label": label,
        "team": team,
        "field_tilt": {t: round(100 * v, 1) for t, v in tilt.items()},
        "possession_share": {t: round(100 * v, 1) for t, v in share.items()},
        "shots": {t: int(v) for t, v in shots.items()},
        "xg": {t: round(v, 2) for t, v in xg.items()},
        "turnovers_per_min": round(tpm, 2),
    }
