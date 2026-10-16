# Demo video script: 1 minute 55 seconds

Rules recap: under 2 minutes, show the project running, no third-party trademarks or copyrighted music.
Everything on screen is synthetic (fictional clubs and players). Use royalty-free music or none, and keep any
Premier League logos out of shot.

**Setup before recording**
- Record the live deployment: https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io
  (Foundry gpt-4.1-mini, so every receipt shows the real model). Open it a minute early: the first load after a quiet
  spell takes about 20 seconds while the container starts.
- Browser window at 1600×900 (or 1440×900), zoom 100%. Close the "How it works" strip after the first shot.
- Pre-open tabs: Broadcast, Two fans, Control room, Recap, Data lab; the Azure portal on resource group `rg-regista`
  (Application Insights → Transaction search); VS Code with Copilot agent mode and the `regista` MCP server.
- Drive the match with the transport bar: the slider jumps to a minute, 4× is the recording speed.

**What happens in the demo match (verified from the pipeline output)**
| Minute | Event | What Regista says |
|---|---|---|
| 20' | Valdane 1-0 | a 0.04 xG header, "against the odds"; Northbridge win probability 41% → 75% |
| 37' | Pellegrini 1-1 | 0.24 xG; Northbridge 77% → 37% |
| 59' | *(ground truth)* Northbridge switch to an all-out high press | detected at **63'**, onset estimated **60'**: players within 8 m of the ball in Port Calder's build-up 0.71 → 1.35, defensive line 32 m → 37 m |
| 69' | Red card, Fontes (Northbridge) | ten men |
| 74' | Valdane 2-1 | Northbridge win probability 14% → 76% |

**Shot list**
| Time | Shot | Voice-over (suggested) |
|---|---|---|
| 0:00–0:08 | Broadcast tab at kick-off: the voxel pitch, floodlit stands, the "How it works" strip, a name tag popping over Valdane | "Football stories don't end at the scoreline. This is Regista: one synthetic match feed in, a different, explainable broadcast out for every fan." |
| 0:08–0:22 | Slider to 19', play at 4×. Valdane scores: lower third, the win-probability bar swings; point at the receipt row (VERIFIED, Narrator, foundry:gpt-4.1-mini, evidence ids) | "Every graphic is a timed cue. This goal moved Northbridge from 41 to 75 percent, and the receipt shows the events that prove it and which agent, on which model, wrote the line." |
| 0:22–0:38 | Click the goal in *Key moments*: the receipts drawer with *Why it matters*, the agent trace (Analyst → Narrator → Localizer → Verifier, each on gpt-4.1-mini) and the copy in every language | "Behind it are Microsoft Agent Framework agents on Microsoft Foundry: an Analyst explains why, a Narrator writes for three audiences, a Localizer adapts it, and a deterministic Verifier checks every number before it airs." |
| 0:38–0:54 | Two fans tab around 37': left an analyst in English, right a Port Calder fan in Arabic, right to left, with different cards | "Same second, two broadcasts. The Director agent re-cuts the graphics, the language and the voice for each viewer." |
| 0:54–1:08 | Broadcast, slider to 62', *Tactical lens* on: the 63' tactical-shift card (0.71 → 1.35 near the ball, line 32 → 37 m) | "At the hour Northbridge changed their plan. Regista spotted it from tracking alone and placed it at 60 minutes; the simulator logged the truth, 59, so we can grade every explanation." |
| 1:08–1:22 | Control room → *Simulate model outage*: nodes flash red, the breaker opens, cues keep airing with FALLBACK tags; then *Restore* | "Cut the model mid-match: the circuit breaker trips, grounded templates take over, and viewers never see a gap." |
| 1:22–1:32 | Azure portal: Application Insights transaction for one story (invoke_agent Narrator → chat gpt-4.1-mini), then the resource group (Container Apps, Event Hubs, Foundry) | "It runs on Azure Container Apps with Event Hubs for ingest, and every agent step is traced in Application Insights." |
| 1:32–1:42 | Broadcast sidebar *Use it live* (overlay, on-air JSON for vMix and CasparCG, MCP), then VS Code: Copilot asks "Why did Northbridge take control after the hour?" over MCP | "Producers drop it into OBS, vMix or CasparCG, and Copilot can question the live match over MCP." |
| 1:42–1:55 | Recap tab (Arabic, then English), then Data lab: *Tested on Microsoft Foundry* (83% first drafts verified, 100% on air verified) | "Automated recaps in five languages, every figure verified, explanations graded against ground truth. Regista: every match, made for every fan." |

Tips: record at 4× and cut the waits, keep the cursor still while the overlays animate, and capture the Arabic
broadcast for a few seconds so the right-to-left layout reads.
