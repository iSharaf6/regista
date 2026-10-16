import { useEffect, useState } from "react";
import type { Feed } from "../lib/feed";
import { api } from "../lib/feed";
import type { Lang, Moment } from "../lib/types";

export function MomentsList({ feed, onOpen, min = 30 }: { feed: Feed; onOpen: (m: Moment) => void; min?: number }) {
  const items = feed.moments.filter((m) => m.importance >= min).slice().reverse().slice(0, 60);
  if (!items.length) return <div className="empty">Moments appear here as the match unfolds. Press play.</div>;
  return (
    <div className="list">
      {items.map((m) => {
        const story = feed.stories[m.id] ?? m.story;
        return (
          <button className="moment-row" key={m.id} onClick={() => onOpen(m)}>
            <span className="clk">{m.clock}</span>
            <span>
              <span className="hl">{m.headline}</span>
              <span className="meta">
                <span className={`kind ${m.kind === "goal" ? "goal" : ""}`}>{m.kind.replace("_", " ")}</span>
                <span>{m.lane === "story" ? "story lane" : "fast lane"}</span>
                {story && <span className="verified">✓ {story.verdict?.numbers_supported}/{story.verdict?.numbers_checked} · {Math.round(story.latency_ms)} ms</span>}
              </span>
              <span className="imp"><i style={{ width: `${m.importance}%` }} /></span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function Receipts({ moment, feed, onClose, lang }: { moment: Moment; feed: Feed; onClose: () => void; lang: Lang }) {
  const [full, setFull] = useState<any>(null);
  const [tab, setTab] = useState<string>(lang);
  useEffect(() => {
    api(`/api/moments/${moment.id}`).then(setFull).catch(() => setFull(null));
  }, [moment.id, feed.stories[moment.id]]);
  const m = full ?? moment;
  const story = full?.story ?? feed.stories[moment.id];
  const narration = story?.narration ?? {};
  const langs = Object.keys(narration);
  return (
    <>
      <div className="drawer-back" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label="Receipts">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="kind">{m.kind.replace("_", " ")} · {m.clock}</span>
          <button className="btn small" onClick={onClose}>Close</button>
        </div>
        <h2 className="cond" style={{ fontSize: 30, margin: "10px 0 2px", textTransform: "uppercase" }}>{m.headline}</h2>
        <div className="muted">Importance {m.importance}/100 · {m.lane === "story" ? "story lane (agents)" : "fast lane (deterministic)"} · evidence {m.evidence?.join(", ") || "windowed signal"}</div>

        <div className="section-title">Why it matters</div>
        <div className="stack">
          {(m.why ?? []).map((w: any, i: number) => (
            <div key={i} className="card" style={{ padding: 10 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <b>{w.label}</b>
                <span className="mono">{w.value !== null && w.value !== undefined ? (typeof w.value === "object" ? JSON.stringify(w.value) : `${w.value}${w.unit ?? ""}`) : ""}</span>
              </div>
              {w.detail && <div className="muted" style={{ fontSize: 13 }}>{w.detail}</div>}
              {w.factors && (
                <div style={{ marginTop: 6 }}>
                  {w.factors.map((f: any) => (
                    <div className="factor" key={f.label} style={{ fontSize: 12 }}>
                      <span>{f.label} {f.detail ? <span className="muted">· {f.detail}</span> : null}</span>
                      <span className="mono">{f.effect > 0 ? "+" : ""}{f.effect}</span>
                      <div className="bar"><i style={{ left: f.effect >= 0 ? "50%" : `${50 + Math.max(-50, f.effect * 12)}%`, width: `${Math.min(50, Math.abs(f.effect * 12))}%`, background: f.effect >= 0 ? "var(--ok)" : "var(--warn)" }} /></div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {story && (
          <>
            <div className="section-title">Agent trace</div>
            <div className="trace">
              {story.trace.map((s: any) => (
                <div className="step" key={s.id}>
                  <b>{s.agent}</b>
                  <span className={`status ${s.status}`}>{s.status}</span>
                  <span className="muted" style={{ fontSize: 12 }}>{s.detail || s.model}</span>
                  <span className="mono">{s.ms.toFixed(1)} ms</span>
                </div>
              ))}
            </div>
            <div className="section-title">Verifier</div>
            <div className="kv">
              <span className="k">Verdict</span><span className={story.verdict?.ok ? "verified" : ""}>{story.verdict?.ok ? "✓ passed" : "✗ rejected"}{story.verdict?.via ? ` (${story.verdict.via})` : ""}</span>
              <span className="k">Figures grounded in facts</span><span className="mono">{story.verdict?.numbers_supported}/{story.verdict?.numbers_checked}</span>
              <span className="k">Drafts</span><span className="mono">{story.attempts}</span>
              <span className="k">Template fallback</span><span>{story.fallback_langs?.length ? story.fallback_langs.join(", ") : "none"}</span>
              <span className="k">End-to-end</span><span className="mono">{Math.round(story.latency_ms)} ms</span>
            </div>
            {story.verdict?.issues?.length > 0 && (
              <ul className="muted" style={{ fontSize: 12 }}>{story.verdict.issues.map((i: string) => <li key={i}>{i}</li>)}</ul>
            )}
            {story.insight && (
              <>
                <div className="section-title">Analyst insight</div>
                <div className="card" style={{ padding: 10 }}>
                  <b>{story.insight.claim}</b>
                  {story.insight.tactical_read && <div style={{ marginTop: 4 }}>{story.insight.tactical_read}</div>}
                  <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{(story.insight.why ?? []).map((w: string) => <li key={w}>{w}</li>)}</ul>
                </div>
              </>
            )}
            <div className="section-title">On-air copy, every language and persona</div>
            <div className="tabs">{langs.map((l) => <button key={l} className={tab === l ? "on" : ""} onClick={() => setTab(l)}>{l.toUpperCase()}</button>)}</div>
            {narration[tab] && Object.entries(narration[tab]).map(([persona, c]: any) => (
              <div className={`card ${tab === "ar" ? "rtl" : ""}`} style={{ padding: 10, marginBottom: 6 }} key={persona}>
                <div className="kind" style={{ display: "inline-block", marginBottom: 4 }}>{persona.replace("_", " ")}</div>
                <div className="cond" style={{ fontSize: 18, fontWeight: 700 }}>{c.caption}</div>
                <div>{c.line}</div>
                <div className="muted" style={{ fontSize: 13 }}>{c.explainer}</div>
              </div>
            ))}
          </>
        )}
        <div className="section-title">Facts</div>
        <pre className="mono card" style={{ padding: 10, fontSize: 11.5, whiteSpace: "pre-wrap", maxHeight: 260, overflow: "auto" }}>{JSON.stringify(m.facts, null, 1)}</pre>
      </aside>
    </>
  );
}
