import { useEffect, useState } from "react";
import { api } from "../lib/feed";

const pct = (v: number | undefined) => (typeof v === "number" ? `${Math.round(v * 100)}%` : "-");
const secs = (ms: number | undefined) => (typeof ms === "number" ? `${(ms / 1000).toFixed(1)} s` : "-");

/** The live agents scored against the real model (docs/llm-eval.json, written by `regista llm-eval`). */
function ModelEval({ llm, grounding }: { llm: any; grounding: any }) {
  const model = String(llm.model ?? "").replace(/^foundry:/, "");
  const recaps: any[] = llm.recaps ?? [];
  const sample = (llm.pundit ?? [])[0];
  const wf = llm.workflow;
  const one = llm.single_agent_baseline;
  const planted = Object.values(llm.verifier_probe?.planted_errors ?? {}) as { planted: number; caught: number }[];
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
          <div className="kpi"><span>On air verified, no fallback</span><b>{pct(llm.verified_without_fallback)}</b></div>
          <div className="kpi"><span>Template fallbacks</span><b>{llm.jobs_with_fallback ?? "-"}</b></div>
          <div className="kpi"><span>Drafts per moment</span><b>{llm.mean_attempts ?? "-"}</b></div>
          <div className="kpi"><span>Story latency p50 / p95</span><b>{secs(llm.story_latency_ms?.p50)} / {secs(llm.story_latency_ms?.p95)}</b></div>
          <div className="kpi"><span>Pundit answers from tools</span><b>{pct(llm.pundit_used_tools)}</b></div>
          {recaps.length > 0 && <div className="kpi"><span>Recaps verified</span><b>{recaps.filter((r) => r.verified).length}/{recaps.length}</b></div>}
          {planted.length > 0 && <div className="kpi"><span>Planted errors caught</span><b>{planted.reduce((s, p) => s + p.caught, 0)}/{planted.reduce((s, p) => s + p.planted, 0)}</b></div>}
          {grounding && <div className="kpi"><span>Fallbacks wrongly rejected</span><b>{grounding.rejected}/{grounding.outputs.toLocaleString("en")}</b></div>}
        </div>
        {wf && one && (
          <>
            <div className="section-title">Workflow vs one big prompt · same model, facts and checker</div>
            <div className="versus">
              <span /><span className="head">Workflow</span><span className="head">Single agent</span>
              <span>Every language written by the model and checked</span><b className="win">{pct(wf.verified_without_fallback)}</b><b>{pct(one.all_languages_verified)}</b>
              <span>Story latency, median</span><b>{secs(wf.latency_ms?.p50)}</b><b>{secs(one.latency_ms?.p50)}</b>
              <span>Model cost per moment</span><b>${wf.cost_usd_per_moment}</b><b>${one.cost_usd_per_moment}</b>
            </div>
            {typeof wf.first_draft_verified === "number" && (
              <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>
                The workflow's first drafts alone pass for {pct(wf.first_draft_verified)} of moments: the Verifier's notes, sent back to the
                writers, are what lift it to {pct(wf.verified_without_fallback)}.
              </div>
            )}
          </>
        )}
        <div className="muted" style={{ fontSize: 13, marginTop: 10 }}>
          {llm.moments} story-lane moments{seeds.length ? ` from ${seeds.length} held-out matches the prompts never saw` : ""}, in{" "}
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
  useEffect(() => {
    api("/api/evaluation").then(setEv).catch(() => setEv(null));
    api("/api/match").then((m) => { setMatch(m); setForm(m.params); }).catch(() => null);
  }, []);
  const load = async () => {
    setMsg("Simulating 95 minutes of football…");
    await api("/api/control", { method: "POST", body: JSON.stringify({ action: "load", value: form }) });
    setMsg(`Loaded ${form.home} v ${form.away}, seed ${form.seed}, scenario ${form.scenario}. Open Broadcast and press play.`);
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
                return (
                  <div key={m.metric} style={{ display: "grid", gridTemplateColumns: "190px 1fr 80px", gap: 10, alignItems: "center", margin: "8px 0" }}>
                    <span>{m.metric.replaceAll("_", " ")}</span>
                    <div className="range">
                      <div className="ok-zone" style={{ left: pos(lo), width: `calc(${pos(hi)} - ${pos(lo)})` }} />
                      <div className="val" style={{ left: pos(m.mean) }} />
                    </div>
                    <span className="mono" style={{ color: m.pass ? "var(--ok)" : "var(--bad)" }}>{m.mean}</span>
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
                  <select value={form.home} onChange={(e) => setForm({ ...form, home: e.target.value })}>{(match?.options?.teams ?? ["NOR", "CAL", "ASH", "KES"]).map((t: string) => <option key={t}>{t}</option>)}</select>
                </label>
                <label className="field" style={{ flex: 1 }}>Away
                  <select value={form.away} onChange={(e) => setForm({ ...form, away: e.target.value })}>{(match?.options?.teams ?? ["NOR", "CAL", "ASH", "KES"]).map((t: string) => <option key={t}>{t}</option>)}</select>
                </label>
              </div>
              <div className="row">
                <label className="field" style={{ flex: 1 }}>Seed
                  <input type="number" value={form.seed} onChange={(e) => setForm({ ...form, seed: Number(e.target.value) })} />
                </label>
                <label className="field" style={{ flex: 2 }}>Scenario
                  <select value={form.scenario} onChange={(e) => setForm({ ...form, scenario: e.target.value })}>
                    {Object.entries(match?.options?.scenarios ?? { derby: "", press: "", baseline: "" }).map(([k, d]) => <option key={k} value={k} title={String(d)}>{k}</option>)}
                  </select>
                </label>
              </div>
              <div className="muted" style={{ fontSize: 12 }}>{match?.options?.scenarios?.[form.scenario]}</div>
              <button className="btn primary" onClick={load} disabled={form.home === form.away}>Simulate and load</button>
              {msg && <div className="muted" style={{ fontSize: 13 }}>{msg}</div>}
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
