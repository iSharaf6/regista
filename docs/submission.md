# Submission text (Hackathon Website → Projects)

## Project name
Regista: the multi-agent match director

## Category
Best Multi-Agent Orchestration (also eligible for the Grand Prizes)

## Elevator pitch
Regista turns a synthetic football feed into explainable, verified, personalised broadcast intelligence. Specialised
Microsoft Agent Framework agents (Analyst, Narrator, Localizer, a deterministic Verifier, Recap and Pundit) run on
Microsoft Foundry. They explain *why* moments matter and write copy for three audiences in five languages. A Verifier
checks every figure before it airs. Per-viewer Director agents then re-cut the broadcast for each fan: the same goal
reaches an English analyst, an Arabic-speaking supporter of the other side and a newcomer as three different
experiences. The output is a timed, machine-readable Graphics Cue Protocol that drives a broadcast overlay, a
transparent OBS/vMix page and an MCP server that GitHub Copilot can question live.

## Who uses it, and how
Broadcasters and streamers push their live feed to `POST /api/feed` and drive their existing vMix, CasparCG or OBS
graphics from `GET /api/onair`, already personalised for each market. Club media teams get verified goal,
tactical-shift and recap posts in Slack, Teams or Discord. Fans get a second-screen app that speaks their language and
backs their club. Producers can question the live match from GitHub Copilot over MCP.

## What problem it solves
Broadcast data today is either a stream of numbers for analysts or generic commentary for everyone. Studios cannot
explain tactical changes as they happen, cannot trust generative text on air, and cannot afford a separate production
for every market and fan. Regista makes explanation automatic, auditable and personal, and it keeps working when the
AI fails.

## What makes it different
- Receipts: every on-air claim carries the evidence event ids behind it and passes a deterministic fact check.
- Graded explainability: the simulator logs ground truth, so press-shift detection is measured (52% recall,
  0.6 false alarms per match, onset within 2 minutes), and so is the live xG model (bias −0.007).
- Two lanes: deterministic graphics in milliseconds, generative copy upgraded in place; a chaos switch proves the
  broadcast survives a model outage.
- A realistic synthetic league: 14/14 match statistics inside top-flight reference ranges.
- Tested on a real model (Microsoft Foundry gpt-4.1-mini): 100% of moments air model-written, verified copy in
  English, Spanish and Arabic; 83% of first drafts pass the fact-check untouched; median 5.0 s per story.

## Microsoft and GitHub technologies
Microsoft Agent Framework (agents, workflow with switch-case retry edges, function tools, OpenTelemetry) · Microsoft
Foundry (project + gpt-4.1-mini, Entra ID) · Azure Container Apps · Azure Event Hubs · Application Insights · Azure
Container Registry + managed identity · Azure Developer CLI (Bicep) · Model Context Protocol · GitHub Copilot agent mode
(custom agent + MCP config) · GitHub Actions.

## Links
- Repository: https://github.com/iSharaf6/regista
- Demo video (< 2 min): <YouTube or Vimeo URL>
- Live demo: https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io

## Testing instructions
1. **Live demo:** open https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io; it plays the demo match automatically (the first load after a quiet spell takes
   about 20 seconds while the container starts). Try the Fan Studio presets, the **Two fans**
   tab, **Control room → Simulate model outage**, click any key moment for its receipts, and ask the Pundit a question.
2. **Locally, no keys:** `cd backend && uv venv --python 3.12 && uv pip install -e ".[dev]" && .venv/bin/regista serve`,
   then `cd web && npm install && npm run dev` and open http://localhost:5173.
3. **With a model:** `REGISTA_LLM=foundry` with `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL` (Entra ID), then
   `regista llm-eval` to score the live agents.
4. **Tests and evaluation:** `pytest -q` (26 tests) and `regista evaluate --matches 20`.
5. **Real-world integrations:** `regista publish --url https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io` streams a match through the live feed API;
   `https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/api/onair?mode=casual&lang=es` is the vMix/CasparCG feed. See `docs/real-world.md`.
6. **Copilot:** open the repo in VS Code with the API running, enable the `regista` MCP server and use the
   **match-analyst** agent.

All data is synthetic; all clubs, players and venues are fictional.
