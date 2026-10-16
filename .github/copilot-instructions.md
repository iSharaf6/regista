# Regista: instructions for GitHub Copilot

Regista is a multi-agent match director: synthetic football feed -> interpret -> explain -> render -> personalise.

## Ground rules
- **Grounding is non-negotiable.** Generated copy may only use numbers and names present in a moment's facts,
  the live context or tool results. Any new copy path must go through `regista/agents/verifier.py`.
- **Deterministic first, generative second.** Numbers come from `regista/intel/*`; language models explain them.
  Never move a metric computation into a prompt.
- **Fallbacks are a feature.** Every agent call goes through `AgentRuntime.call` (breaker, timeout, chaos, spans)
  and must have a template fallback in `regista/agents/templates.py` for all five languages (en, es, fr, ar, pt).
- **Synthetic data only.** Clubs and players in `regista/sim/squads.py` are fictional. Do not add real names,
  crests, trademarks or real match footage.
- **Contracts are versioned.** Events (`schema/events.py`) and Graphics Cue Protocol cues (`schema/cues.py`) are
  public contracts - extend with optional fields, never break existing ones.

## Layout
- `backend/regista/sim` engine, squads, scenarios, realism report
- `backend/regista/intel` match state (blackboard), models (xG, pass difficulty, win probability), signals, moments
- `backend/regista/agents` Agent Framework agents + workflow, verifier, producer, director, pundit, recap
- `backend/regista/runtime` live session (two lanes), event bus (in-memory / Event Hubs), observability
- `backend/regista/mcp_server.py` MCP tools over the live match; `backend/regista/api/app.py` REST + WebSocket
- `web/` React + Vite broadcast app (pitch renderer, GCP overlay, Fan Studio, Control Room)

## Commands
- `cd backend && uv venv && uv pip install -e ".[dev]" && pytest -q`
- `regista serve` then `cd web && npm run dev`
- `regista evaluate --matches 20` re-scores the explainers against simulator ground truth
- The live match is available to Copilot agent mode through the `regista` MCP server in `.vscode/mcp.json`.
