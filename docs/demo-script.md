# Demo video: "Three fans, one goal" (1:55)

Most entries will open on a dashboard. This one opens on a moment and three people. Every feature we show answers a
question one of them has, so the judges remember a story, not a feature list.

**The idea in one line:** at 74 minutes Valdane scores the winner. Tom, Amira and Lucía watch the same second and
need three different broadcasts. Regista gives each of them one, and every figure in it is checked against the match data.

**The cast** (fictional, like the whole league; lower thirds are in `docs/media/video/`)
| | Who | What they need | Fan Studio preset |
|---|---|---|---|
| **Tom** | Manchester, analyst, English | the numbers behind every chance | *Tom · analyst · EN* |
| **Amira** | Cairo, Port Calder fan, Arabic | her team just went behind | *Amira · Port Calder fan · عربي* |
| **Lucía** | Madrid, first match ever, Spanish | has no idea what xG means | *Lucía · first match · ES* |

Rules recap: under 2 minutes, show the project running, no third-party trademarks or copyrighted music (no Premier
League logos or footage). Sound: silence under the voice-over, or crowd noise you made yourself, for example Blocky
League's synthesised crowd.

---

## Script

### Act 1 · The goal (0:00–0:24)
| Time | Picture | Voice-over |
|---|---|---|
| 0:00–0:04 | Card `01-t74.png` ("74:12 · Northbridge 1–1 Port Calder. Ten men. One chance.") | "Seventy-four minutes. One-all. Northbridge are down to ten men." |
| 0:04–0:09 | Broadcast tab with *Tom · analyst · EN*: Valdane scores, the lower third bangs in, the win-probability bar jumps | "Valdane. Three people see this goal…" |
| 0:09–0:20 | **Explore a moment → 74' Goal**: the three broadcasts side by side. Punch in on each card in turn with its lower third: `02-fan-tom`, `03-fan-amira`, `04-fan-lucia` | "Tom, in Manchester, wants the numbers. Amira, in Cairo, supports the side that just went behind. And Lucía, in Madrid, is watching her first match ever." |
| 0:20–0:24 | Card `05-problem.png` ("Every fan gets the same broadcast.") | "Today, all three get exactly the same broadcast." |

### Act 2 · Regista (0:24–1:10)
| Time | Picture | Voice-over |
|---|---|---|
| 0:24–0:28 | Card `06-logo.png` | "This is Regista." |
| 0:28–0:42 | *Two fans* tab around the 74' goal: Tom on the left in English, Amira on the right in Arabic, right to left | "AI agents watch every pass, work out *why* each moment matters, and re-cut the broadcast for every viewer, live. Same second, two stories: Tom gets the numbers; Amira gets it in Arabic, from her side." |
| 0:42–0:50 | **The phone shot:** film your hand scanning the *Watch on your phone* QR code on the laptop; on the phone, tap *Lucía · first match · ES* and the Spanish broadcast appears | "Lucía just scans the screen. Her phone becomes her own broadcast: Spanish, and football explained." |
| 0:50–0:53 | Card `07-truth.png` ("Nothing airs unchecked.") | "But AI makes things up." |
| 0:53–1:10 | Back on **Explore a moment**, scroll slowly: *The facts* (each one tagged observed or model estimate), then *How it was checked* (the Verifier's verdict, the agent trace). Cut to the Data lab tile **Believable errors caught 235/235** | "So before anything airs, a Verifier checks every figure, player and key claim against the match data. When a draft gets one wrong, it goes back to the writer with the fact-checker's notes. We wrote two hundred and thirty-five believable mistakes in five languages: it caught every one." |

### Act 3 · The stress test (1:10–1:30)
| Time | Picture | Voice-over |
|---|---|---|
| 1:10–1:13 | Card `08-outage.png` ("What if the AI goes down mid-match?") | "And if the AI goes down in the middle of a live match?" |
| 1:13–1:24 | Control room → *Simulate model outage*: nodes flash red, the breaker opens; cut to the broadcast still airing with TEMPLATE tags; *Restore* | "The circuit breaker trips, grounded templates take over, and not one fan sees a gap." |
| 1:24–1:30 | Azure portal: an Application Insights transaction (invoke_agent Narrator → chat gpt-4.1-mini), then the resource group | "Microsoft Agent Framework agents on Microsoft Foundry, running on Azure, every step traced." |

### Act 4 · Full time (1:30–1:55)
| Time | Picture | Voice-over |
|---|---|---|
| 1:30–1:42 | Recap tab at full time: English ("Valdane's Double Secures Northbridge a 2–1 Victory…"), then switch to عربي, then ES | "At full time each of them gets the story of the match, in their own language, checked figure by figure." |
| 1:42–1:50 | Data lab: *Workflow vs a single agent* (18/24 one shot, 21/24 with the checker loop) | "On matches it had never seen, one-shot AI got every language right three times in four. With the fact-checker in the loop, nearly nine in ten, and nothing unchecked ever airs." |
| 1:50–1:55 | Card `09-end.png` | "Same match. Three fans. Three stories. All of them checked." |

---

## How to record it (about 30 minutes)

1. **Open the live site** a minute early: https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io
   (the first load after a quiet spell takes about 20 s). Browser window 1600×900, zoom 100%.
2. **The three fans (Act 1 and Act 2's checks), one recording:** open **Explore a moment** and pick **74' Goal**
   (or go straight to `/#/explore?moment=m055`). Record the three broadcasts side by side for ~10 s, then scroll slowly
   through *The facts* and *How it was checked*. You'll crop each fan's card in the editor.
3. **The goal live:** Broadcast tab with *Tom · analyst · EN*, drag the slider to 73', play at 4× and record ~15 s around
   the goal. Then the *Two fans* tab at the same point (Tom and Amira side by side).
4. **The phone shot.** On the laptop, Broadcast tab, scroll to *Watch on your phone*. Film with a second phone, or
   screen-record your phone and composite it next to the laptop clip: scan, tap Lucía's preset, the goal plays in Spanish.
5. **Outage:** Control room, *Simulate model outage*, wait 5 s, cut to Broadcast, then *Restore*.
6. **Azure:** portal → `rg-regista` → Application Insights → *Transaction search* → open one `invoke_agent Narrator`.
7. **Full time:** slider to 94', let the whistle go, open Recap (the full-time report holds for 45 s before the match loops).
8. **Data lab:** scroll to *Tested on Microsoft Foundry*: the *Believable errors caught* tile and the *Workflow vs a single agent* table.
9. **Edit** in Clipchamp (free, from Microsoft) or any editor: drop the cards from `docs/media/video/` between clips and
   the transparent fan lower thirds over the three fan crops. Hard cuts, no transitions; it matches the pixel style.
10. **Voice-over:** read it slowly; it runs about 90 seconds of speech, which leaves room for the goal and the outage to breathe.
11. Export 1080p, check it's under **1:58**, upload to YouTube (Unlisted or Public), paste the link on the project page.
