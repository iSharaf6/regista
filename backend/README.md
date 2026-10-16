# regista (backend package)

The Python service behind Regista, the multi-agent match director: synthetic feed, interpretation, Microsoft Agent
Framework agents, Graphics Cue Protocol, live feed API, MCP server and the FastAPI app.

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
.venv/bin/regista serve          # API + WebSocket + MCP (+ the web app if web/dist is built)
.venv/bin/pytest -q              # offline test suite
.venv/bin/regista --help         # simulate, realism, evaluate, cast, llm-eval, publish, mcp
```

See the repository README for the full project description, architecture and evidence.
