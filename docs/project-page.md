# Innovation Studio project page

This is the current draft to paste into the form. The video remains pending; do not treat this document as proof of submission. Verify media against the corrected build before upload.

## Title
Regista: the multi-agent match director

## Tagline
Match stories for different fans. Evidence for the producer. Microsoft Agent Framework and Foundry turn one synthetic feed into audience-specific explanations, timed graphics and inspectable recovery.

## Keywords
multi-agent, Microsoft Agent Framework, Microsoft Foundry, Azure Container Apps, Azure Event Hubs, Application Insights, MCP, GitHub Copilot, sports broadcasting, personalization, multilingual, explainable AI

## Description

**Category: Best Multi-Agent Orchestration / Best Multi-Agent System Prize**; also eligible for Grand Prize consideration.

### One goal, different questions
At 63′, Northbridge pull one back against Port Calder: **1–2**. Tom wants the numbers. Amira supports Port Calder and watches in Arabic. Lucía needs football explained in Spanish. Regista shows one producer how to serve those different needs from the same synthetic event.

[Try Explore in one minute](https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/#/explore?moment=highlight). Compare the three fictional fans, then switch to **Same language**: Tom and Sam both read English, with explanations chosen for an analyst and a newcomer. Open the facts and correction receipt to inspect what supports the copy.

The current seed-16 match ends **Northbridge 1–2 Port Calder**. Port Calder score at 48′ and 50′; Northbridge's 63′ goal reduces the deficit. There are no red cards.

### How it works
Microsoft Agent Framework coordinates an Analyst, English Narrator and parallel Localizers. A deterministic Verifier checks supported numbers and units, roster names and selected football claims against match data. A rejected writer receives specific feedback; exhausted retries use checked templates. The Producer schedules Graphics Cue Protocol cues, and a Director selects them for each viewer.

The model runs on Microsoft Foundry. Essential deterministic graphics can appear without waiting for the model; checked generated copy upgrades eligible cues after the workflow completes. Healthy language results currently wait for that completion barrier.

### Inspect the recovery
[Run the labelled Arabic drill](https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/#/explore?moment=highlight&drill=ar). A deliberately planted wrong goal count is rejected; its receipt shows the exact finding and rewrite. Other languages keep their copy. `drill=ar2` shows the exhausted-retry template path. This is an injected demonstration, not a measured natural failure rate.

### Evidence with a defined scope
After the **22 October 2026** simulator and checker fixes, the standard 20-match run detected **12/30 press shifts (40%)**, with **0.5 false alarms per match**, **5-minute median detection delay** and **1-minute median onset error**. The checker accepted **3,350 language bundles / 10,050 persona copies**; xG MAE was **0.0082 over 560 shots** against engine probabilities. The realism report passes **12/14** ranges; fouls (16.525 versus an upper bound of 16) and tackles (26 versus 25) remain outside their bands. Synthetic stress invariants and these aggregate range checks measure different things. The README links the reports and records **147 passing backend tests**, **40 frontend harness cases** and **21 browser checks** covered by the verification runs.

[The fresh Foundry comparison](https://github.com/iSharaf6/regista/blob/main/docs/llm-eval.json) covers **24 moments** from six never-used seeds in all five languages, on the frozen final build. Checked copy aired for **24/24** moments; **20/24** were model-written in every language (**110/120** language outputs). A single agent managed **15/24** in one shot and **21/24** with the same checker loop: the loop lifts accuracy, and splitting the writing across agents matches it while finishing faster (p50/p95 **11.9/28.5 s** vs **19.9/67.9 s**, with 20 s vs 90 s call timeouts) and confining failures to one language, at about twice the cost (**$0.0082** vs **$0.0043** per moment). It caught **220/220** hand-written and **724/724** constructed errors and wrongly rejected **0/120** templates. One Arabic model recap misspelled Port Calder in Arabic script and still passed: the checker cannot verify Arabic spellings of names.

[The separate synthetic stress report](https://github.com/iSharaf6/regista/blob/main/docs/synthetic-stress-2026-10-22.json) covers **12 matches and 350,023 tracking frames** with no checked invariant failures. [Historical reports](https://github.com/iSharaf6/regista/tree/main/docs/history/before-physics-fix-2026-10-22) remain available. A local selection benchmark is not a network load test. The checker does not establish arbitrary causal claims, translation quality or unknown names outside the roster. Pundit answers use tools but do not pass through the story checker.

### Intended use
A producer serving multiple audiences can inspect the same event, choose language and knowledge level, and export a browser overlay or structured `/api/onair` output. Feed ingestion, a reference publisher and MCP tools make the prototype inspectable and extensible. Real provider adapters, external switcher validation, editorial operations and independent user benefit remain adoption work. There is no human approve/hold/retract console.

### Built with
Microsoft Agent Framework · Microsoft Foundry (`gpt-4.1-mini`, Entra ID) · Azure Container Apps · Azure Event Hubs (feed mirror; no implemented Fabric consumer) · Application Insights/OpenTelemetry · Azure Container Registry and managed identity · Azure Developer CLI/Bicep · MCP · GitHub Copilot agent mode · GitHub Actions.

### Links
- [Explore the goal](https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/#/explore?moment=highlight)
- [Live demo](https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io); allow cold-start/loading time.
- [Public source](https://github.com/iSharaf6/regista); local no-key setup and verification commands are in the README and `docs/submission.md`.
- **Required video, strictly under two minutes: `<VIDEO URL>` — pending recording and upload.**

All teams, players, venues and fan personas are fictional. All match data is synthetic.

## Form fields
- Challenge: **The Synthetic Match Insights Engine for Premier League Studio**.
- Writing code: **Yes**; add `https://github.com/iSharaf6/regista` after saving.
- Open for others to join: **No**, unless team preferences change.

## Media preparation
The ten images listed in [capture-manifest.json](img/capture-manifest.json) were refreshed on 22 October from the corrected local build using Microsoft Foundry and synthetic data. They include a real rejected Arabic drill draft, its rewrite and live goal output. This records local capture, not publication of the updated demo. Do not upload old 74′/ten-men/2–1 Northbridge cards as current evidence.

| Refreshed image | Caption |
|---|---|
| `docs/img/explore.jpg` | Northbridge's 63′ response through three fictional fans: English analyst, Arabic supporter and Spanish newcomer |
| `docs/img/explore-same.jpg` | Same language, different needs: Tom and Sam receive different English explanations |
| `docs/img/correction-receipt.jpg` | Labelled Arabic drill: the rejected draft, actual finding and targeted recovery |
| `docs/img/explore-checks.jpg` | Source facts labelled observed or estimated, with the checker result and trace |
| `docs/img/overlay-amira.jpg` | Arabic browser-overlay export, shown with its selected audience; claim OBS operation only after validating it in OBS |

These files are current captures; select the images you want to upload with the submission.

## Before final submission
- [ ] Record and upload the functioning-project video, strictly under 2:00; replace its placeholder in the description and video field.
- [ ] Check the demo and stable highlight link in a private window.
- [ ] Check the repository and video while signed out.
- [ ] Ensure every numerical claim has a matching current artifact and scope; keep historical results explicitly historical.
- [ ] Complete the submission form by **Tuesday 27 October, 23:59 PT / Wednesday 28 October, 5:59 pm Sydney**. Leave time for upload and access checks.

These checks prepare the submission; they do not record that it has already been submitted.
