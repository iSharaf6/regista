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
- **The fact-check loop, tested fairly on held-out matches.** 24 moments from 4 matches the prompts never saw, in 5
  languages, same model and facts: one-shot generation got every language through the Verifier for 18/24 moments.
  With the Verifier's feedback loop, the multi-agent workflow reached 21/24 (117/120 language outputs) and a single
  agent given the same loop and draft budget 23/24 (115/120). The loop is what lifts accuracy; splitting the work
  across agents adds speed (median 18.7 s vs 21.9 s, slowest moment 30 s vs 42 s) and isolation (a failure costs one
  language, not a whole moment), at $0.0076 vs $0.0042 per moment. Every moment aired checked copy: 3 languages fell
  back to grounded templates.
- **A checker you can audit.** The Verifier uses match data only, never anything a model produced (the Analyst's
  insight is checked before writers see it). It caught 235 of 235 hand-written believable mistakes in five languages:
  a wrong tally in digits or words, a false brace, "down to ten" with nine left, a rate per 100 passes called "per
  minute", a wrong minute. It wrongly rejects 0 of 3,425 fallback outputs, and a constructed regression probe (691
  errors built from its own figure pools) also passes. It does not judge causal claims or catch invented names from
  outside the squad, and the README says so.
- **Graded explainability.** The simulator logs ground truth, so tactical detection is measured: press-shift recall 52%,
  0.6 false alarms per match, median detection delay 5 minutes, median onset-estimation error 2 minutes; live xG bias
  −0.007 over 607 shots. Receipts label each fact as observed or a model estimate.
- **Two lanes.** Deterministic graphics in milliseconds, generative copy upgraded in place only once it is checked; a
  chaos switch shows the broadcast staying on air through a model outage.
- **Shared generation, per-viewer selection.** In an in-process selection microbenchmark (no network, no generation),
  1 to 1,000 personalised viewers cost about 0.7 to 7 ms of Director work per match-second, while model work stays one
  story job per moment (at most 5 languages).
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
1. **Start here (1 minute):** open
   https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/#/explore?moment=m055 . This
   **Explore a moment** page is a curated replay of the demo's 74th-minute winner: Tom's (English analyst), Amira's
   (Arabic, supports the side that conceded) and Lucía's (Spanish, first match) broadcasts side by side, with the facts
   behind them and the Verifier's verdict. It runs privately through the same agents; pick any other moment from the list.
   The first page load after a quiet spell can take about 20 s while the container wakes.
2. **The live broadcast:** open the **Broadcast** tab; it plays the demo match automatically and pauses itself when
   nobody is watching. Try the Fan Studio presets, the **Two fans** tab, **Control room → Simulate model outage** (it
   switches itself off after 90 s), click any key moment for its receipts, and ask the Pundit a question. Playback is
   shared by everyone on the site; a match loaded in the Data lab returns to the demo once the room is empty.
3. **Locally, no keys:** `cd backend && uv venv --python 3.12 && uv pip install -e ".[dev]" && .venv/bin/regista serve`,
   then `cd web && npm install && npm run dev` and open http://localhost:5173.
4. **With a model:** `REGISTA_LLM=foundry` with `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL` (Entra ID), then
   `regista llm-eval` to score the workflow against the single-agent baseline on held-out matches.
5. **Tests and evaluation:** `pytest -q` (65 tests), `regista evaluate --matches 20` and `regista fanout`.
6. **Real-world integrations:** with the local server from step 3, `regista publish --url http://localhost:8000`
   streams a match through the live feed API (the public site locks that API so nobody can replace its broadcast);
   `https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/api/onair?mode=casual&lang=es`
   is the vMix/CasparCG feed. See `docs/real-world.md`.
7. **Copilot:** open the repo in VS Code with the API running, enable the `regista` MCP server and use the
   **match-analyst** agent.

All data is synthetic; all clubs, players and venues are fictional.
