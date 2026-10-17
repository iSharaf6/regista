"""HTTP + WebSocket API, MCP endpoint and static web app in one service."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import __version__
from ..mcp_server import build_mcp
from ..runtime.observability import setup_observability
from ..runtime.session import MatchSession
from ..schema.cues import Cue
from ..schema.events import Frame, MatchEvent, MatchInfo
from ..schema.profiles import FOCUS_METRICS, SUPPORTED_LANGUAGES, FanProfile, Mode
from ..sim.scenarios import SCENARIOS
from ..sim.squads import TEAMS

log = logging.getLogger("regista.api")
ROOT = Path(__file__).resolve().parents[3]
WEB_DIST = Path(os.getenv("REGISTA_WEB_DIST", ROOT / "web" / "dist"))
DOCS = Path(os.getenv("REGISTA_DOCS", ROOT / "docs"))

session_ref: dict[str, MatchSession] = {}
mcp = build_mcp(session_ref)
mcp_app = mcp.streamable_http_app(streamable_http_path="/", stateless_http=True, json_response=True, host="0.0.0.0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_observability()
    session = MatchSession()
    session_ref["session"] = session
    await session.start()
    if os.getenv("REGISTA_AUTOPLAY", "0") == "1":
        await session.control("play")
    async with mcp.session_manager.run():
        yield
    await session.stop()


app = FastAPI(title="Regista", version=__version__, lifespan=lifespan,
              description="Multi-agent match director: explainable, personalised football intelligence.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/mcp", mcp_app)


def S() -> MatchSession:
    return session_ref["session"]


ADMIN_TOKEN = os.getenv("REGISTA_ADMIN_TOKEN", "").strip()


def require_producer(token: str | None) -> None:
    """With REGISTA_ADMIN_TOKEN set, only producers holding it may change the shared broadcast or push a feed."""
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        raise HTTPException(401, "producer token required (X-Regista-Token)")


def web_file(root: Path, path: str) -> Path | None:
    """The file to serve for a browser path: a real file inside the built web app, the SPA index for app routes,
    or None for anything that resolves outside it (.., encoded .., symlinks)."""
    base = root.resolve()
    f = (base / path).resolve()
    if not f.is_relative_to(base):
        return None
    return f if path and f.is_file() else base / "index.html"


class RateLimit:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and q[0] < now - 60:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True


ask_limit = RateLimit(int(os.getenv("REGISTA_ASK_PER_MINUTE", "8")))
SLOW_DOWN = {"en": "One moment - you have asked a lot of questions. Try again in a minute.",
             "es": "Un momento: has hecho muchas preguntas. Vuelve a intentarlo en un minuto.",
             "fr": "Un instant : vous avez posé beaucoup de questions. Réessayez dans une minute.",
             "ar": "لحظة من فضلك: لقد طرحت أسئلة كثيرة. حاول مرة أخرى بعد دقيقة.",
             "pt": "Um momento: você fez muitas perguntas. Tente de novo em um minuto."}


class ControlBody(BaseModel):
    action: str
    value: Any = None


class AskBody(BaseModel):
    question: str
    language: str = "en"
    persona: str = "casual"


@app.get("/api/health")
def health() -> dict[str, Any]:
    s = S()
    return {"ok": True, "version": __version__, "llm": s.llm_info(), "bus": s.bus.name,
            "viewers": len(s.viewers) - len(s.virtual), "onair_consumers": len(s.virtual), "mode": s.mode,
            "clock": s.state.clock, "breaker": s.rt.breaker.as_dict(), "webhooks": s.webhooks.status(),
            "producer_token_required": bool(ADMIN_TOKEN)}


@app.get("/api/match")
def match() -> dict[str, Any]:
    s = S()
    return {"info": s.res.info.model_dump(), "params": s.params, "llm": s.llm_info(), "control": s.control_state(),
            "options": {"languages": SUPPORTED_LANGUAGES, "modes": [m.value for m in Mode], "focus_metrics": FOCUS_METRICS,
                        "teams": sorted(TEAMS), "scenarios": {k: v.description for k, v in SCENARIOS.items()}}}


@app.get("/api/state")
def state() -> dict[str, Any]:
    return S().state.snapshot()


@app.get("/api/series")
def series() -> dict[str, Any]:
    st = S().state
    return {"wp_series": st.wp_series, "momentum_series": st.momentum_series}


@app.get("/api/players")
def players() -> list[dict[str, Any]]:
    s = S()
    return [s.state.player_view(pid) for pid in s.state.players]


@app.get("/api/moments")
def moments(min_importance: int = 0) -> list[dict[str, Any]]:
    s = S()
    return [s._moment_summary(m) for m in s.moments if m.importance >= min_importance]


@app.get("/api/moments/{moment_id}")
def moment(moment_id: str) -> dict[str, Any]:
    s = S()
    for m in s.moments:
        if m.id == moment_id:
            return {**m.as_dict(), "story": s.story.get(m.id)}
    raise HTTPException(404, "moment not found")


@app.get("/api/cues")
def cues(since: float = 0.0, kind: str | None = None) -> list[dict[str, Any]]:
    return [c.model_dump() for c in S().cues if c.t_in >= since and (kind is None or c.kind.value == kind)]


@app.get("/api/tactical")
def tactical() -> dict[str, Any]:
    return S().tools.tactical_picture()


@app.get("/api/telemetry")
def telemetry(limit: int = 80) -> dict[str, Any]:
    s = S()
    return {"summary": s.telemetry.summary(), "breaker": s.rt.breaker.as_dict(),
            "spans": [sp.as_dict() for sp in list(s.telemetry.spans)[-limit:]]}


@app.post("/api/control")
async def control(body: ControlBody, x_regista_token: str | None = Header(None)) -> dict[str, Any]:
    require_producer(x_regista_token)
    return await S().control(body.action, body.value)


@app.post("/api/ask")
async def ask(body: AskBody, request: Request) -> dict[str, Any]:
    if not ask_limit.allow(request.client.host if request.client else "anon"):
        return {"answer": SLOW_DOWN.get(body.language, SLOW_DOWN["en"]), "tools": [], "model": "rate-limit", "ms": 0}
    return await S().ask(body.question[:500], body.language, body.persona)


# ---------------------------------------------------------------------- live feeds and production tools
class FeedBatch(BaseModel):
    # bounded: ten minutes of 5 Hz tracking per request is far more than any provider needs to send at once
    frames: list[Frame] = Field(default_factory=list, max_length=3000)
    events: list[MatchEvent] = Field(default_factory=list, max_length=2000)


@app.post("/api/feed/start", tags=["live feed"])
async def feed_start(info: MatchInfo, x_regista_token: str | None = Header(None)) -> dict[str, Any]:
    """Start a live match from an external provider: send the MatchInfo (teams, squads, roster order)."""
    require_producer(x_regista_token)
    if not info.roster:
        info.roster = [p.id for t in (info.home, info.away) for p in t.players]
    return S().start_live(info)


@app.post("/api/feed", tags=["live feed"])
async def feed(batch: FeedBatch, x_regista_token: str | None = Header(None)) -> dict[str, Any]:
    """Push tracking frames (5 Hz, positions in MatchInfo.roster order) and completed events, in any batch size."""
    require_producer(x_regista_token)
    s = S()
    if s.mode != "live":
        raise HTTPException(409, "no live match: POST /api/feed/start first")
    roster = len(s.res.info.roster)
    bad = [f.t for f in batch.frames if len(f.p) != roster]
    if bad:
        raise HTTPException(422, f"frames must carry {roster} positions (MatchInfo.roster order); bad frames at t={bad[:3]}")
    frames = [{"t": f.t, "b": list(f.b), "p": [None if q is None else list(q) for q in f.p]} for f in batch.frames]
    return s.ingest(frames, batch.events)


@app.post("/api/feed/stop", tags=["live feed"])
async def feed_stop(x_regista_token: str | None = Header(None)) -> dict[str, Any]:
    require_producer(x_regista_token)
    return S().stop_live()


@app.get("/api/onair", tags=["production tools"])
async def onair(mode: Mode = Mode.CASUAL, lang: str = "en", team: str | None = None, player: str | None = None,
          focus: str = "none") -> dict[str, Any]:
    """What is on air right now for a viewer profile, as plain JSON: poll it from vMix Data Sources, CasparCG or OBS."""
    profile = FanProfile(id="onair", mode=mode, language=lang if lang in SUPPORTED_LANGUAGES else "en",
                         favorite_team=team, favorite_player=player, focus_metric=focus)
    return S().onair(profile)


@app.get("/api/recap")
async def recap(language: str = "en", persona: str = "analyst", period: str | None = None) -> dict[str, Any]:
    return await S().recap(language, persona, period)


@app.get("/api/evaluation")
def evaluation() -> dict[str, Any]:
    for name in ("evaluation.json", "realism.json"):
        if not (DOCS / name).exists():
            return {"available": False, "hint": "run `regista evaluate` and `regista realism`"}
    out = {"available": True, "explainers": json.loads((DOCS / "evaluation.json").read_text()),
           "realism": json.loads((DOCS / "realism.json").read_text())}
    if (DOCS / "llm-eval.json").exists():
        llm = json.loads((DOCS / "llm-eval.json").read_text())
        out["llm"] = {k: v for k, v in llm.items() if k not in {"jobs", "agents"}}
    return out


@app.get("/api/schema/{name}")
def schema(name: str) -> dict[str, Any]:
    models = {"cue": Cue, "event": MatchEvent, "frame": Frame, "match": MatchInfo, "profile": FanProfile}
    if name not in models:
        raise HTTPException(404, f"schemas: {sorted(models)}")
    return models[name].model_json_schema()


@app.get("/api/export/events.jsonl", response_class=PlainTextResponse)
def export_events() -> str:
    return "\n".join(e.model_dump_json() for e in S().res.events)


@app.get("/api/export/cues.json")
def export_cues() -> JSONResponse:
    s = S()
    return JSONResponse({"protocol": "regista-gcp/1", "match": s.res.info.match_id, "cues": [c.model_dump() for c in s.cues]})


@app.websocket("/ws")
async def ws(socket: WebSocket, profile: str = Query("{}"), ops: int = Query(0)) -> None:
    await socket.accept()
    s = S()
    try:
        prof = FanProfile.model_validate_json(profile or "{}")
    except Exception:  # noqa: BLE001
        prof = FanProfile()
    viewer = s.connect(prof, ops=bool(ops))

    async def pump() -> None:
        while True:
            msg = await viewer.queue.get()
            await socket.send_text(json.dumps(msg, default=str, ensure_ascii=False))

    sender = asyncio.create_task(pump())
    try:
        while True:
            raw = await socket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = msg.get("type")
            if kind == "profile":
                with contextlib.suppress(Exception):
                    s.set_profile(viewer.id, FanProfile.model_validate(msg.get("profile", {})))
            elif kind == "control":
                if not ADMIN_TOKEN or msg.get("token") == ADMIN_TOKEN:
                    await s.control(msg.get("action", ""), msg.get("value"))
                else:
                    viewer.send({"type": "error", "error": "producer token required"})
            elif kind == "ask":
                if not ask_limit.allow(f"ws:{viewer.id}"):
                    viewer.send({"type": "answer", "id": msg.get("id"), "answer": SLOW_DOWN.get(viewer.profile.language,
                                 SLOW_DOWN["en"]), "tools": [], "model": "rate-limit", "ms": 0})
                    continue
                res = await s.ask(str(msg.get("question", ""))[:500], viewer.profile.language,
                                  "analyst" if viewer.profile.mode == Mode.ANALYST else
                                  "new_fan" if viewer.profile.mode == Mode.NEW_FAN else "casual")
                viewer.send({"type": "answer", "id": msg.get("id"), **res})
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        s.disconnect(viewer.id)


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        f = web_file(WEB_DIST, path)
        if f is None:
            raise HTTPException(404)
        return FileResponse(f)
