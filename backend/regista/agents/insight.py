"""Deterministic insight builder: the Analyst's grounded fallback."""

from __future__ import annotations

from typing import Any

from .templates import Names

KEY_FACTS = {
    "goal": ("xg", "wp_swing", "shot_speed_kmh", "distance_m"),
    "big_chance": ("xg", "shot_speed_kmh", "distance_m", "team_xg"),
    "thunderbolt": ("shot_speed_kmh", "distance_m"),
    "master_pass": ("difficulty", "length_m", "opponents_bypassed", "ball_speed_kmh", "passer_accuracy"),
    "press_shift": ("players_near_ball_before", "players_near_ball_after", "line_height_before_m", "line_height_after_m", "z_score"),
    "control_chaos": ("index",),
    "speed": ("speed_kmh", "sprints", "distance_km"),
    "red_card": (),
    "momentum_swing": ("momentum",),
}

READ = {
    "goal": {
        "opener": "Breaks the deadlock and forces the other side to come out.",
        "equaliser": "Resets the match: the trailing side's pressure has paid off.",
        "go_ahead": "Puts the scorers in front and flips the win-probability picture.",
        "extends_lead": "A two-goal cushion changes how both teams will play the rest of the match.",
        "pulls_one_back": "Gives the trailing side a foothold and real hope.",
    },
    "press_shift": {
        "up": "A deliberate change of plan: more bodies engaging the build-up, a higher line, more risk for more reward.",
        "down": "A retreat into a protective block, conceding territory to defend the result.",
    },
}


def deterministic_insight(m: dict[str, Any], names: Names) -> dict[str, Any]:
    f = m.get("facts", {})
    kind = m["kind"]
    why: list[str] = []
    for w in m.get("why", [])[:3]:
        if w.get("detail"):
            why.append(f"{w['label']}: {w['detail']}")
        elif w.get("value") is not None:
            why.append(f"{w['label']}: {w['value']}{w.get('unit', '')}")
    key_numbers = {k: f[k] for k in KEY_FACTS.get(kind, ()) if isinstance(f.get(k), (int, float))}
    read = ""
    if kind == "goal":
        read = READ["goal"].get(f.get("context", ""), "")
    elif kind == "press_shift":
        read = READ["press_shift"].get(f.get("direction", "up"), "")
    elif kind == "control_chaos":
        read = "One side is dictating tempo." if f.get("label") == "control" else "Transitions and duels dominate: nobody can settle."
    conf = 0.9
    if kind == "press_shift":
        conf = round(min(0.95, 0.5 + abs(f.get("z_score", 0)) / 12), 2)
    return {
        "claim": m.get("headline", ""),
        "why": why,
        "tactical_read": read,
        "key_numbers": key_numbers,
        "players": [names.p(p) for p in m.get("players", [])],
        "confidence": conf,
    }
