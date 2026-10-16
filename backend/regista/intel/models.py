"""Interpretable models used by the Interpret stage.

Each model is a small closed-form formula on purpose: every number it
produces can be decomposed into named factors, which is what the Explain
stage needs to say *why* something matters rather than just *that* it did.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..schema.events import PITCH_LENGTH as L
from ..schema.events import PITCH_WIDTH as W

GOAL_Y = W / 2


def sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


@dataclass
class Factor:
    label: str
    value: float
    effect: float  # contribution in logit space (or percentage points)
    detail: str = ""

    def as_dict(self) -> dict:
        return {"label": self.label, "value": round(self.value, 2), "effect": round(self.effect, 3), "detail": self.detail}


# ---------------------------------------------------------------------- xG
def shot_geometry(ax: float, ay: float) -> tuple[float, float]:
    dx, dy = L - ax, abs(GOAL_Y - ay)
    dist = math.hypot(dx, dy)
    angle = abs(math.atan2(3.66 - dy, dx) - math.atan2(-3.66 - dy, dx))
    return dist, angle


def expected_goals(ax: float, ay: float, header: bool, under_pressure: bool, set_piece: str | None
                   ) -> tuple[float, list[Factor]]:
    """Location-based xG with explicit factors. Coefficients fitted on synthetic league seasons."""
    if set_piece == "penalty":
        return 0.76, [Factor("Penalty", 1, 0, "Penalties are converted roughly three times in four")]
    dist, angle = shot_geometry(ax, ay)
    factors = [
        Factor("Base", 1, -1.5),
        Factor("Distance", dist, -0.098 * dist, f"{dist:.0f} m from goal"),
        Factor("Angle", math.degrees(angle), 1.22 * angle, f"{math.degrees(angle):.0f}° of goal visible"),
    ]
    if header:
        factors.append(Factor("Header", 1, -0.95, "Headed attempts convert far less often"))
    if under_pressure:
        factors.append(Factor("Under pressure", 1, -0.3, "A defender within two metres"))
    if set_piece == "direct_free_kick":
        factors.append(Factor("Direct free kick", 1, -0.9, "Wall and keeper set"))
    z = sum(f.effect for f in factors)
    return sigmoid(z), factors


# ---------------------------------------------------------------------- pass difficulty
def pass_difficulty(length: float, under_pressure: bool, forward_m: float, into_box: bool, cross: bool,
                    through: bool, height: str, receiver_space: float | None) -> tuple[float, list[Factor]]:
    """Probability the pass FAILS, as a 0-100 difficulty rating with factors.

    A completed pass with difficulty 80 means 4 in 5 attempts like it fail -
    which is exactly the kind of context a casual viewer cannot see.
    """
    factors = [
        Factor("Base", 1, 3.4),
        Factor("Length", length, -0.045 * length, f"{length:.0f} m"),
    ]
    if under_pressure:
        factors.append(Factor("Passer under pressure", 1, -0.8, "Opponent closing within 3 m"))
    if forward_m > 0:
        factors.append(Factor("Forward progress", forward_m, -0.012 * forward_m, f"{forward_m:.0f} m forward"))
    if into_box:
        factors.append(Factor("Into the box", 1, -1.1, "Penalty area is the most crowded zone"))
    if cross:
        factors.append(Factor("Cross", 1, -1.3, "Crosses are completed about one time in four"))
    if through:
        factors.append(Factor("Through ball", 1, -0.7, "Played into space behind the line"))
    if height == "high" and not cross:
        factors.append(Factor("Lofted", 1, -0.3, "Aerial delivery"))
    if receiver_space is not None and receiver_space < 4:
        factors.append(Factor("Tight marking", receiver_space, -0.22 * (4 - receiver_space),
                              f"Receiver had {receiver_space:.1f} m of space"))
    z = sum(f.effect for f in factors)
    p_complete = sigmoid(z)
    return round(100 * (1 - p_complete), 1), factors


# ---------------------------------------------------------------------- win probability
def _poisson(k: int, mu: float) -> float:
    return math.exp(-mu) * mu ** k / math.factorial(k)


def win_probability(score_home: int, score_away: int, minutes_left: float, rate_home: float, rate_away: float
                    ) -> tuple[float, float, float]:
    """P(home win), P(draw), P(away win) from independent Poisson goal processes."""
    mh = max(0.0, rate_home * minutes_left)
    ma = max(0.0, rate_away * minutes_left)
    ph = [_poisson(k, mh) for k in range(10)]
    pa = [_poisson(k, ma) for k in range(10)]
    win = draw = loss = 0.0
    for i, a in enumerate(ph):
        for j, b in enumerate(pa):
            diff = (score_home + i) - (score_away + j)
            p = a * b
            if diff > 0:
                win += p
            elif diff == 0:
                draw += p
            else:
                loss += p
    tot = win + draw + loss
    return win / tot, draw / tot, loss / tot
