import { useEffect, useState } from "react";
import { api } from "../lib/feed";

const pct = (v: number | undefined) => (typeof v === "number" ? `${Math.round(v * 100)}%` : "-");
const secs = (ms: number | undefined) => (typeof ms === "number" ? `${(ms / 1000).toFixed(1)} s` : "-");

/** The realism report's metrics as a fan reads them (per team, per match). */
const one = (v: number) => v.toFixed(1);
const REALISM: Record<string, { label: string; fmt: (v: number) => string }> = {
  passes: { label: "Passes", fmt: (v) => String(Math.round(v)) },
  pass_accuracy: { label: "Pass accuracy", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  shots: { label: "Shots", fmt: one },
  shots_on_target_share: { label: "Shots on target", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  xg: { label: "xG", fmt: (v) => v.toFixed(2) },
  goals: { label: "Goals", fmt: (v) => v.toFixed(2) },
  xg_per_shot: { label: "xG per shot", fmt: (v) => v.toFixed(2) },
  fouls: { label: "Fouls", fmt: one },
  corners: { label: "Corners", fmt: one },
  yellow_cards: { label: "Yellow cards", fmt: one },
  tackles: { label: "Tackles", fmt: one },
  interceptions: { label: "Interceptions", fmt: one },
  outfield_distance_km: { label: "Distance per outfield player", fmt: (v) => `${one(v)} km` },
  top_speed_kmh: { label: "Top sprint speed", fmt: (v) => `${one(v)} km/h` },
};

/** The live agents scored against the real model (docs/llm-eval.json, written by `regista llm-eval`). */
function ModelEval({ llm, grounding }: { llm: any; grounding: any }) {
  const model = String(llm.model ?? "").replace(/^foundry:/, "");
  const recaps: any[] = llm.recaps ?? [];
  const sample = (llm.pundit ?? [])[0];
  const wf = llm.workflow;
  const one = llm.single_agent_baseline;
  const loop = llm.single_agent_with_checker;
  const planted = Object.values(llm.verifier_probe?.planted_errors ?? {}) as { planted: number; caught: number }[];
  const believable = Object.values(llm.verifier_probe?.believable_errors ?? {}) as { planted: number; caught: number }[];
  const sum = (xs: { planted: number; caught: number }[]) => `${xs.reduce((s, p) => s + p.caught, 0)}/${xs.reduce((s, p) => s + p.planted, 0)}`;
  const share = (frac: string | undefined, v: number | undefined) => (frac ? `${frac} · ${pct(v)}` : pct(v));
  // highlight the best setup in a row, whichever it is: the workflow does not win every comparison
  const best = (vals: (number | undefined)[]) => Math.max(...vals.map((v) => v ?? -1));
  const mark = (v: number | undefined, vals: (number | undefined)[]) => (v !== undefined && v === best(vals) ? "win" : "");
  const seeds: number[] = llm.eval_seeds ?? [];
  return (
    <div className="card">
      <header>
        <h3>Tested on Microsoft Foundry</h3>
        {model && <span className="kind goal">{model}</span>}
      </header>
      <div className="body">
        <div className="kpis">
          <div className="kpi"><span>First draft verified</span><b>{pct(llm.first_draft_verified)}</b></div>
          <div className="kpi"><span>Every language model-written</span><b>{pct(llm.verified_without_fallback)}</b></div>
          <div className="kpi"><span>Template fallbacks</span><b>{llm.jobs_with_fallback ?? "-"}</b></div>
          <div className="kpi"><span>Drafts per moment</span><b>{llm.mean_attempts ?? "-"}</b></div>
          <div className="kpi"><span>Story latency p50 / p95</span><b>{secs(llm.story_latency_ms?.p50)} / {secs(llm.story_latency_ms?.p95)}</b></div>
          <div className="kpi"><span>Pundit answers from tools</span><b>{pct(llm.pundit_used_tools)}</b></div>
          {recaps.length > 0 && <div className="kpi"><span>Recaps verified</span><b>{recaps.filter((r) => r.verified).length}/{recaps.length}</b></div>}
          {believable.length > 0 && <div className="kpi"><span>Believable errors caught</span><b>{sum(believable)}</b></div>}
          {planted.length > 0 && <div className="kpi"><span>Constructed probe caught</span><b>{sum(planted)}</b></div>}
          {grounding && <div className="kpi"><span>Fallbacks wrongly rejected</span><b>{grounding.rejected}/{grounding.outputs.toLocaleString("en")}</b></div>}
        </div>
        {wf && one && (
          <>
            <div className="section-title">Workflow vs a single agent · same model, facts and Verifier</div>
            <div className={`versus ${loop ? "three" : ""}`}>
              <span /><span className="head">Workflow</span>{loop && <span className="head">1 agent + checker</span>}<span className="head">1 agent, one shot</span>
              <span>Moments with every language model-written and checked</span>
              <b className={mark(wf.verified_without_fallback, [wf.verified_without_fallback, loop?.all_languages_verified, one.all_languages_verified])}>{share(wf.moments_model_written, wf.verified_without_fallback)}</b>
              {loop && <b className={mark(loop.all_languages_verified, [wf.verified_without_fallback, loop.all_languages_verified, one.all_languages_verified])}>{share(loop.moments_all_languages, loop.all_languages_verified)}</b>}
              <b className={mark(one.all_languages_verified, [wf.verified_without_fallback, loop?.all_languages_verified, one.all_languages_verified])}>{share(one.moments_all_languages, one.all_languages_verified)}</b>
              {typeof wf.language_outputs_model_written === "number" && (
                <>
                  <span>Language outputs model-written and checked</span>
                  <b className={mark(wf.language_outputs_model_written, [wf.language_outputs_model_written, loop?.language_outputs_verified, one.language_outputs_verified])}>{pct(wf.language_outputs_model_written)}</b>
                  {loop && <b className={mark(loop.language_outputs_verified, [wf.language_outputs_model_written, loop.language_outputs_verified, one.language_outputs_verified])}>{pct(loop.language_outputs_verified)}</b>}
                  <b className={mark(one.language_outputs_verified, [wf.language_outputs_model_written, loop?.language_outputs_verified, one.language_outputs_verified])}>{pct(one.language_outputs_verified)}</b>
                </>
              )}
              <span>Drafts per moment</span><b>{wf.mean_attempts}</b>{loop && <b>{loop.mean_attempts}</b>}<b>1</b>
              <span>Story latency, median</span><b>{secs(wf.latency_ms?.p50)}</b>{loop && <b>{secs(loop.latency_ms?.p50)}</b>}<b>{secs(one.latency_ms?.p50)}</b>
              <span>Model cost per moment</span><b>${wf.cost_usd_per_moment}</b>{loop && <b>${loop.cost_usd_per_moment}</b>}<b>${one.cost_usd_per_moment}</b>
            </div>
            {loop && (
              <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>
                With the same Verifier feedback and two-draft budget, the workflow passes every language without a template for{" "}
                {pct(wf.verified_without_fallback)} of moments; one agent with the checker reaches {pct(loop.all_languages_verified)}.
                Median time is {secs(wf.latency_ms?.p50)} vs {secs(loop.latency_ms?.p50)}. Call deadlines differ:
                workflow {llm.run?.timeout_s ?? 20} s, single agent {llm.run?.baseline_timeout_s ?? 90} s.
                This small sample does not establish a general speed or accuracy advantage. The workflow can recover one failing language independently.
              </div>
            )}
            {typeof wf.first_draft_verified === "number" && (
              <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>
                The workflow's first drafts alone pass for {pct(wf.first_draft_verified)} of moments: the Verifier's notes, sent back to the
                writers, are what lift it to {pct(wf.verified_without_fallback)}.
              </div>
            )}
          </>
        )}
        <div className="muted" style={{ fontSize: 13, marginTop: 10 }}>
          {llm.moments} story-lane moments{seeds.length ? ` from ${seeds.length} fixed evaluation matches` : ""}, in{" "}
          {(llm.languages ?? []).join(", ").toUpperCase()}, the figures, players and selected football claims checked by the deterministic
          Verifier before air. Rejected drafts go back to the agents with the fact-checker's notes; the Verifier itself was tested by
          planting errors in real model copy.
        </div>
        {sample && (
          <div className="bubble" style={{ marginTop: 12 }}>
            <div className="section-title" style={{ margin: "0 0 4px" }}>Pundit, asked live</div>
            <b>{sample.question}</b>
            <div style={{ marginTop: 4 }}>{sample.answer}</div>
            <div className="tools">{(sample.tools ?? []).map((t: string) => <span key={t}>{t}()</span>)}<span>{sample.model}</span></div>
          </div>
        )}
      </div>
    </div>
  );
}

export function Lab() {
  const [ev, setEv] = useState<any>(null);
  const [match, setMatch] = useState<any>(null);
  const [form, setForm] = useState({ home: "NOR", away: "CAL", seed: 16, scenario: "derby" });
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const validSeed = Number.isInteger(form.seed) && form.seed >= 0 && form.seed <= 4294967295;
  useEffect(() => {
    api("/api/evaluation").then(setEv).catch(() => setEv(null));
    api("/api/match").then((m) => { setMatch(m); setForm(m.params); }).catch(() => null);
  }, []);
  const load = async () => {
    if (loading || !validSeed || form.home === form.away) return;
    setLoading(true);
    setMsg("Simulating 95 minutes of football…");
    try {
      await api("/api/control", { method: "POST", body: JSON.stringify({ action: "load", value: form }) });
      setMsg(`Loaded ${form.home} v ${form.away}, seed ${form.seed}, scenario ${form.scenario}. Open Broadcast and press play.`);
    } catch {
      setMsg("Couldn't load this match. Check the connection and match settings, then try again.");
    } finally {
      setLoading(false);
    }
  };
  const ps = ev?.explainers?.press_shift;
  const xg = ev?.explainers?.xg_model;
  const llm = ev?.llm;
  return (
    <div className="page">
      <div className="page-head">
        <h2 className="title-px">Data <span className="y">lab</span></h2>
        <p>
          Every match comes from a seeded, tactically-aware simulator with 5 Hz tracking. Because the engine logs what it actually did
          (true xG, the minute a team changed its press), Regista can measure whether its explanations are right, which no real feed allows.
        </p>
      </div>
      <div className="ops-grid" style={{ marginTop: 16 }}>
        <section className="stack">
          {llm && <ModelEval llm={llm} grounding={ev?.explainers?.template_grounding} />}
          <div className="card">
            <header><h3>Do the explainers tell the truth?</h3><span className="muted" style={{ fontSize: 12 }}>{ev?.explainers?.matches ?? "-"} matches vs hidden ground truth</span></header>
            <div className="body">
              {!ev?.available && <div className="empty">Run <code>regista evaluate</code> and <code>regista realism</code> to populate this page.</div>}
              {ps && (
                <div className="kpis">
                  <div className="kpi"><span>Press-shift recall</span><b>{Math.round(ps.recall * 100)}%</b></div>
                  <div className="kpi"><span>False alarms / match</span><b>{ps.false_alarms_per_match}</b></div>
                  <div className="kpi"><span>Median detection delay</span><b>{ps.median_delay_min} min</b></div>
                  <div className="kpi"><span>Median onset error</span><b>{ps.median_onset_error_min} min</b></div>
                  <div className="kpi"><span>xG model bias</span><b>{xg.bias > 0 ? "+" : ""}{xg.bias}</b></div>
                  <div className="kpi"><span>xG MAE per shot</span><b>{xg.mae}</b></div>
                </div>
              )}
              <div className="muted" style={{ fontSize: 13 }}>
                Press shifts are detected from tracking alone (players within 8 m of the ball in the opponent's build-up, defensive line height),
                never from the score, then the onset is located with a two-segment change-point fit.
              </div>
            </div>
          </div>
          <div className="card">
            <header><h3>Is it football?</h3><span className="muted" style={{ fontSize: 12 }}>per team, per match, vs top-flight reference ranges</span></header>
            <div className="body">
              {ev?.realism?.metrics?.map((m: any) => {
                const [lo, hi] = m.range;
                const span = hi - lo;
                const min = lo - span * 0.5;
                const max = hi + span * 0.5;
                const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100))}%`;
                const r = REALISM[m.metric] ?? { label: m.metric.replaceAll("_", " "), fmt: (v: number) => String(+v.toFixed(2)) };
                return (
                  <div key={m.metric} className="realism-row">
                    <span>{r.label}<small className="muted">reference {r.fmt(lo)}–{r.fmt(hi)} {m.pass ? "✓" : "✗ outside"}</small></span>
                    <div className="range" aria-hidden>
                      <div className="ok-zone" style={{ left: pos(lo), width: `calc(${pos(hi)} - ${pos(lo)})` }} />
                      <div className="val" style={{ left: pos(m.mean) }} />
                    </div>
                    <span className="mono" style={{ color: m.pass ? "var(--ok)" : "var(--bad)" }}>{r.fmt(m.mean)}</span>
                  </div>
                );
              })}
              {ev?.realism && <div className="muted" style={{ fontSize: 13 }}>{ev.realism.passed}/{ev.realism.total} metrics inside reference ranges over {ev.realism.matches} matches.</div>}
            </div>
          </div>
        </section>
        <section className="stack">
          <div className="card">
            <header><h3>Generate a match</h3></header>
            <div className="body stack">
              <div className="row">
                <label className="field" style={{ flex: 1 }}>Home
                  <select aria-label="Home" value={form.home} onChange={(e) => setForm({ ...form, home: e.target.value })}>{(match?.options?.teams ?? ["NOR", "CAL", "ASH", "KES"]).map((t: string) => <option key={t}>{t}</option>)}</select>
                </label>
                <label className="field" style={{ flex: 1 }}>Away
                  <select aria-label="Away" value={form.away} onChange={(e) => setForm({ ...form, away: e.target.value })}>{(match?.options?.teams ?? ["NOR", "CAL", "ASH", "KES"]).map((t: string) => <option key={t}>{t}</option>)}</select>
                </label>
              </div>
              <div className="row">
                <label className="field" style={{ flex: 1 }}>Seed
                  <input type="number" min={0} max={4294967295} step={1} value={form.seed} onChange={(e) => setForm({ ...form, seed: Number(e.target.value) })} />
                </label>
                <label className="field" style={{ flex: 2 }}>Scenario
                  <select aria-label="Scenario" value={form.scenario} onChange={(e) => setForm({ ...form, scenario: e.target.value })}>
                    {Object.entries(match?.options?.scenarios ?? { derby: "", press: "", baseline: "" }).map(([k, d]) => <option key={k} value={k} title={String(d)}>{k}</option>)}
                  </select>
                </label>
              </div>
              <div className="muted" style={{ fontSize: 12 }}>{match?.options?.scenarios?.[form.scenario]}</div>
              {!validSeed && <div role="alert">Seed must be a whole number between 0 and 4294967295.</div>}
              <button className="btn primary" onClick={load} disabled={loading || !validSeed || form.home === form.away}>{loading ? "Simulating…" : "Simulate and load"}</button>
              {msg && <div className="muted" role="status" style={{ fontSize: 13 }}>{msg}</div>}
            </div>
          </div>
          <div className="card">
            <header><h3>Open data and contracts</h3></header>
            <div className="body stack" style={{ fontSize: 13 }}>
              <a href="/api/export/events.jsonl" target="_blank" rel="noreferrer">events.jsonl · synthetic event feed</a>
              <a href="/api/export/cues.json" target="_blank" rel="noreferrer">cues.json · Graphics Cue Protocol output</a>
              <a href="/api/schema/cue" target="_blank" rel="noreferrer">JSON Schema · Cue (GCP v1)</a>
              <a href="/api/schema/event" target="_blank" rel="noreferrer">JSON Schema · MatchEvent</a>
              <a href="/api/schema/frame" target="_blank" rel="noreferrer">JSON Schema · tracking Frame</a>
              <a href="/api/schema/profile" target="_blank" rel="noreferrer">JSON Schema · FanProfile</a>
              <a href="/docs" target="_blank" rel="noreferrer">OpenAPI · REST reference</a>
              <span className="muted">MCP endpoint: <code>/mcp</code> (streamable HTTP, 10 tools)</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
