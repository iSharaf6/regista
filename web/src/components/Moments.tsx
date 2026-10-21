import { useEffect, useRef, useState } from "react";
import type { Feed } from "../lib/feed";
import { api } from "../lib/feed";
import type { Lang, MatchInfo, Moment } from "../lib/types";

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
                {story?.verdict?.numbers_checked ? <span className="verified">✓ checked · {story.verdict.numbers_supported}/{story.verdict.numbers_checked} figures</span> : null}
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
  // a real dialog: focus moves in, Tab stays inside, Escape closes, focus returns to the moment that opened it
  const panel = useRef<HTMLElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); close.current(); return; }
      if (e.key !== "Tab" || !panel.current) return;
      const els = panel.current.querySelectorAll<HTMLElement>("button, [href], select, input, textarea, [tabindex]:not([tabindex='-1'])");
      if (!els.length) return;
      const first = els[0];
      const last = els[els.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); opener?.focus(); };
  }, []);
  return (
    <>
      <div className="drawer-back" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="receipts-title" ref={panel}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="kind">{m.kind.replace("_", " ")} · {m.clock}</span>
          <button className="btn small" onClick={onClose} ref={closeBtn}>Close</button>
        </div>
        <h2 id="receipts-title" className="cond" style={{ fontSize: 30, margin: "10px 0 2px", textTransform: "uppercase" }}>{m.headline}</h2>
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

        <div className="section-title">The facts</div>
        <FactTable facts={m.facts ?? {}} kinds={m.fact_kinds ?? {}} match={feed.match} />

        {story && (
          <>
            <div className="section-title">Interpretation (AI, checked against the facts above)</div>
            {story.insight && (
              <div className="card" style={{ padding: 10, marginBottom: 8 }}>
                <b>{story.insight.claim}</b>
                {story.insight.tactical_read && <div style={{ marginTop: 4 }}>{story.insight.tactical_read}</div>}
                <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{(story.insight.why ?? []).map((w: string) => <li key={w}>{w}</li>)}</ul>
              </div>
            )}
            <div className="tabs" role="group" aria-label="Language">{langs.map((l) => <button key={l} className={tab === l ? "on" : ""} aria-pressed={tab === l} onClick={() => setTab(l)}>{l.toUpperCase()}</button>)}</div>
            {narration[tab] && Object.entries(narration[tab]).map(([persona, c]: any) => (
              <div className={`card ${tab === "ar" ? "rtl" : ""}`} lang={tab} style={{ padding: 10, marginBottom: 6 }} key={persona}>
                <div className="kind" style={{ display: "inline-block", marginBottom: 4 }}>{persona.replace("_", " ")}</div>
                <div className="cond" style={{ fontSize: 18, fontWeight: 700 }}>{c.caption}</div>
                <div>{c.line}</div>
                <div className="muted" style={{ fontSize: 13 }}>{c.explainer}</div>
              </div>
            ))}

            <div className="section-title">How it was checked</div>
            <HowChecked story={story} />
          </>
        )}
      </aside>
    </>
  );
}

/** The Verifier's verdict on a story and the agent trace behind it. */
export function HowChecked({ story }: { story: any }) {
  // writer templates and the Analyst's insight are separate: an Analyst fallback is not a template in any language
  // say why only when the trace says why: a timeout or a malformed reply falls back too, and is not a failed check
  const fell = (story.trace ?? []).find((s: any) => s.agent === "Analyst" && s.status === "fallback");
  const analyst = !fell ? story.models?.Analyst ?? "model"
    : /fact check/i.test(fell.detail ?? "") ? "deterministic (the model's insight failed the fact check)"
    : "deterministic fallback";
  return (
    <>
      <div className="kv">
        <span className="k">Verdict</span><span className={story.verdict?.ok ? "verified" : ""}>{story.verdict?.ok ? "✓ passed" : "✗ rejected"}{story.verdict?.via ? ` (${story.verdict.via})` : ""}</span>
        <span className="k">Figures grounded in the facts</span><span className="mono">{story.verdict?.numbers_supported}/{story.verdict?.numbers_checked}</span>
        <span className="k">Drafts</span><span className="mono">{story.attempts}</span>
        <span className="k">Analyst insight</span><span>{analyst}</span>
        <span className="k">Writer copy from templates</span>
        <span>{story.fallback_langs?.length ? story.fallback_langs.join(", ").toUpperCase() : "none: every language model-written"}</span>
        <span className="k">End-to-end</span><span className="mono">{Math.round(story.latency_ms)} ms</span>
      </div>
      {story.verdict?.issues?.length > 0 && (
        <ul className="muted" style={{ fontSize: 12 }}>{story.verdict.issues.map((i: string) => <li key={i}>{i}</li>)}</ul>
      )}
      <div className="trace" style={{ marginTop: 8 }}>
        {(story.trace ?? []).map((s: any) => (
          <div className="step" key={s.id}>
            <b>{s.agent}</b>
            <span className={`status ${s.status}`}>{s.status}</span>
            <span className="muted" style={{ fontSize: 12 }}>{s.detail || s.model}</span>
            <span className="mono">{s.ms.toFixed(1)} ms</span>
          </div>
        ))}
      </div>
    </>
  );
}

const FACT_LABEL = (k: string) => k.replaceAll("_", " ").replace(/\bkmh\b/, "km/h").replace(/\bwp\b/, "win probability");

/** A fact as a fan reads it: player ids as names, a score as "NOR 1 · CAL 0", win probabilities as percentages. */
function factValue(k: string, v: unknown, match?: MatchInfo | null): string {
  if (v === null || v === undefined) return "none";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(Math.abs(v) < 10 ? 2 : 1);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "string") {
    const p = [...(match?.home.players ?? []), ...(match?.away.players ?? [])].find((x) => x.id === v);
    return p ? p.short_name : v;
  }
  if (Array.isArray(v) && k.startsWith("wp") && v.length === 3 && v.every((x) => typeof x === "number")) {
    const [h, d, a] = v.map((x: number) => `${Math.round(x * 100)}%`);
    return `${match?.home.abbr ?? "home"} ${h} · draw ${d} · ${match?.away.abbr ?? "away"} ${a}`;
  }
  if (typeof v === "object" && !Array.isArray(v) && Object.values(v).every((x) => typeof x === "number")) {
    return Object.entries(v).map(([team, n]) => `${team} ${n}`).join(" · ");
  }
  const json = JSON.stringify(v);
  return json.length > 60 ? `${json.slice(0, 57)}…` : json;
}

/** Each fact with what it is: observed in the feed, or estimated by a model. */
export function FactTable({ facts, kinds, match }: { facts: Record<string, unknown>; kinds: Record<string, string>; match?: MatchInfo | null }) {
  const rows = Object.entries(facts);
  if (!rows.length) return <div className="empty">No facts recorded for this moment.</div>;
  return (
    <div className="facts">
      {rows.map(([k, v]) => {
        const kind = kinds[k];
        return (
          <div className="fact" key={k}>
            <span className="k">{FACT_LABEL(k)}</span>
            <span className="mono">{factValue(k, v, match)}</span>
            {kind ? <span className={`fact-kind ${kind === "observed" ? "obs" : "est"}`}>{kind}</span> : <span />}
          </div>
        );
      })}
    </div>
  );
}
