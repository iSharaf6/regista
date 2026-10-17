"""Regista command line.

  regista serve                 run API + WebSocket + MCP (+ web app if built)
  regista simulate --seed 7     generate a synthetic match to data/ (events.jsonl, frames.json, truth.json)
  regista realism --matches 20  realism report vs top-flight reference ranges -> docs/realism.json
  regista evaluate --matches 20 explainers vs ground truth -> docs/evaluation.json
  regista cast --tries 40       storyline casting: find the most dramatic seed for a demo
  regista llm-eval              score the live agents (first-draft verification, retries, latency) with the configured model
  regista fanout                per-viewer personalisation cost at 1 to 1,000 viewers (model work does not grow with viewers)
  regista publish --url URL     reference data provider: stream a match into the live feed API
  regista mcp                   MCP server over stdio (for local MCP clients)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def cmd_serve(a: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("regista.api.app:app", host=a.host, port=a.port, reload=False, log_level="info")


def cmd_simulate(a: argparse.Namespace) -> None:
    from .sim.engine import simulate

    res = simulate(a.home, a.away, a.seed, a.scenario)
    out = Path(a.out) / res.info.match_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "match.json").write_text(res.info.model_dump_json(indent=2))
    (out / "events.jsonl").write_text("\n".join(e.model_dump_json() for e in res.events))
    (out / "truth.json").write_text(json.dumps(res.truth, indent=1))
    with open(out / "frames.jsonl", "w") as f:
        for k in range(len(res.frame_t)):
            f.write(json.dumps(res.frame(k), separators=(",", ":")) + "\n")
    print(f"{res.info.match_id}: {res.summary['score']} -> {out} ({len(res.events)} events, {len(res.frame_t)} frames)")


def cmd_realism(a: argparse.Namespace) -> None:
    from .sim.engine import simulate
    from .sim.realism import report

    rep = report([simulate(a.home, a.away, s, a.scenario) for s in range(1, a.matches + 1)])
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "realism.json").write_text(json.dumps(rep, indent=1))
    for m in rep["metrics"]:
        print(f"{'PASS' if m['pass'] else 'FAIL'}  {m['metric']:24s} {m['mean']:>9}  ref {m['range']}")
    print(f"{rep['passed']}/{rep['total']} metrics inside reference ranges over {rep['matches']} matches")


def cmd_evaluate(a: argparse.Namespace) -> None:
    from .evaluation import evaluate

    rep = evaluate(list(range(1, a.matches + 1)), a.home, a.away, a.scenario)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "evaluation.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_match"}, indent=1))


def cmd_fanout(a: argparse.Namespace) -> None:
    """Shared generation, per-viewer selection: measure the Director/cue fan-out as the audience grows (no network I/O)."""
    import asyncio
    import itertools

    from .runtime.session import MatchSession
    from .schema.profiles import FanProfile

    modes, langs, teams = ["casual", "analyst", "player_cam", "new_fan"], ["en", "es", "fr", "ar", "pt"], [None, "NOR", "CAL"]

    async def one(n: int) -> dict[str, Any]:
        s = MatchSession(story_workers=0)
        combos = itertools.cycle(itertools.product(modes, langs, teams))
        for i in range(n):
            m, lang, team = next(combos)
            s.connect(FanProfile(id=f"v{i}", mode=m, language=lang, favorite_team=team,
                                 favorite_player="NOR-10" if m == "player_cam" else None))
        s.seek(15)
        t0 = time.perf_counter()
        for _ in range(a.seconds):
            s.advance(1.0, live=True)
        dt = time.perf_counter() - t0
        return {"viewers": n, "ms_per_match_second": round(1000 * dt / a.seconds, 2), "story_jobs": s.queue.qsize(),
                "languages": len(s.languages())}

    rows = [asyncio.run(one(n)) for n in (1, 10, 100, 1000)]
    (ROOT / "docs" / "fanout.json").write_text(json.dumps({"match_seconds": a.seconds, "rows": rows}, indent=1))
    for r in rows:
        print(f"{r['viewers']:>5} viewers: {r['ms_per_match_second']:6.2f} ms per match-second, "
              f"{r['story_jobs']} story jobs, {r['languages']} languages")


def cmd_cast(a: argparse.Namespace) -> None:
    from .evaluation import replay
    from .sim.engine import simulate

    best = []
    for seed in range(1, a.tries + 1):
        res = simulate(a.home, a.away, seed, a.scenario)
        st, _, moments = replay(res)
        wp = st.wp_series
        swings = sum(abs(wp[i]["home"] - wp[i - 1]["home"]) for i in range(1, len(wp)))
        goals = [m for m in moments if m.kind == "goal"]
        late = sum(1 for m in goals if m.t > res.frame_t[-1] - 20 * 60)
        lead_changes = sum(1 for m in goals if m.facts.get("context") in {"equaliser", "go_ahead"})
        detected = sum(1 for m in moments if m.kind == "press_shift")
        score = swings + 0.6 * late + 0.4 * lead_changes + 0.3 * min(detected, 2) + (0.5 if 3 <= len(goals) <= 6 else 0)
        best.append((round(score, 2), seed, st.score, len(goals), late, lead_changes, detected))
    best.sort(reverse=True)
    print("drama  seed  score            goals late lead_changes press_shifts")
    for row in best[:10]:
        print(f"{row[0]:5}  {row[1]:4}  {str(row[2]):16} {row[3]:5} {row[4]:4} {row[5]:12} {row[6]:12}")


def cmd_llm_eval(a: argparse.Namespace) -> None:
    import asyncio

    from .llm_eval import run

    rep = asyncio.run(run(a.moments, tuple(a.langs.split(",")), a.concurrency,
                          tuple(int(x) for x in a.seeds.split(",")), not a.no_baseline))
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "llm-eval.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    keys = ("model", "eval_seeds", "moments", "moment_kinds", "workflow", "single_agent_baseline", "verifier_probe",
            "rejection_reasons", "pundit_used_tools")
    print(json.dumps({k: rep[k] for k in keys}, indent=1, ensure_ascii=False))
    for r in rep["recaps"]:
        print(f"recap[{r['lang']}] {r['source']} verified={r['verified']} :: {r['headline']}")
    for q in rep["pundit"]:
        print(f"pundit[{q['lang']}] tools={q['tools']} :: {q['answer'][:140]}")


def cmd_publish(a: argparse.Namespace) -> None:
    """Reference data provider: stream a match into a running Regista over the live feed API, in real time."""
    import time

    import httpx

    from .sim.engine import simulate

    res = simulate(a.home, a.away, a.seed, a.scenario)
    headers = {"X-Regista-Token": a.token} if a.token else {}
    client = httpx.Client(base_url=a.url.rstrip("/"), headers=headers, timeout=30)
    client.post("/api/feed/start", json=res.info.model_dump(mode="json")).raise_for_status()
    events = sorted(res.events, key=lambda e: (e.qualifiers.get("t_end", e.t), e.seq))
    # feed clock -> wall clock, squeezing the half-time gap so a replayed match never stalls
    virtual, prev, vt = [], None, 0.0
    for t in res.frame_t:
        vt += 0.2 if prev is None or t - prev > 3 else float(t - prev)
        virtual.append(vt)
        prev = t
    start, ei, k, n = time.monotonic(), 0, 0, len(res.frame_t)
    print(f"publishing {res.info.match_id} to {a.url} at {a.speed}x ({n} frames, {len(events)} events)", flush=True)
    while k < n:
        due = (time.monotonic() - start) * a.speed
        frames = []
        while k < n and virtual[k] <= due:
            frames.append(res.frame(k))
            k += 1
        last_t = frames[-1]["t"] if frames else None
        batch = []
        while last_t is not None and ei < len(events) and events[ei].qualifiers.get("t_end", events[ei].t) <= last_t:
            batch.append(events[ei].model_dump(mode="json"))
            ei += 1
        if frames or batch:
            r = client.post("/api/feed", json={"frames": frames, "events": batch})
            r.raise_for_status()
            for headline in r.json().get("new_moments", []):
                print(f"  {r.json()['clock']:>7}  {headline}", flush=True)
        time.sleep(0.25)
    if ei < len(events):
        client.post("/api/feed", json={"frames": [], "events": [e.model_dump(mode="json") for e in events[ei:]]})
    print("full time", flush=True)


def cmd_mcp(a: argparse.Namespace) -> None:
    import asyncio

    from .mcp_server import build_mcp
    from .runtime.session import MatchSession

    async def main() -> None:
        session = MatchSession()
        session.seek(a.minute)
        mcp = build_mcp({"session": session})
        await mcp.run_stdio_async()

    asyncio.run(main())


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="regista", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def match_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--home", default="NOR")
        sp.add_argument("--away", default="CAL")
        sp.add_argument("--scenario", default="derby")

    s = sub.add_parser("serve")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=cmd_serve)
    s = sub.add_parser("simulate")
    match_args(s)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--out", default=str(ROOT / "data" / "matches"))
    s.set_defaults(fn=cmd_simulate)
    for name, fn in (("realism", cmd_realism), ("evaluate", cmd_evaluate)):
        s = sub.add_parser(name)
        match_args(s)
        s.add_argument("--matches", type=int, default=20)
        s.set_defaults(fn=fn)
    s = sub.add_parser("fanout", help="per-viewer personalisation cost as the audience grows")
    s.add_argument("--seconds", type=int, default=600)
    s.set_defaults(fn=cmd_fanout)
    s = sub.add_parser("cast")
    match_args(s)
    s.add_argument("--tries", type=int, default=40)
    s.set_defaults(fn=cmd_cast)
    s = sub.add_parser("llm-eval", help="score the live agents with the configured model")
    s.add_argument("--seeds", default="101,202,303,404", help="held-out evaluation matches (the demo is seed 16)")
    s.add_argument("--moments", type=int, default=24)
    s.add_argument("--langs", default="en,es,fr,ar,pt")
    s.add_argument("--concurrency", type=int, default=2)
    s.add_argument("--no-baseline", action="store_true", help="skip the single-agent comparison")
    s.set_defaults(fn=cmd_llm_eval)
    s = sub.add_parser("publish", help="stream a simulated match into a running Regista via the live feed API")
    match_args(s)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--url", default="http://localhost:8000")
    s.add_argument("--speed", type=float, default=4.0)
    s.add_argument("--token", default=None, help="producer token, if the server sets REGISTA_FEED_TOKEN or REGISTA_ADMIN_TOKEN")
    s.set_defaults(fn=cmd_publish)
    s = sub.add_parser("mcp")
    s.add_argument("--minute", type=float, default=70.0, help="replay the demo match up to this minute first")
    s.set_defaults(fn=cmd_mcp)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main(sys.argv[1:])
