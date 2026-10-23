import { useEffect, useRef, useState } from "react";
import { TRUST } from "../components/Moments";
import { api } from "../lib/feed";
import { LANGS, type Lang, type MatchInfo } from "../lib/types";

const PERSONAS = [{ id: "casual", label: "Casual" }, { id: "analyst", label: "Analyst" }, { id: "new_fan", label: "New fan" }];

// the match phase a live report was written in, in the report's own language
const PHASE: Record<string, Record<string, string>> = {
  first_half: { en: "first half", es: "primera parte", fr: "première période", ar: "الشوط الأول", pt: "primeiro tempo" },
  half_time: { en: "half time", es: "descanso", fr: "mi-temps", ar: "بين الشوطين", pt: "intervalo" },
  second_half: { en: "second half", es: "segunda parte", fr: "seconde période", ar: "الشوط الثاني", pt: "segundo tempo" },
  full_time: { en: "full time", es: "final del partido", fr: "fin du match", ar: "نهاية المباراة", pt: "fim de jogo" },
};

export function Recap({ lang: initial }: { lang: Lang }) {
  const [lang, setLang] = useState<Lang>(initial);
  const [persona, setPersona] = useState("analyst");
  const [data, setData] = useState<any>(null);
  const [series, setSeries] = useState<any>(null);
  const [match, setMatch] = useState<MatchInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const asked = useRef(0);
  const [again, setAgain] = useState(0);
  useEffect(() => {
    setErr(null);
    const mine = ++asked.current; // switching language or persona quickly: only the latest answer may render
    api(`/api/recap?language=${lang}&persona=${persona}`)
      .then((d) => { if (mine === asked.current) setData(d); })
      .catch((e) => { if (mine === asked.current) setErr(String(e)); });
    api(`/api/series`).then(setSeries).catch(() => setSeries(null));
    api(`/api/match`).then((m) => setMatch(m.info)).catch(() => setMatch(null));
  }, [lang, persona, again]);
  // a report for another match never renders (the match changed under it); while a new language or persona loads,
  // the previous report keeps its own language and direction, marked as updating, instead of borrowing the new ones
  const foreign = !!(data?.match_id && match?.match_id && data.match_id !== match.match_id);
  const r = foreign ? null : data?.recap;
  const shown = (data?.language as Lang) ?? lang;
  const updating = !!data && (data.language !== lang || data.persona !== persona || foreign);
  const rtl = shown === "ar";
  useEffect(() => { if (foreign) setAgain((n) => n + 1); }, [foreign]); // the match changed: ask for its report
  const phase = data?.as_of?.phase ? PHASE[data.as_of.phase]?.[shown] ?? data.as_of.phase.replace("_", " ") : "";
  return (
    <div className="page recap">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="seg">{LANGS.map((l) => <button key={l.id} className={lang === l.id ? "on" : ""} aria-pressed={lang === l.id} onClick={() => setLang(l.id)}>{l.label}</button>)}</div>
        <div className="seg">{PERSONAS.map((p) => <button key={p.id} className={persona === p.id ? "on" : ""} aria-pressed={persona === p.id} onClick={() => setPersona(p.id)}>{p.label}</button>)}</div>
      </div>
      {err && <div className="empty">{err}</div>}
      {updating && <div className="muted" role="status" style={{ margin: "10px 0" }}>Updating…</div>}
      {r && (
        <article className={`${rtl ? "rtl" : ""} ${updating ? "updating" : ""}`} dir={rtl ? "rtl" : "ltr"} lang={shown}>
          {/* English labels, minutes and figures stay left-to-right inside an Arabic report; the article keeps its RTL alignment */}
          <div className="section-title"><bdi dir="ltr">{data.period === "live"
            ? <>Live report as of {data.as_of?.clock ?? ""}{phase ? <> · <bdi>{phase}</bdi></> : null}</>
            : data.period.replace("_", " ")} · automated by the Recap agent · {data.source}</bdi></div>
          <h1>{r.headline}</h1>
          <p className="lede">{r.summary}</p>
          <div className="receipt" style={{ fontSize: 12 }}>
            <span dir="ltr" className={data.verdict.ok ? "ok" : "fb"}>{data.verdict.ok ? "✓ VERIFIED" : "✗ CHECK"} {data.verdict.numbers_supported}/{data.verdict.numbers_checked} figures</span>
            <span dir="ltr">{data.ms} ms</span>
          </div>
          <p className="trust"><bdi dir="ltr">{TRUST} {data.verdict.numbers_supported}/{data.verdict.numbers_checked}: the figures in this report matched to
            the match data.</bdi></p>
          {series && <WpChart series={series.wp_series} match={match} />}
          <div className="section-title">Turning points</div>
          {r.turning_points.map((tp: any, i: number) => (
            <div className="tp" key={i}>
              <span className="clk" dir="ltr">{tp.clock}</span>
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

function WpChart({ series, match }: { series: any[]; match: MatchInfo | null }) {
  if (!series || series.length < 2) return null;
  const home = { name: match?.home.name ?? "Home", color: match?.home.primary ?? "#0E7C7B" };
  const away = { name: match?.away.name ?? "Away", color: match?.away.primary ?? "#E4572E" };
  const w = 900;
  const h = 150;
  const x0 = 46; // room for the % scale
  const t0 = series[0].t;
  const t1 = series[series.length - 1].t || 1;
  const x = (t: number) => x0 + ((t - t0) / (t1 - t0 || 1)) * (w - x0);
  const y = (p: number) => h - p * h;
  const line = (k: string) => series.map((s) => `${x(s.t)},${y(s[k])}`).join(" ");
  const events = series.filter((s) => !String(s.label).endsWith("'") && s.label !== "kick-off");
  return (
    // a time axis reads left to right in every language: in RTL the minute labels would show as "'63"
    <div className="card" dir="ltr" style={{ marginTop: 16, padding: 12 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="section-title" style={{ margin: 0 }}>Win probability path</div>
        <div className="legend" aria-hidden>
          <span><i style={{ background: home.color }} />{home.name}</span>
          <span><i style={{ background: away.color }} />{away.name}</span>
          <span><i className="dash" />Draw</span>
        </div>
      </div>
      <svg viewBox={`0 0 ${w} ${h + 22}`} style={{ width: "100%", height: "auto", marginTop: 8 }} role="img"
        aria-label={`Win probability over the match: ${home.name}, ${away.name} and the draw, from 0 to 100 percent, with goals and red cards marked`}>
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <g key={p}>
            <line x1={x0} x2={w} y1={y(p)} y2={y(p)} stroke="rgba(31,0,36,0.14)" strokeDasharray={p === 0.5 ? "6 4" : "2 4"} />
            <text x={x0 - 8} y={Math.max(12, y(p) + 4)} textAnchor="end" fill="#5f3a64" fontSize="13" fontFamily="'Lilita One', sans-serif">{Math.round(p * 100)}%</text>
          </g>
        ))}
        {events.map((e, i) => (
          <g key={i}>
            <line x1={x(e.t)} x2={x(e.t)} y1="0" y2={h} stroke="#e90052" strokeWidth="3" />
            {/* a label near the right edge sits left of its line, so the latest minute is never cut off */}
            <text x={x(e.t) > w - 40 ? x(e.t) - 4 : x(e.t) + 4} textAnchor={x(e.t) > w - 40 ? "end" : "start"} y={h + 16} fill="#1f0024" fontSize="13" fontFamily="'Lilita One', sans-serif">{e.clock}</text>
          </g>
        ))}
        <polyline points={line("draw")} fill="none" stroke="#9a968a" strokeWidth="2" strokeDasharray="5 4" />
        <polyline points={line("home")} fill="none" stroke={home.color} strokeWidth="4" strokeLinejoin="miter" />
        <polyline points={line("away")} fill="none" stroke={away.color} strokeWidth="4" strokeLinejoin="miter" />
      </svg>
    </div>
  );
}
