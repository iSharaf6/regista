import { useEffect, useState } from "react";
import { api } from "../lib/feed";
import { LANGS, type Lang } from "../lib/types";

const PERSONAS = [{ id: "casual", label: "Casual" }, { id: "analyst", label: "Analyst" }, { id: "new_fan", label: "New fan" }];

export function Recap({ lang: initial }: { lang: Lang }) {
  const [lang, setLang] = useState<Lang>(initial);
  const [persona, setPersona] = useState("analyst");
  const [data, setData] = useState<any>(null);
  const [series, setSeries] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setErr(null);
    api(`/api/recap?language=${lang}&persona=${persona}`).then(setData).catch((e) => setErr(String(e)));
    api(`/api/series`).then(setSeries).catch(() => setSeries(null));
  }, [lang, persona]);
  const r = data?.recap;
  const rtl = lang === "ar";
  return (
    <div className="page recap">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="seg">{LANGS.map((l) => <button key={l.id} className={lang === l.id ? "on" : ""} onClick={() => setLang(l.id)}>{l.label}</button>)}</div>
        <div className="seg">{PERSONAS.map((p) => <button key={p.id} className={persona === p.id ? "on" : ""} onClick={() => setPersona(p.id)}>{p.label}</button>)}</div>
      </div>
      {err && <div className="empty">{err}</div>}
      {r && (
        <article className={rtl ? "rtl" : ""} dir={rtl ? "rtl" : "ltr"}>
          <div className="section-title">{data.period === "live" ? "Live report so far" : data.period.replace("_", " ")} · automated by the Recap agent · {data.source}</div>
          <h1>{r.headline}</h1>
          <p className="lede">{r.summary}</p>
          <div className="receipt" style={{ fontSize: 12 }}>
            <span className={data.verdict.ok ? "ok" : "fb"}>{data.verdict.ok ? "✓ VERIFIED" : "✗ CHECK"} {data.verdict.numbers_supported}/{data.verdict.numbers_checked} figures</span>
            <span>{data.ms} ms</span>
          </div>
          {series && <WpChart series={series.wp_series} />}
          <div className="section-title">Turning points</div>
          {r.turning_points.map((tp: any, i: number) => (
            <div className="tp" key={i}>
              <span className="clk">{tp.clock}</span>
              <div>
                <div>{tp.text}</div>
                <div>{(tp.evidence ?? []).map((e: string) => <span className="ev" key={e}>{e}</span>)}</div>
              </div>
            </div>
          ))}
          <div className="row" style={{ alignItems: "stretch", marginTop: 18, gap: 14 }}>
            <div className="card" style={{ flex: 1, minWidth: 240 }}>
              <header><h3>Player of the match</h3></header>
              <div className="body">
                <div className="cond" style={{ fontSize: 30, fontWeight: 800 }}>{r.player_of_the_match.name}</div>
                <div className="muted">{r.player_of_the_match.reason}</div>
                {r.player_of_the_match.rating && <div className="hero-stat" style={{ marginTop: 8 }}><b>{r.player_of_the_match.rating}</b><span>rating</span></div>}
              </div>
            </div>
            <div className="card" style={{ flex: 2, minWidth: 280 }}>
              <header><h3>The tactical story</h3></header>
              <div className="body">{r.tactical_story}</div>
            </div>
          </div>
          <p className="lede" style={{ marginTop: 18 }}>{r.closing_line}</p>
        </article>
      )}
    </div>
  );
}

function WpChart({ series }: { series: any[] }) {
  if (!series || series.length < 2) return null;
  const w = 900;
  const h = 140;
  const t0 = series[0].t;
  const t1 = series[series.length - 1].t || 1;
  const x = (t: number) => ((t - t0) / (t1 - t0 || 1)) * w;
  const line = (k: string) => series.map((s) => `${x(s.t)},${h - s[k] * h}`).join(" ");
  const events = series.filter((s) => !String(s.label).endsWith("'") && s.label !== "kick-off");
  return (
    <div className="card" style={{ marginTop: 16, padding: 12 }}>
      <div className="section-title" style={{ marginTop: 0 }}>Win probability path</div>
      <svg viewBox={`0 0 ${w} ${h + 18}`} style={{ width: "100%", height: "auto" }} role="img" aria-label="Win probability over time">
        <line x1="0" x2={w} y1={h / 2} y2={h / 2} stroke="rgba(31,0,36,0.25)" strokeDasharray="6 4" />
        {events.map((e, i) => (
          <g key={i}>
            <line x1={x(e.t)} x2={x(e.t)} y1="0" y2={h} stroke="#e90052" strokeWidth="3" />
            <text x={x(e.t) + 4} y={h + 14} fill="#1f0024" fontSize="11" fontFamily="Silkscreen, monospace" fontWeight="700">{e.clock}</text>
          </g>
        ))}
        <polyline points={line("draw")} fill="none" stroke="#9a968a" strokeWidth="2" strokeDasharray="5 4" />
        <polyline points={line("home")} fill="none" stroke="#0E7C7B" strokeWidth="4" strokeLinejoin="miter" />
        <polyline points={line("away")} fill="none" stroke="#E4572E" strokeWidth="4" strokeLinejoin="miter" />
      </svg>
    </div>
  );
}
