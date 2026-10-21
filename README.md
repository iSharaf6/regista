# REGISTA · the multi-agent match director

![Regista: one match, every fan, every figure checked](docs/media/cover.png)

**Live demo:** https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io (Microsoft Foundry gpt-4.1-mini on Azure Container Apps; the first load after a quiet spell takes about 20 s)

**Try it in one minute:** [Explore a moment](https://ca-registaednsnlttycm2o.calmsea-720b2319.koreacentral.azurecontainerapps.io/#/explore?moment=m055) shows the 74th-minute winner as three fans get it (an English analyst, an Arabic-speaking supporter of the side that conceded, a Spanish newcomer), with the facts behind it and the Verifier's verdict.

> *Regista* (Italian): the deep-lying playmaker who orchestrates a team, and the director who calls the shots in a TV gallery.

**One synthetic match feed in. A different, explainable, verified broadcast out for every fan.**

Regista turns synthetic football events and 5 Hz tracking into match intelligence that explains *why* moments matter, renders it as timed broadcast graphics, and re-cuts the whole broadcast per viewer: an analyst in English, a Port Calder fan in Arabic, a newcomer in Spanish and a player-cam viewer following one midfielder, all from the same feed at the same time.

It is built on **Microsoft Agent Framework** (agents + workflow), runs models on **Microsoft Foundry**, publishes every feed event to **Azure Event Hubs** for downstream consumers, ships as one container on **Azure Container Apps**, traces to **Application Insights**, and exposes the live match to **GitHub Copilot agent mode** and any agent over **MCP**.

![Explore a moment: the same goal as three fans get it](docs/img/explore.jpg)
**Explore a moment**: the same second as three broadcasts, each in its fan's language, with what each fan is shown and why

| | |
|---|---|
| ![Broadcast](docs/img/broadcast.jpg) | ![Two fans](docs/img/compare.jpg) |
| **Broadcast**: the 74th-minute goal with tracked players, name tags, a shot card and a lower third whose figures were checked | **Two fans, two broadcasts**: an English analyst and an Arabic, right-to-left Port Calder fan watch the same second |
| ![Receipts](docs/img/explore-checks.jpg) | ![Data lab](docs/img/lab.jpg) |
| **Receipts**: every fact tagged observed or model estimate, the Verifier's verdict and the agent trace | **Data lab**: the workflow against a single agent with and without the same checker, and 235/235 believable errors caught |
| ![Control room](docs/img/control-room.jpg) | ![Recap](docs/img/recap.jpg) |
| **Control room**: the real agent workflow live, the chaos switch, the circuit breaker, spans and Director decisions | **Recap**: the full-time report written by the Recap agent, checked figure by figure, with the win-probability path |

---

## Why it stands out

1. **Receipts, and a fact-checker with teeth.** Every cue carries the evidence event ids behind it. Before generated copy airs, a deterministic **Verifier** checks it against match data only (never against anything a model produced): every figure it can read, including ordinals, small counts and written-out numbers in five languages; figures with a unit (km/h, metres, %, goals, players, per-minute rates, the match minute) against facts of that kind, so a 33 km/h sprint cannot become "33 goals" and a rate per 100 passes cannot become "per minute"; a goal count next to the scorer's name against that player's tally, and "down to ten" against the players actually left; the squad players it names; and selected football claims (header, penalty, free kick, brace, hat-trick). Writers are told each metric's unit. A failing draft goes back to its writer with the exact issues; after two failures a grounded template airs instead, and unverified copy never replaces the on-air graphic. What it does not check: causal claims, tone, invented names from outside the squad, and a count attached by a pronoun in a later sentence. "Verified" means the copy passed these checks, not that every statement is independently true.
2. **Two lanes, never dark.** A deterministic *fast lane* puts shot cards, pass-quality cards, player tags and speed flashes on screen within milliseconds of the event. A generative *story lane* (Analyst → Narrator → Localizer → Verifier) upgrades the copy **in place** once it passes verification. Pull the plug on the model (Control Room → *Simulate model outage*) and the breaker trips, templates take over, and viewers see no gap.
3. **Explanations you can grade.** Real feeds never tell you *why* a team changed shape, so nobody can check whether an "explainable AI" is right. Our simulator logs what it actually did (true xG per shot, the minute a team switched its press). Regista detects tactical shifts **from tracking alone**: players within 8 m of the ball in the opponent's build-up, and defensive line height. It is then scored against that ground truth. Few entries will be able to measure their explanations at all.
4. **A broadcast contract, not a chat box.** The output is the **Graphics Cue Protocol (GCP v1)**: versioned, machine-readable cues timed on the match clock, with slot, priority, locale, audience, evidence and provenance. They can drive any renderer. The same cues drive our web overlay and a **transparent overlay page for OBS / vMix / CasparCG** (`/#/overlay?mode=analyst&lang=es`).
5. **Personalisation that changes the broadcast, not just the language.** The **Director** scores every cue per viewer: mode, favourite club, favourite player and focus metric. It enforces a cue budget and screen-slot scheduling, picks the language and voice, and writes partisan captions ("GET IN! Valdane" for one fan, "Northbridge score · 1-0" for the other). Player cam keeps a halo on one player and brings back their live stats card throughout the match.

## The pipeline: one feed, five stages

| Stage | What Regista does | Where |
|---|---|---|
| **Ingest** | Seeded, tactically-aware simulator: possession chains, physics-limited 5 Hz tracking for 22 players, set pieces, cards, subs, scripted tactical scenarios and a hidden ground-truth log. Every event is also published to an event bus (in-memory or **Azure Event Hubs**) for downstream consumers; the live pipeline reads the feed directly. | `sim/`, `runtime/bus.py` |
| **Interpret** | A live blackboard of team and player state. Interpretable models with named factors: location xG, a 0–100 **pass difficulty** rating, opponents bypassed per pass, Poisson **win probability**, momentum, a **control-vs-chaos index** scored against the league reference, a press-shift detector (z-test plus change-point onset), and game-rhythm classes. | `intel/` |
| **Explain** | Agent Framework workflow: **Analyst** (why it matters), **Narrator** (3 personas), **Localizer** (es/fr/ar/pt idiom), **Verifier** (grounding + brand safety, retry loop), **Recap** (match report), **Pundit** (Q&A with function tools). | `agents/` |
| **Render** | **Producer** emits GCP cues; the web app renders them over a broadcast-angle pitch (or a tactical cam with a tactical lens showing line heights and the pressing radius). | `agents/producer.py`, `web/` |
| **Personalise** | One **Director** per viewer: relevance, budget, slots, language, persona, partisan captions, player cam. | `agents/director.py` |

```mermaid
flowchart LR
  F[Synthetic feed<br/>events + 5 Hz tracking] --> I[Interpret<br/>MatchState · models · MomentDetector]
  F -.->|mirrored| EH[Azure Event Hubs<br/>fabric-rti consumer group]
  I -->|fast lane, ms| P[Producer · GCP cues]
  I -->|story lane| A[Analyst]
  A --> N[Narrator · EN] --> V{Verifier}
  A --> L[Localizer · es fr ar pt] --> V
  V -->|fail + exact issues| R[Rewriter] --> V
  V -->|exhausted| T[Grounded templates]
  V -->|pass| P
  T --> P
  P --> D1[Director · analyst EN] & D2[Director · fan AR] & D3[Director · player cam]
  I --> M[MCP server<br/>10 tools] --> C[GitHub Copilot agent mode<br/>Foundry agents · any MCP client]
  I --> Q[Pundit agent<br/>function tools]
```

## The agents

| Agent | Kind | Job | When it fails |
|---|---|---|---|
| Interpret (Scout) | deterministic | events + tracking → state, enriched events, moments with `why` factors and evidence | n/a (pure computation) |
| **Analyst** | LLM (`agent_framework.Agent`) | why the moment matters: claim, reasons, tactical read, key numbers; called only for goals, red cards, press shifts and big chances (routine moments use their factor breakdown, saving a model round trip) | deterministic insight from the moment's factors |
| **Narrator** | LLM | caption / line / explainer × casual, analyst, new fan | retry with the Verifier's issues, then template |
| **Localizer** | LLM | native es / fr / ar / pt copy, written in parallel with the Narrator from the same insight (no translation) | per-language rewrite, then template |
| **Verifier** | deterministic | evidence is match data only (facts, context, clock, shirt numbers), never model output; every figure grounded within rounding (digits, ordinals, written-out numbers in 5 languages); figures with units matched to facts of that kind; no uninvolved squad players; football claims (header, penalty, free kick) match the facts; slot length limits; brand safety | n/a (it is the guard) |
| **Producer** | deterministic | GCP cues: kind, slot, timing, priority, provenance | n/a |
| **Director** ×N | deterministic policy | per-viewer relevance, budget, slot scheduling, language, persona, partisan copy | n/a |
| **Recap** | LLM | half-time / full-time report with evidence ids per turning point | verified template recap |
| **Pundit** | LLM + function tools | fan Q&A in five languages, tool calls cited | multilingual intent router over the same tools |

Reliability: per-call timeout, a circuit breaker (opens after 3 consecutive failures and half-opens to probe), fault injection for live demos, OpenTelemetry spans to Application Insights, and a span stream to the Control Room.

## Evidence

| Measure | Result |
|---|---|
| Realism sanity check (20 matches, per team, per match, vs generous top-flight bands in `sim/realism.py`; consistency of the synthetic data, not proof it predicts real football) | **14/14 metrics inside**: 615 passes at 80%, 15.3 shots, 1.50 xG, 1.55 goals, 0.097 xG/shot, 12.0 km per outfield player, 32 km/h median top speed |
| Live xG model vs engine's true scoring probability (607 shots) | bias **−0.007**, MAE **0.009** per shot |
| Press-shift detection from tracking (33 true shifts, 20 matches) | recall **52%**, **0.6** false alarms per match, median detection delay **5 min**, median onset error **2 min** |
| Fallback copy vs the Verifier (`regista evaluate`: every story moment of 20 matches × 5 languages × 3 personas) | **0 of 3,425** template outputs rejected (685 moments), so the fallback that airs when a model fails always passes the same checks |
| Real model on fixed evaluation matches: Microsoft Foundry `gpt-4.1-mini`, 24 moments stratified across 6 kinds from 4 fixed evaluation matches (separate from the demo match the prompts were developed on; their failures have guided repairs) × 5 languages (`regista llm-eval --concurrency 1 --pace 6`; workflow calls time out at 20 s, single-agent calls at 90 s, and latency is as observed under those settings; a small sample, so read it as a direction, not a precise rate) | **Workflow:** every language model-written and checked for **21/24** moments (87.5%) and **117/120** language outputs (97.5%); the other 3 languages aired as checked templates, so all 24 moments aired checked copy. First drafts alone pass for 11/24; mean 1.54 drafts; p50 18.7 s, p95 30.4 s; $0.0076 per moment. **One agent with the same Verifier loop and draft budget:** 23/24 moments (95.8%), 115/120 outputs; p50 21.9 s, p95 42.3 s; $0.0042. **One agent, one shot (no loop):** 18/24 moments (75%), 95/120 outputs; p50 18.2 s; $0.0035. So the checker loop is what lifts accuracy; splitting the writing across agents adds speed and isolation (a failure costs one language, not the moment), not accuracy, in this sample. **Errors:** 235 of 235 hand-written believable mistakes caught (wrong tallies in digits and words, false braces, wrong manpower, per-minute rates, wrong minutes, in 5 languages); a constructed regression probe built from the Verifier's own figure pools caught 691 of 691. The Analyst's model insight passed its own check for 10/24 moments (the rest used the deterministic read). The Pundit used its tools for 100% of questions; 3 of 3 model recaps verified field by field. **Read by hand:** all 24 English moments plus the Spanish and Arabic goals, red cards and press shifts: no wrong figure; one misleading rounding ("0.7 to 0.7", now formatted with the precision that shows the change) and Arabic name transliteration, which the name check cannot see |
| Self-correction loop | a test model that invents a figure and an uninvolved player is rejected by the Verifier, receives the exact issues, and fixes its draft on retry; a model that never listens ends in the grounded fallback; an Analyst that invents a figure is caught before any writer sees its insight |
| Fan-out (`regista fanout`: an in-process selection microbenchmark, no network and no generation) | 1 → 1,000 simulated viewers: about **0.7 → 7 ms** of Director and cue work per match-second (run to run, ±0.3 ms). It shows that per-viewer selection scales; it is not a test of 1,000 networked users with generation active. Model work stays one story job per moment (at most 5 languages) whatever the audience size |
| Tests | 65 end-to-end and unit tests, all offline, about 2 min: the live feed API (including replay/live parity at any batch size), on-air JSON, webhooks, guards and tokens, path containment, stale-result discarding, profile re-cuts, the curated explore replay and its warm-up off the event loop, the demo returning after a custom match, rate limits that ignore forged forwarding headers, the agent loop and timed-out writer retries, the Verifier against poisoned agents, claim binding in 5 languages (a scorer's tally, manpower after one and two red cards, per-minute rates, minutes), recap field checks and freshness, and the pipeline |

Reproduce: `regista realism --matches 20`, `regista evaluate --matches 20`, `regista fanout` and, with a model, `regista llm-eval` (results land in `docs/`; the Data lab page renders them).

## Microsoft and GitHub stack

| Technology | How Regista uses it |
|---|---|
| **Microsoft Agent Framework** | `Agent`s with distinct instructions, a `WorkflowBuilder` graph with switch-case retry edges, `@tool` function tools for the Pundit, a custom `BaseChatClient` for offline runs, and OpenTelemetry instrumentation |
| **Microsoft Foundry** | Foundry project + `gpt-4.1-mini` deployment (Bicep), `FoundryChatClient` with Entra ID / managed identity, no keys |
| **Azure Container Apps** | one container serves API, WebSocket, MCP and the web app; managed identity pulls from ACR |
| **Azure Event Hubs** | every feed event is mirrored to `match-events` for downstream consumers, with a `fabric-rti` consumer group for Fabric Real-Time Intelligence (the in-process pipeline does not depend on it) |
| **Application Insights** | agent runs, chat calls, tool calls and workflow supersteps via Azure Monitor OpenTelemetry |
| **MCP** | 10 live-match tools + a match resource at `/mcp` (streamable HTTP) |
| **GitHub Copilot agent mode** | `.vscode/mcp.json` + a custom `match-analyst` agent (`.github/agents`) + repo instructions |
| **GitHub Actions** | CI runs lint, tests, the ground-truth evaluation, the web build and the image build |
| **Azure Developer CLI** | `azd up` provisions everything above from `infra/` |

## Use it for real, not just as a demo

Regista plugs into an actual production chain, with no simulator required. Full guide: [docs/real-world.md](docs/real-world.md).
- **Live feed API:** any data provider pushes events and 5 Hz tracking to `POST /api/feed`. Ingestion is idempotent and
  validated against JSON Schema, and `regista publish` is a working reference provider.
- **Your own graphics:** `GET /api/onair?mode=casual&lang=ar&team=CAL` returns what that viewer should see right now as
  one flat JSON row. Bind it to vMix Data Sources or CasparCG templates, or add `/#/overlay` as an OBS browser source.
- **Media teams and fan communities:** webhooks post verified goals, red cards, tactical shifts and recaps to Slack,
  Teams or Discord in five languages.
- **Safe in public:** an optional producer token for shared controls, rate-limited Q&A, chaos that switches itself
  off, and a demo that loops itself for judges.

## Run it

**Offline, no keys, about 2 minutes:**

```bash
cd backend && uv venv --python 3.12 && uv pip install -e ".[dev]" && .venv/bin/regista serve
```

```bash
cd web && npm install && npm run dev
```

Open http://localhost:5173, press **Play** (4× is good for watching; 30× to skim) and try:
- Fan Studio presets: *Analyst · EN*, *Port Calder fan · عربي*, *New to football · ES*, *Player cam · Arata*
- **Two fans** for side-by-side broadcasts
- **Control room** → *Simulate model outage*
- Click any key moment to see its **receipts** (factors, agent trace, verifier verdict, copy in every language)
- **Ask the Pundit**: "Why are Northbridge winning the ball so high?"

**With real models:** set `REGISTA_LLM=foundry` with `FOUNDRY_PROJECT_ENDPOINT` + `FOUNDRY_MODEL` (Entra ID, e.g. after `az login`), or `REGISTA_LLM=azure_openai` / `openai`. See `.env.example`. `regista llm-eval` then scores the live agents: first-draft verification rate, retries, fallbacks and latency.

**On Azure:** `azd up` (Foundry project and model, Container Apps, Event Hubs, Application Insights, ACR, managed identity and roles).

**From GitHub Copilot:** start the API, open the repo in VS Code, enable the `regista` MCP server, pick the **match-analyst** agent and ask about the live match.

**Docker:** `docker build -t regista . && docker run -p 8000:8000 regista` then open http://localhost:8000.

## Repository map

```
backend/regista/
  sim/        engine (possession chains + 5 Hz tracking), fictional squads, scenarios, realism report
  intel/      MatchState blackboard, interpretable models, windowed signals, moment detector
  agents/     Agent Framework agents + story workflow, verifier, producer, director, pundit, recap, templates (5 languages)
  runtime/    live session (fast + story lanes), event bus (Event Hubs), observability
  api/        FastAPI REST + WebSocket;  mcp_server.py  MCP tools;  evaluation.py  ground-truth scoring;  cli.py
web/src/      pitch renderer (broadcast + tactical cams), GCP overlay, Fan Studio, Pundit, Control Room, Recap, Data lab
infra/        Bicep for azd: Foundry, Container Apps, Event Hubs, App Insights, ACR, managed identity
docs/         demo script, submission text, Fabric RTI notes, evaluation + realism outputs
```

## Responsible by design
- **Synthetic only.** Every club, player, venue and referee is invented, with no real crests, trademarks or footage. Feeds are reproducible from a seed.
- **Grounded and auditable.** Numbers come from deterministic models with named factors; language models only explain them. Every cue carries evidence ids and provenance (agent, model, verified, fallback, drafts, latency).
- **Brand-safe.** The Verifier blocks betting, gambling and alcohol language in all five languages.
- **Accessible.** Right-to-left layout and Arabic typography, a plain-language *new fan* persona that explains jargon, `prefers-reduced-motion` support, and keyboard-reachable controls.

## Judging criteria map

| Criterion | Where to look |
|---|---|
| Technological implementation | synthetic data with ground truth and a realism report, typed contracts (JSON Schema at `/api/schema/*`), tests and CI, Agent Framework + Foundry + Event Hubs + Container Apps + MCP |
| Agentic design and innovation | Verifier-in-the-loop workflow with targeted retries, two-lane progressive enhancement, per-viewer Director agents, Pundit with function tools, MCP for Copilot |
| Real-world impact | GCP cues and a transparent overlay for production switchers, multilingual by default, chaos-tested reliability, `azd up` deployment |
| User experience | broadcast-grade overlay, Two fans view, Control room, receipts drawer, recap page |
| Category: Best Multi-Agent System | distinct agents, shared state (the StoryJob and MatchState blackboard), hand-offs and loops, failure recovery shown live |

MIT licensed. Built for the Inside the Game developer hackathon.
