# Innovation Studio project page: what to paste where

Fill the form top to bottom, save, then add the media and the code repository (both unlock after the first save).
Everything below is measured (`docs/*.json`) and matches the README; don't round the numbers up.

---

## Title (max 140)
```
Regista: the multi-agent match director
```

## Tagline (max 300)
```
One match, every fan. Microsoft Agent Framework agents on Microsoft Foundry re-cut the broadcast for each viewer's language, club and football knowledge, and a deterministic Verifier checks every figure against the match data before it airs.
```

## Keywords
```
multi-agent, Microsoft Agent Framework, Microsoft Foundry, Azure Container Apps, Azure Event Hubs, Application Insights, MCP, GitHub Copilot, sports broadcasting, personalization, multilingual, explainable AI, fact-checking
```

## Description (Markdown)
Paste everything between the lines. Replace `<VIDEO URL>` with your YouTube link once it's uploaded.

---
**Category: Best Multi-Agent Orchestration** (also entered for the Grand Prize)

### 74 minutes. One goal. Three fans.
Valdane scores the winner. **Tom**, an analyst in Manchester, wants the numbers. **Amira**, in Cairo, supports the side that just went behind and watches in Arabic. **Lucía**, in Madrid, is at her first match and has no idea what xG means. Today all three get the same broadcast. With **Regista** each gets their own, live, and every figure in it is checked against the match data before it airs.

**Try it in one minute:** [Explore a moment](https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/#/explore?moment=m055) shows the three broadcasts of that goal side by side, with the facts behind them and the Verifier's verdict.

### What it is
A multi-agent match director for a synthetic football feed. It turns events and 5 Hz tracking into explanations of *why* moments matter, renders them as timed broadcast graphics (a Graphics Cue Protocol), and re-cuts the whole broadcast for every viewer: web overlay, OBS/vMix page, on-air JSON for vMix and CasparCG, a phone second screen, and an MCP server that GitHub Copilot can question live.

### How the agents work together
Built with **Microsoft Agent Framework** (agents + a workflow graph with fan-out, fan-in and switch-case retry edges), models on **Microsoft Foundry**:
1. **Analyst** explains why a moment matters. Its own figures are checked before any writer sees them.
2. **Narrator** (English) and **Localizers** (Spanish, French, Arabic, Portuguese) write in parallel for three audiences (casual, analyst, newcomer): native copy, not translation.
3. **Verifier** (deterministic) checks every figure, player and key claim against match data only, never against model output. A rejected draft goes back to its writer with the exact issues; after two failures a grounded template airs instead.
4. **Producer** times the graphics, and a **Director** per viewer re-cuts them for language, club, focus and knowledge.
5. A deterministic **fast lane** airs shot and pass graphics in milliseconds, and a circuit breaker keeps the broadcast on air when the model fails.

### Measured, not claimed
- **Orchestration beats one agent, on matches the prompts never saw.** 24 moments from 4 held-out matches, 5 languages, same model, facts and checker: the workflow got model-written, checked copy into every language for **92%** of moments; one big prompt managed **54%**. The workflow's own first drafts also pass for only 54%: the Verifier's notes are what lift it to 92%. The price: 13.4 s vs 12.3 s median, $0.0073 vs $0.0034 per moment.
- **A checker you can audit.** It caught **691 of 691** errors planted in real model copy (invented figures, wrong units, wrong minutes, wrong goal counts, written-out numbers, uninvolved players, contradicted claims) and wrongly rejected **0 of 3,425** fallback outputs. Its limits are documented: it doesn't judge causal claims or catch invented names from outside the squad.
- **Graded explainability.** The simulator logs ground truth, so tactical detection is measured: press-shift recall 52%, 0.6 false alarms per match. Every receipt labels each fact as observed or a model estimate.
- **Scales by sharing.** From 1 to 1,000 personalised viewers, Director work grows from about 0.7 to 7 ms per match-second while model work stays one story job per moment.

### Who it's for
A **producer running one match for several markets**: push the feed to `POST /api/feed`, drive existing vMix, CasparCG or OBS graphics from `GET /api/onair` (already personalised per market), open any graphic's receipt, and stay on air through a model outage. Fans get it as a second screen (scan the QR code), and club media teams as checked posts in Slack, Teams or Discord.

### Built with
Microsoft Agent Framework · Microsoft Foundry (gpt-4.1-mini, Entra ID, no keys) · Azure Container Apps · Azure Event Hubs (every feed event mirrored, Fabric RTI consumer group) · Application Insights (OpenTelemetry traces of every agent run) · Azure Container Registry + managed identity · Azure Developer CLI (Bicep) · Model Context Protocol · GitHub Copilot agent mode · GitHub Actions.

### Links and testing
- **Live demo:** https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io (the first load after a quiet spell takes about 20 s). Start with **Explore a moment**, then **Broadcast**, **Two fans**, **Control room → Simulate model outage** (it switches itself off after 90 s), **Recap** and **Data lab**.
- **Code:** https://github.com/iSharaf6/regista (runs locally with no keys; 39 offline tests; full testing steps in `docs/submission.md`)
- **Video (under 2 minutes):** <VIDEO URL>

All data is synthetic; all clubs, players and venues are fictional.

---

## Challenge
Select **The Synthetic Match Insights Engine for Premier League Studio**.

## Writing Code
**Yes.** After saving, add the code repository: `https://github.com/iSharaf6/regista`

## Skills Needed / open for others to join
**No** (leave it closed).

## Media (after saving), in this order
| # | File | Caption |
|---|---|---|
| 1 | `docs/media/cover.png` | One match. Every fan. Every figure checked. |
| 2 | `docs/img/explore.jpg` | Same second, three broadcasts: Tom (English analyst), Amira (Arabic, Port Calder fan) and Lucía (Spanish, first match) |
| 3 | `docs/img/explore-checks.jpg` | The receipts: each fact tagged observed or model estimate, the Verifier's verdict and the agent trace |
| 4 | `docs/img/broadcast.jpg` | The live broadcast with tracked players and timed graphics |
| 5 | `docs/img/compare.jpg` | Two fans, two broadcasts, the same second |
| 6 | `docs/img/control-room.jpg` | Control room: the real agent workflow, live, with the outage switch |
| 7 | `docs/img/lab.jpg` | Data lab: the workflow against one big prompt, and 691/691 planted errors caught |
| 8 | `docs/img/recap.jpg` | Full-time recap, written by an agent and checked figure by figure |
| 9 | `docs/img/receipts.jpg` | A graphic's receipt, opened from the broadcast |

Video: paste the YouTube URL wherever the page asks for it, and in the Description's Links section.

## Before you press Submit
- [ ] Video uploaded (Public or Unlisted), under 2:00, link pasted in two places.
- [ ] Live demo opens in a private window, and **Explore a moment** shows the three fans.
- [ ] Repo is public: https://github.com/iSharaf6/regista opens when signed out.
- [ ] Submit by **Tue Oct 27, 23:59 PT** (Wed Oct 28, 5:59 pm Sydney). Aim for Sunday, so a failed upload isn't a crisis.
