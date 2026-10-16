"""Explainer evaluation against simulator ground truth.

Real broadcast feeds never tell you *why* a team changed shape, so nobody can
measure whether an "explainable AI" is actually right. Our synthetic league
can: the engine logs every tactical change it makes. This module replays
matches through the live Interpret stage and scores:

* press-shift detection: recall, false alarms per match, detection delay;
* xG calibration: live model vs the engine's true scoring probability.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any

from .intel.moments import Moment, MomentDetector
from .intel.state import MatchState
from .sim.engine import SimResult, simulate


def replay(res: SimResult) -> tuple[MatchState, MomentDetector, list[Moment]]:
    """Feed a finished simulation through the live pipeline exactly as the stream would."""
    st = MatchState(res.info)
    det = MomentDetector(st)
    evs = sorted(res.events, key=lambda e: (e.qualifiers.get("t_end", e.t), e.seq))
    k = 0
    moments: list[Moment] = []
    for fi in range(len(res.frame_t)):
        ft = float(res.frame_t[fi])
        for sig in st.on_frame(res.frame(fi)):
            moments += det.on_signal(sig, ft, st.clock)
        while k < len(evs) and evs[k].qualifiers.get("t_end", evs[k].t) <= ft:
            moments += det.on_enriched(st.on_event(evs[k]))
            k += 1
    while k < len(evs):
        moments += det.on_enriched(st.on_event(evs[k]))
        k += 1
    return st, det, moments


def _press_truth(res: SimResult) -> list[dict[str, Any]]:
    out = []
    for tr in res.truth:
        if tr["type"] != "tactical_shift" or tr["t"] < 120:
            continue
        delta = tr["after"]["press_intensity"] - tr["before"]["press_intensity"]
        if abs(delta) >= 0.25:
            out.append({**tr, "direction": "up" if delta > 0 else "down", "delta": round(delta, 2)})
    return out


def _clock_minutes(clock: str) -> float:
    base, _, extra = clock.rstrip("'").partition("+")
    return float(base) + (float(extra) if extra else 0.0)


def evaluate(seeds: list[int], home: str = "NOR", away: str = "CAL", scenario: str = "derby") -> dict[str, Any]:
    hits, misses, false_alarms, delays, onset_err = 0, 0, 0, [], []
    xg_pairs: list[tuple[float, float]] = []
    per_match = []
    for seed in seeds:
        res = simulate(home, away, seed, scenario)
        st, _, moments = replay(res)
        truth = _press_truth(res)
        detections = [m for m in moments if m.kind == "press_shift"]
        matched: set[str] = set()
        for tr in truth:
            cand = [d for d in detections if d.team == tr["team"] and d.facts["direction"] == tr["direction"]
                    and -5 * 60 <= d.t - tr["t"] <= 20 * 60 and d.id not in matched]
            if cand:
                d = min(cand, key=lambda m: m.t)
                matched.add(d.id)
                hits += 1
                gap = d.t - tr["t"]
                if gap > 15 * 60:  # straddles half-time: remove the 15 minute break
                    gap -= 15 * 60
                delays.append(gap / 60)
                onset_err.append(abs(_clock_minutes(d.facts["onset_clock"]) - _clock_minutes(tr["clock"])))
            else:
                misses += 1
        fa = [d for d in detections if d.id not in matched]
        false_alarms += len(fa)
        truth_xg = {t["event"]: t["true_xg"] for t in res.truth if t["type"] == "shot"}
        for eid, data in st.enriched.items():
            if "xg" in data and eid in truth_xg and data.get("set_piece") != "penalty":
                xg_pairs.append((data["xg"], truth_xg[eid]))
        per_match.append({"seed": seed, "score": dict(st.score), "truth_shifts": len(truth),
                          "detected": len(detections), "false_alarms": len(fa)})
    n_truth = hits + misses
    model, real = zip(*xg_pairs, strict=True) if xg_pairs else ((), ())
    bias = mean(m - r for m, r in xg_pairs) if xg_pairs else 0.0
    mae = mean(abs(m - r) for m, r in xg_pairs) if xg_pairs else 0.0
    return {
        "matches": len(seeds),
        "press_shift": {
            "truth_events": n_truth,
            "recall": round(hits / n_truth, 2) if n_truth else None,
            "false_alarms_per_match": round(false_alarms / len(seeds), 2),
            "median_delay_min": round(median(delays), 1) if delays else None,
            "mean_delay_min": round(mean(delays), 1) if delays else None,
            "median_onset_error_min": round(median(onset_err), 1) if onset_err else None,
        },
        "xg_model": {
            "shots": len(xg_pairs),
            "mean_model_xg": round(mean(model), 3) if model else None,
            "mean_true_xg": round(mean(real), 3) if real else None,
            "bias": round(bias, 4),
            "mae": round(mae, 4),
        },
        "per_match": per_match,
    }
