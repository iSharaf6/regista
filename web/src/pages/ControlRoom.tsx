import { useEffect, useMemo, useRef, useState } from "react";
import { AgentGraph } from "../components/AgentGraph";
import { Transport } from "../components/Transport";
import { UseLive } from "../components/UseLive";
import { useFeed } from "../lib/feed";
import { defaultProfile } from "../lib/types";


export function ControlRoom() {
  const profile = useMemo(() => defaultProfile({ id: "ops", mode: "analyst" }), []);
  const feed = useFeed(profile, { ops: true });
  const [fail, setFail] = useState(0);
  const [lat, setLat] = useState(0);
  const serverChaos = feed.control?.chaos;
  useEffect(() => {
    if (!serverChaos) return;
    setFail(Math.round(serverChaos.fail_rate * 100));
    setLat(Math.round(serverChaos.latency_ms));
  }, [serverChaos?.fail_rate, serverChaos?.latency_ms]);
  const sum = feed.ops?.telemetry?.agents ?? {};
  const totals = feed.ops?.telemetry?.totals ?? {};
  const breaker = feed.ops?.breaker ?? feed.control?.breaker;
  // the Rewriter re-runs the Narrator and the Localizer: its work shows up as their second-draft spans
  const rewrites = feed.spans.filter((x) => x.attempt > 1 && (x.agent === "Narrator" || x.agent === "Localizer"));
  const lastRewrite = rewrites[rewrites.length - 1];
  const pulses = usePulses(lastRewrite ? { ...feed.lastSpanByAgent, Rewriter: lastRewrite } : feed.lastSpanByAgent);
  const graphStats = { ...sum, Rewriter: rewrites.length ? `${rewrites.length} second drafts` : "second drafts" };
  const stories = Object.entries(feed.stories).slice(-14).reverse();
  const chaos = (fr: number, l: number) => {
    setFail(fr);
    setLat(l);
    feed.control$("chaos", { fail_rate: fr / 100, latency_ms: l });
  };
  return (
    <div className="page">
      <div className="kpis">
        <div className="kpi"><span>Model</span><b style={{ fontSize: 15 }}>{feed.llm?.model ?? "-"}</b></div>
        <div className="kpi"><span>Circuit breaker</span><b style={{ color: breaker?.state === "open" ? "var(--bad)" : breaker?.state === "half_open" ? "var(--warn)" : "var(--ok)" }}>{breaker?.state ?? "-"}</b></div>
        <div className="kpi"><span>Agent steps ok</span><b>{totals.ok ?? 0}</b></div>
        <div className="kpi"><span>Verifier rejections</span><b>{totals.rejected ?? 0}</b></div>
        <div className="kpi"><span>Fallbacks</span><b>{totals.fallback ?? 0}</b></div>
        <div className="kpi"><span>Story queue</span><b>{feed.ops?.queue ?? 0}</b></div>
        <div className="kpi"><span>Event bus</span><b style={{ fontSize: 15 }}>{feed.ops?.bus?.name ?? "-"} · {feed.ops?.bus?.published ?? 0}</b></div>
      </div>
      <div className="card graph" style={{ marginBottom: 16 }}>
        <header><h3>Agent graph</h3><span className="muted" style={{ fontSize: 12 }}>Microsoft Agent Framework workflow · nodes flash as spans arrive</span></header>
        <div className="body"><AgentGraph stats={graphStats} pulses={pulses} flowing={!!feed.control?.playing} /></div>
      </div>
      <div className="ops-grid">
        <section className="stack">
          <Transport feed={feed} />
          <div className="card">
            <header><h3>Story jobs</h3></header>
            <div className="body table-wrap">
              <table className="log">
                <thead><tr><th>Moment</th><th>Drafts</th><th>Verified</th><th>Fallback</th><th>Latency</th></tr></thead>
                <tbody>
                  {stories.map(([mid, s]) => (
                    <tr key={mid}>
                      <td>{feed.moments.find((m) => m.id === mid)?.headline ?? mid}</td>
                      <td className="mono">{s.attempts}</td>
                      <td>{s.verdict?.ok ? <span className="verified">✓ {s.verdict.numbers_supported}/{s.verdict.numbers_checked}</span> : "✗"}</td>
                      <td>{s.fallback_langs?.length ? s.fallback_langs.join(",") : "-"}</td>
                      <td className="mono">{Math.round(s.latency_ms)} ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!stories.length && <div className="empty">Press play. Story-lane moments (goals, tactical shifts, big chances) run through the agent workflow.</div>}
            </div>
          </div>
        </section>
        <section className="stack">
          <UseLive profile={profile} />
          <div className="card">
            <header><h3>Chaos engineering</h3></header>
            <div className="body stack">
              <div className="muted" style={{ fontSize: 13 }}>Inject model failures and latency. The breaker opens, agents fall back to grounded templates, and the broadcast never goes dark.</div>
              <label className="field">Model failure rate · {fail}%
                <input type="range" min={0} max={100} value={fail} onChange={(e) => chaos(Number(e.target.value), lat)} />
              </label>
              <label className="field">Added model latency · {lat} ms
                <input type="range" min={0} max={5000} step={100} value={lat} onChange={(e) => chaos(fail, Number(e.target.value))} />
              </label>
              <div className="row">
                <button className="btn danger" disabled={!feed.connected} onClick={() => chaos(100, 800)}>Simulate model outage</button>
                <button className="btn" disabled={!feed.connected} onClick={() => chaos(0, 0)}>Restore</button>
              </div>
              {breaker && (
                <div className="kv">
                  <span className="k">Breaker trips</span><span className="mono">{breaker.trips}</span>
                  <span className="k">Consecutive failures</span><span className="mono">{breaker.consecutive_failures}</span>
                  <span className="k">Re-probe in</span><span className="mono">{breaker.reopens_in_s}s</span>
                </div>
              )}
            </div>
          </div>
          <div className="card">
            <header><h3>Live spans</h3></header>
            <div className="body table-wrap">
              <table className="log">
                <thead><tr><th>Agent</th><th>Status</th><th>ms</th><th>Detail</th></tr></thead>
                <tbody>
                  {feed.spans.slice().reverse().slice(0, 60).map((s) => (
                    <tr key={s.id}>
                      <td><b>{s.agent}</b></td>
                      <td><span className={`status ${s.status}`}>{s.status}</span></td>
                      <td className="mono">{s.ms.toFixed(1)}</td>
                      <td className="muted" style={{ fontSize: 12 }}>{s.detail || s.model}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="card">
            <header><h3>Director decisions per viewer</h3></header>
            <div className="body table-wrap">
              <table className="log">
                <thead><tr><th>Viewer</th><th>Shown</th><th>Filtered</th><th>Rate-limited</th><th>Slot busy</th></tr></thead>
                <tbody>
                  {Object.entries(feed.ops?.directors ?? {}).map(([vid, d]: any) => (
                    <tr key={vid}>
                      <td>{d.profile.mode} · {d.profile.language}{d.profile.favorite_team ? ` · ${d.profile.favorite_team}` : ""}</td>
                      <td className="mono">{d.shown}</td><td className="mono">{d.filtered}</td><td className="mono">{d.rate_limited}</td><td className="mono">{d.slot_busy}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function usePulses(last: Record<string, any>) {
  const [p, setP] = useState<Record<string, { k: string; bad: boolean }>>({});
  const seen = useRef<Record<string, string>>({});
  useEffect(() => {
    const next: Record<string, { k: string; bad: boolean }> = {};
    let changed = false;
    for (const [agent, span] of Object.entries(last)) {
      if (seen.current[agent] !== span.id) {
        seen.current[agent] = span.id;
        next[agent] = { k: span.id, bad: ["error", "timeout", "rejected", "fallback", "skipped"].includes(span.status) };
        changed = true;
      }
    }
    if (changed) setP((x) => ({ ...x, ...next }));
  }, [last]);
  return p;
}
