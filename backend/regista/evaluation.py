"""Explainer evaluation against simulator ground truth.

Real broadcast feeds never tell you *why* a team changed shape, so nobody can
measure whether an "explainable AI" is actually right. Our synthetic league
can: the engine logs every tactical change it makes. This module replays
matches through the live Interpret stage and scores:

* press-shift detection: recall, false alarms per match, detection delay;
* xG calibration: live model vs the engine's true scoring probability;
* template grounding: the deterministic fallback copy (every story moment x 5 languages x 3 personas) checked by the
  same Verifier the live agents face, since that copy is what airs when a model fails.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any

from .intel.moments import Moment, MomentDetector
from .intel.state import MatchState
from .sim.engine import SimResult, simulate

LANGS = ("en", "es", "fr", "ar", "pt")


def replay(res: SimResult, contexts: dict[str, dict[str, Any]] | None = None
           ) -> tuple[MatchState, MomentDetector, list[Moment]]:
    """Feed a finished simulation through the live pipeline exactly as the stream would. With `contexts`, also keep the
    live CONTEXT each moment was detected in (score, manpower, ...), as a story job would see it then."""
    from .runtime.session import match_context

    st = MatchState(res.info)
    det = MomentDetector(st)
    evs = sorted(res.events, key=lambda e: (e.qualifiers.get("t_end", e.t), e.seq))
    k = 0
    moments: list[Moment] = []

    def add(ms: list[Moment]) -> None:
        moments.extend(ms)
        if contexts is not None:
            for m in ms:
                contexts[m.id] = match_context(st)

    for fi in range(len(res.frame_t)):
        frame = res.frame(fi)
        ft = frame["t"]
        for sig in st.on_frame(frame):
            add(det.on_signal(sig, ft, st.clock))
        while k < len(evs) and evs[k].qualifiers.get("t_end", evs[k].t) <= ft:
            add(det.on_enriched(st.on_event(evs[k])))
            k += 1
    while k < len(evs):
        add(det.on_enriched(st.on_event(evs[k])))
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


def _playing_seconds(t: float, half_time: float | None, second_half: float | None) -> float:
    """Feed time with only the actual half-time interval removed."""
    if half_time is None or second_half is None:
        return t
    return t - min(max(0.0, t - half_time), max(0.0, second_half - half_time))


def evaluate(seeds: list[int], home: str = "NOR", away: str = "CAL", scenario: str = "derby") -> dict[str, Any]:
    from .agents.story import StoryJob, _template
    from .agents.verifier import verify_texts

    hits, misses, false_alarms, delays, onset_err = 0, 0, 0, [], []
    grounding = {"moments": 0, "outputs": 0, "rejected": 0}
    xg_pairs: list[tuple[float, float]] = []
    per_match = []
    for seed in seeds:
        res = simulate(home, away, seed, scenario)
        contexts: dict[str, dict[str, Any]] = {}
        st, _, moments = replay(res, contexts)
        truth = _press_truth(res)
        detections = [m for m in moments if m.kind == "press_shift"]
        half_time = next((e.t for e in res.events if e.type == "half_time"), None)
        second_half = next((e.t for e in res.events if e.type == "second_half"), None)

        def delay(detection_t: float, truth_t: float, half_time: float | None = half_time,
                  second_half: float | None = second_half) -> float:
            return (_playing_seconds(detection_t, half_time, second_half)
                    - _playing_seconds(truth_t, half_time, second_half))

        matched: set[str] = set()
        for tr in truth:
            cand = [d for d in detections if d.team == tr["team"] and d.facts["direction"] == tr["direction"]
                    and -5 * 60 <= delay(d.t, tr["t"]) <= 20 * 60 and d.id not in matched]
            if cand:
                d = min(cand, key=lambda m: m.t)
                matched.add(d.id)
                hits += 1
                gap = delay(d.t, tr["t"])
                delays.append(gap / 60)
                # The detector uses continuous minute bins: 45+3 and 46' are
                # consecutive periods, not the decreasing numbers 48 and 46.
                truth_minute = int(tr["t"] // 60)
                if second_half is not None and tr["t"] >= second_half:
                    truth_minute = st._p1_bins + int((tr["t"] - second_half) // 60)
                onset_err.append(abs(d.facts["onset_index"] - truth_minute))
            else:
                misses += 1
        fa = [d for d in detections if d.id not in matched]
        false_alarms += len(fa)
        truth_xg = {t["event"]: t["true_xg"] for t in res.truth if t["type"] == "shot"}
        for eid, data in st.enriched.items():
            if "xg" in data and eid in truth_xg and data.get("set_piece") != "penalty":
                xg_pairs.append((data["xg"], truth_xg[eid]))
        names = {"players": {pid: p.info.short_name for pid, p in st.players.items()}, "teams": dict(st.short)}
        shirts = {pid: p.info.number for pid, p in st.players.items()}
        for m in moments:
            if m.lane != "story" or m.kind in {"half_time", "full_time"}:
                continue
            # the context at the moment, not the final whistle's: copy is checked against the match as it stood then
            job = StoryJob(m.as_dict(), contexts[m.id], list(LANGS), names, names["players"], st.home, st.away,
                           shirts=shirts)
            grounding["moments"] += 1
            for lang in LANGS:
                grounding["outputs"] += 1
                if not verify_texts({lang: _template(job, lang)}, job.evidence(), set(m.players), names["players"],
                                    claims=m.facts).ok:
                    grounding["rejected"] += 1
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
            "false_alarms_per_match": round(false_alarms / len(seeds), 2) if seeds else None,
            "median_delay_min": round(median(delays), 1) if delays else None,
            "mean_delay_min": round(mean(delays), 1) if delays else None,
            "median_onset_error_min": round(median(onset_err), 1) if onset_err else None,
        },
        "template_grounding": {**grounding, "languages": list(LANGS), "personas_per_output": 3},
        "xg_model": {
            "shots": len(xg_pairs),
            "mean_model_xg": round(mean(model), 3) if model else None,
            "mean_true_xg": round(mean(real), 3) if real else None,
            "bias": round(bias, 4),
            "mae": round(mae, 4),
        },
        "per_match": per_match,
    }
