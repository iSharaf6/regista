"""Realism report: does the synthetic league look like football?

Compares per-team match statistics against published top-flight ranges
(per team, per match) and reports pass/fail for each, so data quality is
measured, not asserted.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

import numpy as np

from ..schema.events import EventType
from .engine import SimResult

# per team, per match; generous bands spanning typical European top-flight seasons
REFERENCE: dict[str, tuple[float, float]] = {
    "passes": (330, 700),
    "pass_accuracy": (0.72, 0.9),
    "shots": (7, 19),
    "shots_on_target_share": (0.25, 0.5),
    "xg": (0.6, 2.2),
    "goals": (0.5, 2.5),
    "xg_per_shot": (0.07, 0.16),
    "fouls": (7, 16),
    "corners": (3, 8),
    "yellow_cards": (0, 4),
    "tackles": (8, 25),
    "interceptions": (5, 20),
    "outfield_distance_km": (9.0, 12.5),
    "top_speed_kmh": (29.0, 37.5),
}


def team_stats(res: SimResult) -> dict[str, dict[str, float]]:
    info = res.info
    out: dict[str, dict[str, float]] = {}
    xg_by_event = {t["event"]: t["true_xg"] for t in res.truth if t["type"] == "shot"}
    roster = info.roster
    speeds = np.linalg.norm(np.diff(res.frame_pos, axis=0), axis=2) / np.diff(res.frame_t)[:, None]
    speeds = np.nan_to_num(speeds, nan=0.0)
    for team in (info.home, info.away):
        evs = [e for e in res.events if e.team == team.id]
        c = Counter(e.type for e in evs)
        passes = [e for e in evs if e.type == EventType.PASS]
        shots = [e for e in evs if e.type == EventType.SHOT]
        on_t = [s for s in shots if s.outcome in {"goal", "saved"}]
        idxs = [i for i, pid in enumerate(roster) if pid.startswith(team.id)]
        outfield = [i for i in idxs if not next(p for p in team.players if p.id == roster[i]).position == "GK"]
        full_match = [i for i in outfield if res.summary["distance_km"][roster[i]] > 0
                      and not np.isnan(res.frame_pos[-1, i, 0]) and not np.isnan(res.frame_pos[0, i, 0])]
        xg = sum(xg_by_event.get(s.id, 0) for s in shots)
        out[team.id] = {
            "passes": len(passes),
            "pass_accuracy": sum(p.outcome == "complete" for p in passes) / max(1, len(passes)),
            "shots": len(shots),
            "shots_on_target_share": len(on_t) / max(1, len(shots)),
            "xg": xg,
            "goals": c[EventType.GOAL],
            "xg_per_shot": xg / max(1, len(shots)),
            "fouls": c[EventType.FOUL],
            "corners": c[EventType.CORNER],
            "yellow_cards": sum(1 for e in evs if e.type == EventType.CARD and e.outcome == "yellow"),
            "tackles": c[EventType.TACKLE],
            "interceptions": c[EventType.INTERCEPTION],
            "outfield_distance_km": mean(res.summary["distance_km"][roster[i]] for i in full_match) if full_match else 0,
            "top_speed_kmh": float(np.percentile(speeds[:, idxs].max(axis=0), 50) * 3.6),
        }
    return out


def report(results: list[SimResult]) -> dict[str, Any]:
    agg: dict[str, list[float]] = defaultdict(list)
    for r in results:
        for stats in team_stats(r).values():
            for k, v in stats.items():
                agg[k].append(v)
    rows = []
    for k, (lo, hi) in REFERENCE.items():
        vals = agg.get(k, [])
        m = mean(vals) if vals else float("nan")
        inside = sum(lo <= v <= hi for v in vals) / max(1, len(vals))
        rows.append({"metric": k, "mean": round(m, 3), "range": [lo, hi], "within_range": round(inside, 2),
                     "pass": lo <= m <= hi})
    return {"matches": len(results), "metrics": rows, "passed": sum(r["pass"] for r in rows), "total": len(rows)}
