# Demo video script: 1 minute 55 seconds

Rules recap: under 2 minutes, show the project running, no third-party trademarks or copyrighted music.
Everything on screen is synthetic (fictional clubs and players). Use royalty-free music or none.

**Setup before recording**
- `regista serve` with `REGISTA_LLM=foundry` + `FOUNDRY_PROJECT_ENDPOINT` + `FOUNDRY_MODEL` (so the receipts show a real model name), and `npm run dev`.
- Demo match: Northbridge Rovers v Port Calder, seed 16 (the default). Browser at 1440×900.
- Pre-open tabs: Broadcast, Two fans, Control room, Recap, and VS Code with Copilot agent mode + the `regista` MCP server.

**What happens in the demo match (verified from the pipeline output)**
| Minute | Event | What Regista says |
|---|---|---|
| 20' | Valdane 1-0 | a 0.045 xG strike, "against the odds"; Northbridge win probability 41% → 75% |
| 37' | Pellegrini 1-1 | 0.24 xG; Northbridge 77% → 37% |
| 59' | *(ground truth)* Northbridge switch to an all-out high press | detected at **63'**, onset estimated **60'**: players within 8 m of the ball in Port Calder's build-up 0.71 → 1.35, defensive line 32 m → 37 m, z = 6.4 |
| 69' | Red card, Fontes (Northbridge) | ten men |
| 74' | Valdane 2-1 | Northbridge win probability 14% → 76% |
| 88' | Port Calder chase the game | press shift detected (onset 83') |

**Shot list**
| Time | Shot | Voice-over (suggested) |
|---|---|---|
| 0:00–0:10 | Broadcast tab, kick-off, players moving, a name tag pops over Valdane | "Football stories don't end at the scoreline. This is Regista: one synthetic match feed in, a different, explainable broadcast out for every fan." |
| 0:10–0:25 | Seek to 19', play at 4×. Valdane scores: lower third, win-probability bar swings; point at the receipts row | "Every graphic is a timed cue. This goal moved Northbridge from 41 to 75 percent, and the receipt shows exactly which events prove it and which agent wrote the line." |
| 0:25–0:40 | Click the goal in *Key moments* → receipts drawer: factors, agent trace Analyst → Narrator → Localizer → Verifier, copy in 5 languages | "Behind it are Microsoft Agent Framework agents: an Analyst explains why, a Narrator writes for three audiences, a Localizer adapts it, and a Verifier checks every number before it airs." |
| 0:40–0:58 | Two fans tab around 37': left Analyst EN, right Port Calder fan in Arabic (right-to-left, partisan caption) | "Same second, two broadcasts. The Director agent re-cuts graphics, language and voice per viewer, down to partisan captions." |
| 0:58–1:15 | Broadcast, seek to 62', tactical lens on: the 63' tactical-shift card (0.71 → 1.35 near the ball, line 32 → 37 m) | "At the hour Northbridge changed their plan. Regista spotted it from tracking data alone, placing it at 60 minutes. Our simulator logged the truth, 59, so we can grade it." |
| 1:15–1:30 | Control room → *Simulate model outage*: nodes flash red, breaker opens, cues keep airing with FALLBACK tags; then *Restore* | "Cut the model mid-match: the circuit breaker trips, grounded templates take over, and viewers never see a gap." |
| 1:30–1:42 | VS Code: Copilot agent mode, match-analyst agent: "Why did Northbridge take control after the hour?" → MCP tool calls | "The live match is also an MCP server, so GitHub Copilot or a Foundry agent can question it and get grounded answers." |
| 1:42–1:55 | Recap tab (Arabic, then English), then the Data lab scoreboard | "Automated recaps in five languages, realism checked against top-flight ranges, explanations graded against ground truth. Regista: every match, made for every fan, one `azd up` from Azure." |

Tips: record at 4× playback, cut the waits, and keep the cursor still while the overlays animate.
