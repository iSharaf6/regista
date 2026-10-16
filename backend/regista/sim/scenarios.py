"""Scripted storylines.

A scenario injects tactical changes at known minutes. Because the engine logs
each change to the hidden ground-truth file, we can later check whether the
Interpret stage *detected* the change from the data alone, and how fast.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class TacticalShift:
    minute: int
    team: Literal["home", "away"]
    changes: dict[str, float]
    label: str
    when: Literal["always", "trailing", "leading", "not_winning"] = "always"
    window: int = 15


@dataclass
class Scenario:
    name: str
    description: str
    shifts: list[TacticalShift] = field(default_factory=list)
    auto_adapt: bool = True


SCENARIOS: dict[str, Scenario] = {
    "derby": Scenario(
        name="derby",
        description=(
            "Home side switch to an all-out high press around the hour if they are not winning; "
            "the away side drop into a low block late on if they lead."
        ),
        shifts=[
            TacticalShift(
                0, "home", {"press_intensity": 0.5, "line_height": 0.55},
                "Start in a cautious mid-block", window=1,
            ),
            TacticalShift(
                58, "home", {"press_intensity": 0.98, "line_height": 0.92, "tempo": 0.84},
                "Switch to an all-out high press", when="not_winning",
            ),
            TacticalShift(
                74, "away", {"line_height": 0.2, "press_intensity": 0.12, "directness": 0.84},
                "Drop into a low block and go direct", when="leading",
            ),
        ],
    ),
    "press": Scenario(
        name="press",
        description="Home side flip from a mid-block to a high press at 30' regardless of the score.",
        shifts=[
            TacticalShift(0, "home", {"press_intensity": 0.5, "line_height": 0.55}, "Start in a cautious mid-block", window=1),
            TacticalShift(
                30, "home", {"press_intensity": 0.98, "line_height": 0.92, "tempo": 0.84},
                "Switch to an all-out high press",
            ),
        ],
        auto_adapt=False,
    ),
    "baseline": Scenario(name="baseline", description="No scripted changes; teams never adapt.", auto_adapt=False),
}


def get_scenario(name: str) -> Scenario:
    try:
        return SCENARIOS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown scenario {name!r}; choose from {sorted(SCENARIOS)}") from exc
