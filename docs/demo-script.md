# Demo video: one goal, different fans (target 1:55)

**Status:** filming and upload are pending. This is a recording plan, not evidence that a video or OBS test exists.

**Central idea:** one producer turns a synthetic match feed into useful audience-specific explanations, with inspectable evidence and recovery.
**Tagline:** *Match stories for different fans. Evidence for the producer.*

Use the current seed-16 match throughout: **Northbridge 1–2 Port Calder**, **no red cards**. Port Calder score at **48′** and **50′**; Northbridge respond at **63′**, making it 1–2. This is the response goal, not the winner. Open it through `/#/explore?moment=highlight` rather than a generated moment ID.

**Video cards** in `docs/media/video/` match this story: `01-t63.png` opens the film, the fan lower thirds carry no city names, and `09-end.png` carries the tagline. Verify every screenshot against the current build before export.

| Fictional fan | Need | View |
|---|---|---|
| Tom | Numbers and their interpretation | Analyst · English |
| Amira | Her club's perspective in Arabic; Port Calder concede but still lead | Port Calder supporter · Arabic |
| Lucía | Football explained for a newcomer | New fan · Spanish |
| Sam | The same-language comparison with Tom | New fan · English, Explore → Same language |

The required film must be strictly under two minutes and show the functioning project. Use your own synthetic visuals and audio, keep text readable, and include captions. Keep Curated replay and drill labels visible. Label sped-up footage or time jumps; do not make a model upgrade look instantaneous. Offline `regista-offline` responses are deterministic demonstrations, not Foundry-generated copy.

## Recording script

| Time | Picture | Voice-over |
|---|---|---|
| 0:00–0:08 | Card `01-t63.png` (2 s), then the Broadcast goal or the clearly labelled Explore replay at 63′; the score becomes 1–2 | “Sixty-three minutes. Northbridge pull one back. One producer has different audiences to serve.” |
| 0:08–0:28 | Three fans; enlarge each card briefly, then switch to Same language | “Tom gets the numbers. Amira gets her club's perspective in Arabic. Lucía gets football explained in Spanish. Now hold English constant: Tom and Sam see the same goal, with explanations chosen for different levels of football knowledge.” |
| 0:28–0:40 | Select Amira, open Control room's export and show the actual Arabic browser overlay. Show OBS only if it has been tested and recorded | “Each audience has an output the producer can use. This is the Arabic browser overlay, with the same timed cues and right-to-left text.” If OBS was actually validated: “Here it is running as an OBS browser source.” |
| 0:40–1:01 | Explore with `drill=ar`; show its label, rejected Arabic draft, exact finding and passing rewrite; if another language was also rejected on its own, leave it on screen; inspect observed/estimate tags | “The checker compares supported figures, squad names and selected football claims with match data. In this labelled drill, we planted a wrong goal count in Arabic. You can inspect the rejection and correction. Only Arabic is rewritten because of the drill; any other rewrite you see is a genuine rejection.” |
| 1:01–1:17 | Inject an outage in Control room, show essential deterministic output and template labels, then restore | “Essential graphics do not wait for generation. Checked model copy upgrades them later. If generation fails, bounded retries and checked templates keep the core output available.” |
| 1:17–1:28 | Workflow and an actual matching Application Insights trace, with the event identity visible | “Microsoft Agent Framework coordinates the agents. Microsoft Foundry supplies the model; Azure Container Apps serves the app, and Application Insights records the execution.” |
| 1:28–1:43 | One evidence card from the 23 Oct Foundry run (24 new moments, 5 languages, same rules for every system): **Passed the checker in every language: one agent, one shot 12/24 · one agent + checker 18/24 · Regista agents 21/24 · median 9.7 s vs 17.3 s** | “On twenty-four new moments, one AI agent passed the checker in every language twelve times. Give it the checker loop and it's eighteen. Our specialised agents reach twenty-one, in about half the time. And every moment still aired checked copy.” |
| 1:43–1:55 | Return to the three fan cards, show the stable highlight link | “One goal, different explanations, evidence the producer can inspect. Match stories for different fans. This is Regista.” |

## Capture and edit checklist

1. Check the current build and the three goal times above before recording. Warm the app and the chosen Explore view; waiting during generation is real and must not be edited into an instant response.
2. For live footage, seek just before the 63′ goal and record at a clearly labelled playback speed. For a repeatable product explanation, use `/#/explore?moment=highlight` and keep Curated replay visible.
3. Capture `/#/explore?moment=highlight&view=same` for Tom and Sam, then return to the three-fan view.
4. Capture `/#/explore?moment=highlight&drill=ar`; for exhausted retries use `drill=ar2`. Show actual receipt entries, not recreated rejection text. A configured real provider may make billable calls on an uncached request.
5. Confirm the overlay's profile, language and club match the chosen fan. If testing OBS, add its actual link as a Browser source and verify it there; a browser screenshot alone does not establish an OBS integration.
6. Record the labelled outage, then restore. Preserve the distinction between deterministic output, generated copy and fallback.
7. Use a real Foundry trace from the shown build and event. Do not splice a different match's trace into the same-event story. If only an offline run is available, label it and omit the real-model claim.
8. The evidence for the 1:28 card is `docs/llm-eval.json`: the 23 October run on the frozen final build, 24 moments from six never-used seeds in five languages, with both single-agent baselines. Say "passed the checker", never "accurate": acceptance is not human-rated accuracy. Its 20 s (workflow) versus 90 s (single agent) call timeouts mean the speed difference is observed, not a matched-deadline result. The synthetic stress run (`docs/synthetic-stress-2026-10-22.json`, 12 whole matches) is separate: don't merge the two denominators. Earlier reports live under `docs/history/`.
9. Edit with readable crops and captions. Use the new script's wording instead of obsolete image cards. Aim for 1:55 and verify the exported file is strictly under 2:00.
10. Upload to an accepted public-access video host and replace the pending video URL in the submission and project page. Check it signed out before final submission.
11. Ask an unfamiliar viewer to identify the user, value, evidence and limitations after one viewing; correct any repeated misunderstanding.

Do not claim a completed user study, validated external switcher, instantaneous model generation, universally truthful copy or a guaranteed competition result.
