# Demo video: "One goal, different fans" (1:55)

**The idea in one line:** Regista helps one producer turn a synthetic match feed into explanations for different
audiences, with evidence they can inspect and essential graphics that keep running when generation fails.
**Tagline:** *Match stories for different fans. Evidence for the producer.*

Keep the same event all the way through: the **74' goal** (Valdane, 1–1 → 2–1, Northbridge down to ten men). Use the
same fan names, clock and wording in the film, the cover and the screenshots.

**The cast** (fictional, like the whole league; lower thirds are in `docs/media/video/`)
| | What they need | Preset |
|---|---|---|
| **Tom** | the numbers and what they imply | *Tom · analyst · EN* |
| **Amira** | the goal from her club's side, in Arabic (her team just went behind) | *Amira · Port Calder fan · عربي* |
| **Lucía** | an explanation for someone at her first match, in Spanish | *Lucía · first match · ES* |
| **Sam** | Tom's same-language pair: also English, first match | (Explore → *Same language*) |

Rules recap: strictly under 2 minutes, show the project running, no third-party trademarks or copyrighted music (no
Premier League logos or footage). Sound: silence under the voice-over, or crowd noise you made yourself.

Honesty rules for the edit: keep the *Curated replay* / synthetic label visible; label the drill and the outage as
injected; mark any time jump ("20 s later"); never cut so that fresh AI copy looks instant.

---

## Script (115 seconds)

| Time | Picture | Voice-over |
|---|---|---|
| 0:00–0:08 | Broadcast tab, *Tom · analyst · EN*, the 74' goal happens: lower third, win-probability bar jumps | "Seventy-four minutes, one-all, Northbridge down to ten men. Valdane." |
| 0:08–0:28 | **Explore a moment → 74' Goal**: Tom, Amira and Lucía side by side; punch in on each card with its lower third. Then switch to **Same language**: Tom and Sam, both English | "One goal, different fans. Tom gets the numbers. Amira supports the side that just went behind, so she gets it in Arabic, from her side. Lucía is at her first match, so it's explained in Spanish. And it's not just translation: Tom and Sam both read English, and get different explanations." |
| 0:28–0:40 | **Producer output:** Control room → *Use it live* with Amira selected → the overlay in **OBS** (browser source), Arabic, right to left | "For the producer, each audience is a feed. This is Amira's version, live in OBS." |
| 0:40–1:01 | **Correction receipt:** Explore with the **Arabic drill**. Show the labelled planted error, the Verifier's actual finding, the rewritten Arabic draft passing, the other languages untouched; then *The facts*, each tagged observed or model estimate | "Before anything airs, a Verifier checks supported numbers, squad players and selected football claims against the match data. In this labelled drill we planted a wrong goal count in the Arabic draft. It's caught, only Arabic is rewritten, and every other language keeps its copy." |
| 1:01–1:17 | Card `08-outage.png`, then Control room → *Simulate model outage* (label it *injected*): nodes flash red, the breaker opens; the broadcast keeps airing template graphics; *Restore* | "Graphics appear instantly from the match data; the checked AI story upgrades them about twenty seconds later. If the model goes down, the breaker trips and templates keep the essential graphics running." |
| 1:17–1:28 | Control room agent graph, then one Application Insights transaction for that goal (invoke_agent Narrator → chat gpt-4.1-mini) | "Microsoft Agent Framework agents on Microsoft Foundry, on Azure Container Apps. Every step traced." |
| 1:28–1:43 | **Option A (only if you ran the pilot):** a card with the real result, denominators included. **Option B:** Data lab, *Workflow vs a single agent* | A: "We tested it with [N] fans and [N] producers: [the actual finding]." B: "On twenty-four fixed evaluation moments, one-shot AI passed the checker in every language for eighteen. With the checker loop, our workflow reached twenty-one and a single agent with the same loop twenty-three. The loop lifts accuracy; separate writers mean a failure costs one language, not the whole moment." |
| 1:43–1:55 | Back to the three fans; card `09-end.png` with the live link | "Match stories for different fans. Evidence for the producer. This is Regista." |

Cut from earlier versions: the long logo intro, city names, the resource-group tour, the recap tour and dense
benchmark narration. Those details live in the written submission.

---

## How to record it (about 40 minutes)

1. **Open the live site** a minute early (the first load after a quiet spell takes about 20 s):
   https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io. Browser window 1600×900,
   zoom 100%; make text readable in the crop.
2. **The goal live:** Broadcast tab with *Tom · analyst · EN*, drag the slider to 73', play at 4× and record ~15 s.
3. **The fans:** Explore a moment → **74' Goal** (`/#/explore?moment=m055`). Record the three cards for ~10 s, then the
   *Same language* view (Tom and Sam).
4. **OBS:** select Amira in Fan Studio, open Control room → *Use it live*, copy the overlay link, and in OBS add a
   *Browser* source (1920×1080) with it. Record OBS showing the Arabic overlay over any background of your own.
5. **Correction receipt:** `/#/explore?moment=m055&drill=ar`. Scroll through *How it was checked*: the rejected Arabic
   draft with its finding, then the passing rewrite. For the exhausted case (Arabic ends on its template), use
   `drill=ar2`. The first visit to a drill runs the real model (10–40 s); later visits load instantly.
6. **Outage:** Control room, *Simulate model outage*, wait 5 s, cut to Broadcast, then *Restore* (it also switches
   itself off after 90 s).
7. **Azure:** portal → `rg-regista` → Application Insights → *Transaction search* → open one `invoke_agent Narrator`.
8. **Data lab** (only for Option B): scroll to *Workflow vs a single agent*.
9. **Edit** in Clipchamp (free, from Microsoft) or any editor: cards from `docs/media/video/` between clips, the fan lower
   thirds over the crops, captions on. Hard cuts; it matches the pixel style.
10. **Voice-over:** read it slowly, about 95 seconds of speech.
11. Export 1080p, check it's under **1:58**, upload to YouTube (Unlisted or Public), paste the link on the project page.
12. Before submitting, show the film to one technical person and one person who hasn't seen Regista. Ask them to write:
    who it's for, what's distinctive, what convinced them, what they doubt. Fix any repeated misunderstanding.
