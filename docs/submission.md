# Submission text

## Project
**Regista: the multi-agent match director**

**Category:** Best Multi-Agent Orchestration / Best Multi-Agent System Prize; also eligible for Grand Prize consideration.

## Pitch
One match can demand different explanations: an analyst wants evidence, a newcomer needs context, and a supporter follows their club's story. Regista gives a producer those choices from one synthetic football feed.

Microsoft Agent Framework coordinates analysis, parallel multilingual writing, checking, targeted repair and timed production cues. Microsoft Foundry supplies the language model. Viewers receive explanations selected for their language, club and football knowledge; the producer can inspect source facts, labelled estimates and correction receipts. Essential deterministic graphics remain available when generation fails.

The intended first user is a producer serving several audiences from one feed. This prototype demonstrates that workflow; adoption, production suitability and independent audience benefit still require user testing.

## Start with one goal
The current seed-16 synthetic match finishes **Northbridge 1–2 Port Calder**, with **no red cards**. Port Calder score at **48′** and **50′**; Northbridge respond at **63′** to reduce the deficit to one goal.

[Explore that response](https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/#/explore?moment=highlight): Tom sees the analyst's explanation, Amira sees Arabic copy for a Port Calder supporter, and Lucía gets a newcomer explanation in Spanish. Amira's side has conceded but still leads. The **Same language** view compares Tom and Sam in English, isolating the audience choice from translation. All personas are fictional.

## Purposeful orchestration
- **Analyst:** checks its structured insight before passing it to writers; routine moments use a deterministic explanation.
- **Narrator and Localizers:** write for casual, analyst and newcomer audiences in English, Spanish, French, Arabic and Portuguese.
- **Verifier:** checks supported numeric forms and units, roster names and selected football claims against deterministic match data. It returns specific issues to the affected writer.
- **Recovery:** bounded retries preserve healthy copy; an exhausted writer uses a checked template. The shared workflow completes before the model-written upgrade is delivered.
- **Producer and Director:** schedule versioned Graphics Cue Protocol cues and select them for each viewer's interests, language and knowledge.

[The labelled Arabic drill](https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/#/explore?moment=highlight&drill=ar) deliberately plants a wrong goal count in one draft. Its correction receipt shows the rejection and rewrite. `drill=ar2` exhausts both drafts and shows the template result. These are controlled demonstrations, not naturally occurring model failures or accuracy measurements.

## Evidence and limitations
The simulator and checker were corrected on **22 October 2026**. The standard 20-match evaluation was rerun: **40% press-shift recall (12/30)**, **0.5 false alarms per match**, **5-minute median detection delay** and **1-minute median onset error**. Against engine probabilities, xG MAE is **0.0082 over 560 shots**. All **3,350 language bundles**, containing **10,050 persona copies**, passed the same checker. These are synthetic and checker-acceptance results, not independent factual accuracy.

- `docs/evaluation.json` retains those current results. `docs/realism.json` passes **12/14** aggregate ranges: fouls average **16.525** per team per match against a limit of 16, and tackles **26** against 25. These range misses are separate from the zero checked invariant failures in the additional [12-match synthetic stress run](https://github.com/iSharaf6/regista/blob/main/docs/synthetic-stress-2026-10-22.json), covering 28,337 events and 350,023 tracking frames.
- [The fresh Foundry report](https://github.com/iSharaf6/regista/blob/main/docs/llm-eval.json) covers **24 moments** (4 of each of six kinds) from six never-used seeds (2026102301–2026102306) in all five languages, on the frozen final build. Checked copy aired for **24/24** moments; **20/24** were model-written in every language and **110/120** language outputs were model-written. A single agent got every language through in one shot for **15/24** moments, and **21/24** with the same checker and draft budget. The checker loop is what lifts checker acceptance; splitting the writing across agents matches the single agent's acceptance, finishes faster (p50/p95 **11.9/28.5 s** vs **19.9/67.9 s**) and confines a failure to one language, at about twice the generation cost (**$0.0082** vs **$0.0043** per moment). Workflow calls time out at 20 s and single-agent calls at 90 s; 24 moments is a small sample, and acceptance means passing the checker, not human-rated accuracy. The single-agent prompt did not yet include the agents' new style rule (no feelings or predictions), which the checker enforces, so its acceptance figures are a slight underestimate until the comparison is re-run.
- The same run caught **220/220** hand-written believable mistakes and **724/724** constructed probes (regression tests built around the checker, not independent accuracy) and wrongly rejected **0/120** templates. **4/4** Pundit questions used tools. Of 3 model recaps, 1 was rejected for a wrong score (the app then shows the checked deterministic report), 1 model call failed over to that report, and 1 passed but misspelled Port Calder in Arabic script, which the checker cannot see. Earlier reports are kept in [docs/history](https://github.com/iSharaf6/regista/tree/main/docs/history).
- **147 backend tests pass** on the final tree; **40 frontend harness cases and 21 browser checks** passed. They cover targeted repair, fallback receipts, malformed nested replies, Unicode/count/unit checks, two dismissals, recap freshness and resets. Offline injected clients are labelled controls, not real Foundry output.
- The checker does not establish arbitrary causal claims, translation quality, tone, unknown names outside the roster or names spelled in Arabic script. It rejects claims about what players feel and predictions of what happens next. Pundit answers use tools but do not pass through the story checker.
- Deterministic graphics and model upgrades have different latency. Healthy language results await the workflow's completion; the circuit breaker is shared.
- Event Hubs mirrors feed events for downstream consumers; a Fabric consumer is not implemented. Renderer endpoints and a browser overlay exist; external OBS/vMix/CasparCG operation must be validated before claiming a tested integration.
- The Producer schedules automatically; a human approve/hold/retract console is not implemented. In-process selection timing is not a network load test. Generation estimates exclude hosting and delivery unless explicitly stated.

## Microsoft and GitHub stack
Microsoft Agent Framework agents and workflow, Microsoft Foundry `gpt-4.1-mini` with Entra ID, Azure Container Apps, Azure Event Hubs, Application Insights and OpenTelemetry, ACR and managed identity, Azure Developer CLI/Bicep, MCP, GitHub Copilot agent mode and GitHub Actions.

## Links and submission status
- [Repository](https://github.com/iSharaf6/regista)
- [Live demo](https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io)
- **Required demo video, strictly under two minutes: pending user recording and upload.** Replace `<VIDEO URL>` before submitting.

## Testing instructions
1. Open [Explore](https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/#/explore?moment=highlight), allow for cold-start/loading time, then compare Three fans and Same language. Inspect The facts and How it was checked.
2. Run the labelled Arabic recovery drill. Confirm the rejected draft is separate from the displayed cue and inspect which language was retried or fell back.
3. Open Broadcast, try Fan Studio and Two fans, inspect a moment's receipt, and use Control room → Simulate model outage. Restore it afterwards; the demo also has a timeout. Shared playback is separate from the curated Explore replay.
4. Locally: `cd backend && uv venv --python 3.12 && uv pip install -e ".[dev]" && .venv/bin/regista serve`; then `cd web && npm install && npm run dev`. Open `http://localhost:5173`. With no provider configured, responses are deterministic offline output.
5. Run `cd backend && .venv/bin/pytest -q`. Reproduce synthetic reports with `regista evaluate --matches 20` and `regista realism --matches 20`; `regista fanout` is a local selection microbenchmark.
6. To evaluate a real model, configure `REGISTA_LLM=foundry`, `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL` with Entra ID. `regista llm-eval` makes billable calls and overwrites its report: retain dated output and record the build, seeds and settings.
7. For feed and graphics integration, use the local reference publisher and `/api/onair`, or copy a browser-overlay link from Control room. The public feed is locked against replacing the shared demo. See `docs/real-world.md`.
8. For Copilot, run the API, enable the repository's `regista` MCP server in VS Code and select the `match-analyst` agent.

All data is synthetic; clubs, players and venues are fictional. Final submission still requires the public video URL and submission-form completion.
