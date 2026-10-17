# Submission text (Hackathon Website → Projects)

## Project name
Regista: the multi-agent match director

## Category
Best Multi-Agent Orchestration (also eligible for the Grand Prizes)

## Elevator pitch
Regista turns one synthetic match feed into different, evidence-backed explanations for every fan. Producers can
inspect the factual basis of every graphic, and essential graphics keep airing when generative AI is unavailable.

Microsoft Agent Framework agents on Microsoft Foundry divide the work: an Analyst explains why a moment matters, a
Narrator and per-market Localizers write in parallel for three audiences in five languages, and a deterministic
Verifier checks their figures, players and football claims against match data before anything airs. Failed drafts go
back with the exact issues; after two failures a grounded template airs instead. Per-viewer Directors then re-cut the
broadcast, so the same goal reaches an English analyst, an Arabic-speaking supporter of the other side and a newcomer as
three different experiences, rendered through a timed Graphics Cue Protocol that drives a web overlay, an OBS/vMix
page and an MCP server GitHub Copilot can question live.

## Who uses it, and how
First user: a **producer running a live match for several markets at once**. They push their feed to `POST /api/feed`,
drive their existing vMix, CasparCG or OBS graphics from `GET /api/onair` (already personalised per market), open any
graphic's receipt to see the facts behind it, and keep airing through a model outage. The same output reaches fans as a
second-screen app in their language, and club media teams as checked goal, tactical-shift and recap posts in Slack,
Teams or Discord.

## What problem it solves
Broadcast data today is either a stream of numbers for analysts or generic commentary for everyone. Studios cannot
explain tactical changes as they happen, cannot trust generative text on air, and cannot afford a separate production
for every market and fan. Regista makes explanation automatic, checkable and personal, and it keeps working when the
AI fails.

## What makes it different (all measured; `docs/*.json`)
- **Orchestration that beats one agent, on held-out matches.** On 24 moments from 4 matches the prompts never
  saw, in 5 languages, with the same model, facts and checker: the workflow put checked copy in every language on air
  for 100% of moments (92% written by the model, the rest by grounded fallback). A single agent writing
  all languages in one call got every language through the same checker for 54% of moments, with nothing to
  catch the rest. The price is latency and tokens: 13.4 s vs 12.3 s median, $0.0073 vs $0.0034 per moment.
- **A checker you can audit.** The Verifier uses match data only, never anything a model produced (the Analyst's
  insight is checked before writers see it). It caught 691 of 691 errors planted in real model
  copy: invented figures, figures with the wrong unit, wrong minutes, wrong goal counts, written-out numbers, uninvolved
  players, contradicted claims. It wrongly rejects 0 of 3,425 fallback outputs. It does not judge causal claims or catch
  invented names from outside the squad, and the README says so.
- **Graded explainability.** The simulator logs ground truth, so tactical detection is measured: press-shift recall 52%,
  0.6 false alarms per match, median detection delay 5 minutes, median onset-estimation error 2 minutes; live xG bias
  −0.007 over 607 shots. Receipts label each fact as observed or a model estimate.
- **Two lanes.** Deterministic graphics in milliseconds, generative copy upgraded in place only once it is checked; a
  chaos switch proves the broadcast survives a model outage.
- **Shared generation, per-viewer selection.** From 1 to 1,000 simultaneous personalised viewers, Director work grows
  from about 0.7 to 7 ms per match-second while model work stays one story job per moment (at most 5 languages).
- **A synthetic league that passes a sanity check:** 14 of 14 aggregate match statistics inside generous top-flight
  bands (consistency of the synthetic data, not a claim that it predicts real football).

## Microsoft and GitHub technologies
Microsoft Agent Framework (agents, workflow with fan-out/fan-in and switch-case retry edges, function tools,
OpenTelemetry) · Microsoft Foundry (project + gpt-4.1-mini, Entra ID) · Azure Container Apps · Azure Event Hubs (every
feed event mirrored for downstream consumers, with a Fabric RTI consumer group) · Application Insights · Azure
Container Registry + managed identity · Azure Developer CLI (Bicep) · Model Context Protocol · GitHub Copilot agent mode
(custom agent + MCP config) · GitHub Actions.

## Links
- Repository: https://github.com/iSharaf6/regista
- Demo video (< 2 min): <YouTube or Vimeo URL>
- Live demo: https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io

## Testing instructions
1. **Live demo:** open https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io; it plays
   the demo match automatically and pauses itself when nobody is watching. Try the Fan Studio presets, the **Two fans**
   tab, **Control room → Simulate model outage** (it switches itself off after 90 s), click any key moment for its
   receipts, and ask the Pundit a question. Playback is shared by everyone on the site.
2. **Locally, no keys:** `cd backend && uv venv --python 3.12 && uv pip install -e ".[dev]" && .venv/bin/regista serve`,
   then `cd web && npm install && npm run dev` and open http://localhost:5173.
3. **With a model:** `REGISTA_LLM=foundry` with `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL` (Entra ID), then
   `regista llm-eval` to score the workflow against the single-agent baseline on held-out matches.
4. **Tests and evaluation:** `pytest -q` (36 tests), `regista evaluate --matches 20` and `regista fanout`.
5. **Real-world integrations:** with the local server from step 2, `regista publish --url http://localhost:8000`
   streams a match through the live feed API (the public site locks that API so nobody can replace its broadcast);
   `https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/api/onair?mode=casual&lang=es`
   is the vMix/CasparCG feed. See `docs/real-world.md`.
6. **Copilot:** open the repo in VS Code with the API running, enable the `regista` MCP server and use the
   **match-analyst** agent.

All data is synthetic; all clubs, players and venues are fictional.
