import { forwardRef, useEffect, useState } from "react";
import { type Feed, isLive } from "../lib/feed";
import { label } from "../lib/i18n";
import type { Cue, MatchInfo, Snapshot } from "../lib/types";

function active(cues: Cue[], t: number) {
  const now = performance.now();
  // the player-cam card stays pinned between its refreshes; the feed keeps only the latest one
  return cues.filter((c) => !["score_bug", "momentum"].includes(c.kind) && (c.kind === "player_focus" || isLive(c, t, now)));
}

function newest(cues: Cue[], slot: string) {
  const xs = cues.filter((c) => c.slot === slot);
  return xs.length ? xs.reduce((a, b) => (b.priority > a.priority + 20 || (b.t_in >= a.t_in && b.priority >= a.priority - 20) ? b : a)) : null;
}

type OnAir = ReturnType<typeof useOnAir>;

/** What is on air right now, re-read five times a second against the match clock. */
function useOnAir(feed: Feed) {
  const [t, setT] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setT(feed.clock.current), 200);
    return () => window.clearInterval(id);
  }, [feed.clock]);
  const live = active(feed.cues, t);
  return {
    bug: feed.cues.find((c) => c.kind === "score_bug"),
    ur: live.filter((c) => c.slot === "upper_right").sort((a, b) => b.t_in - a.t_in).slice(0, 2),
    side: newest(live, "side_panel"),
    lower: newest(live, "lower_third"),
    ticker: newest(live, "ticker"),
    follow: live.filter((c) => c.slot === "follow"),
  };
}

interface OverlayProps {
  feed: Feed; receipts: boolean; rtl: boolean; showMomentum?: boolean;
  /** false on narrow screens: the cards render below the pitch (OverlayCards) instead of over it */
  cards?: boolean;
  /** producer receipts (agent, model, latency, evidence ids) instead of the fan's "checked" chip */
  detail?: boolean;
}

export const Overlay = forwardRef<HTMLDivElement, OverlayProps>(
  function Overlay({ feed, receipts, rtl, showMomentum = true, cards = true, detail = false }, ref) {
    const air = useOnAir(feed);
    return (
      <div className="overlay" ref={ref}>
        <div className="slot-ul">
          {feed.match && <ScoreBug match={feed.match} snap={feed.snap} cue={air.bug} />}
          {showMomentum && feed.match && feed.snap && <WinProb match={feed.match} snap={feed.snap} locale={feed.language} />}
        </div>
        {cards && <CueSlots air={air} match={feed.match} receipts={receipts} rtl={rtl} detail={detail} />}
        {air.follow.map((c) => (
          <div className="follow" data-follow={c.follow ?? ""} key={c.id}>
            {c.kind === "speed_flash" ? (
              <div className="speedflash mono">{Number(c.payload.facts?.speed_kmh ?? c.payload.speed_kmh ?? 0).toFixed(1)} km/h</div>
            ) : (
              <div className="ptag" style={accent(c)}>
                <span className="num">{c.payload.number}</span>
                {c.payload.short_name ?? c.title}
                {c.payload.show_speed && <span className="spd">{Math.round(c.payload.speed_kmh)} km/h</span>}
                {c.payload.show_distance && !c.payload.show_speed && <span className="spd">{Number(c.payload.distance_km).toFixed(1)} km</span>}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  },
);

interface SlotProps { air: OnAir; match: MatchInfo | null; receipts: boolean; rtl: boolean; detail: boolean }

/** The broadcast cards in their on-pitch slots. */
function CueSlots({ air, match, receipts, rtl, detail }: SlotProps) {
  const dir = rtl ? "rtl" : "ltr";
  return (
    <>
      <div className="slot-ur">
        {air.ur.map((c) => <Card key={c.id} cue={c} receipts={receipts} detail={detail} dir={dir} match={match} />)}
      </div>
      {air.side && <div className="slot-side"><Card cue={air.side} receipts={receipts} detail={detail} dir={dir} match={match} /></div>}
      {air.lower && <div className="slot-lower"><Lower cue={air.lower} receipts={receipts} detail={detail} dir={dir} match={match} /></div>}
      {air.ticker && <div className="slot-ticker" key={air.ticker.id}><Ticker cue={air.ticker} rtl={rtl} /></div>}
    </>
  );
}

/** Phones: the same cards stacked below a compact pitch, at a size people can read. */
export function OverlayCards({ feed, receipts, rtl }: { feed: Feed; receipts: boolean; rtl: boolean }) {
  const air = useOnAir(feed);
  const dir = rtl ? "rtl" : "ltr";
  return (
    <div className="stage-cards" aria-live="polite">
      {air.lower && <Lower cue={air.lower} receipts={receipts} detail={false} dir={dir} match={feed.match} />}
      {air.ur.map((c) => <Card key={c.id} cue={c} receipts={receipts} detail={false} dir={dir} match={feed.match} />)}
      {air.side && <Card cue={air.side} receipts={receipts} detail={false} dir={dir} match={feed.match} />}
      {air.ticker && <Ticker cue={air.ticker} rtl={rtl} />}
    </div>
  );
}

function Ticker({ cue, rtl }: { cue: Cue; rtl: boolean }) {
  return (
    <div className="ticker" dir={rtl ? "rtl" : "ltr"} style={accent(cue)}>
      <b>{cue.payload.moment_kind ? label(cue.locale, cue.payload.moment_kind) : cue.kind}</b>
      <span className={rtl ? "rtl" : ""}>{cue.body || cue.title}</span>
    </div>
  );
}

function accent(c: Cue): React.CSSProperties {
  const col = c.payload?.colors?.primary;
  return col ? ({ "--accent": col } as React.CSSProperties) : {};
}

function ScoreBug({ match, snap, cue }: { match: MatchInfo; snap: Snapshot | null; cue?: Cue }) {
  const score = snap?.score ?? cue?.payload.score ?? {};
  return (
    <div className="scorebug" aria-label="Score">
      <div className="team"><span className="chip" style={{ background: match.home.primary }} />{match.home.abbr}</div>
      <div className="score">{score[match.home.id] ?? 0}–{score[match.away.id] ?? 0}</div>
      <div className="team">{match.away.abbr}<span className="chip" style={{ background: match.away.primary }} /></div>
      <div className="clock">{snap?.clock ?? "0'"}</div>
    </div>
  );
}

function WinProb({ match, snap, locale }: { match: MatchInfo; snap: Snapshot; locale?: string }) {
  const wp = snap.win_probability;
  return (
    <div className="momentum g-glass">
      <div className="lbl"><span>{label(locale, "win_probability")}</span><span className="mono">{Math.round(wp.home * 100)} · {Math.round(wp.draw * 100)} · {Math.round(wp.away * 100)}</span></div>
      <div className="wpbar">
        <div style={{ flexGrow: wp.home, background: match.home.primary }} />
        <div style={{ flexGrow: wp.draw, background: "#ddcbe0" }} />
        <div style={{ flexGrow: wp.away, background: match.away.primary }} />
      </div>
    </div>
  );
}

/** Fans see whether the figures were checked; producers (detail) also see who wrote it, on which model, how fast. */
function Receipt({ cue, detail }: { cue: Cue; detail: boolean }) {
  const p = cue.provenance;
  const v = cue.payload.verdict;
  const l = cue.locale;
  const checked = v?.numbers_checked ? label(l, "checked_n", { a: v.numbers_supported, b: v.numbers_checked })
    : p.agent === "Producer" && !cue.moment_id ? label(l, "from_data") : label(l, "checked");
  return (
    <div className="receipt">
      {p.verified ? <span className="ok">✓ {checked}</span> : <span className="fb">{label(l, "not_checked")}</span>}
      {p.fallback && <span className="fb">{label(l, "template")}</span>}
      {detail && (
        <>
          <span>{p.agent}</span>
          <span>{p.model}</span>
          {p.attempts > 1 && <span className="fb">{p.attempts} drafts</span>}
          {p.latency_ms > 0 && <span>{Math.round(p.latency_ms)} ms</span>}
          {cue.evidence.length > 0 && <span>{cue.evidence.slice(0, 2).join(" ")}</span>}
        </>
      )}
    </div>
  );
}

interface CardProps { cue: Cue; receipts: boolean; detail: boolean; dir: string; match: MatchInfo | null }

/** One cue exactly as a fan gets it on air, off the pitch (the Explore page shows three side by side). */
export function CueView({ cue, match, rtl }: { cue: Cue; match: MatchInfo | null; rtl: boolean }) {
  const dir = rtl ? "rtl" : "ltr";
  return cue.slot === "lower_third"
    ? <Lower cue={cue} receipts detail={false} dir={dir} match={match} />
    : <Card cue={cue} receipts detail={false} dir={dir} match={match} />;
}

function Lower({ cue, receipts, detail, dir, match }: CardProps) {
  const team = cue.payload.team === match?.home.id ? match?.home : cue.payload.team === match?.away.id ? match?.away : null;
  const rtl = dir === "rtl";
  return (
    <div className="lower" key={cue.id} style={accent(cue)} dir={dir}>
      <div className="tag">{team?.abbr ?? label(cue.locale, "live")}</div>
      <div className={`content ${rtl ? "rtl" : ""}`}>
        <div className="caption">{cue.title}</div>
        {cue.body && <div className="line">{cue.body}</div>}
        {cue.payload.explainer && <div className="why">{cue.payload.explainer}</div>}
        {receipts && <Receipt cue={cue} detail={detail} />}
      </div>
    </div>
  );
}

function Card({ cue, receipts, detail, dir, match }: CardProps) {
  const p = cue.payload;
  const f = p.facts ?? {};
  const rtl = dir === "rtl";
  const l = cue.locale;
  const kicker = p.moment_kind ? label(l, p.moment_kind) : cue.kind === "pass_card" ? label(l, "master_pass") : cue.kind.replace("_", " ");
  if (cue.kind === "shot_card" && !p.moment_kind) {
    return (
      <div className="gcard g-glass" style={accent(cue)}>
        <div className="kicker">{label(l, "shot")} · {label(l, String(p.outcome))}</div>
        <div className="title">{cue.title}</div>
        <div className="metrics">
          <div className="metric"><b>{Number(p.xg).toFixed(2)}</b><span>xG</span></div>
          <div className="metric"><b>{Math.round(p.shot_speed_kmh)}</b><span>km/h</span></div>
          <div className="metric"><b>{Math.round(p.distance_m)}</b><span>m</span></div>
        </div>
        <div className="meter" title="chance quality"><i style={{ width: `${Math.min(100, p.xg * 100)}%` }} /></div>
      </div>
    );
  }
  if (cue.kind === "player_focus") {
    const v = p.player;
    return (
      <div className="gcard g-glass">
        <div className="kicker">{label(l, "player_cam")}</div>
        <div className="title">{v.name}</div>
        <div className="metrics">
          <div className="metric"><b>{v.rating}</b><span>{label(l, "rating")}</span></div>
          <div className="metric"><b>{v.distance_km}</b><span>km</span></div>
          <div className="metric"><b>{v.top_speed_kmh}</b><span>{label(l, "top_kmh")}</span></div>
          <div className="metric"><b>{v.passes}</b><span>{label(l, "passes")}</span></div>
          <div className="metric"><b>{v.pass_accuracy}%</b><span>{label(l, "accuracy")}</span></div>
          <div className="metric"><b>{v.avg_pass_difficulty}</b><span>{label(l, "avg_difficulty")}</span></div>
        </div>
      </div>
    );
  }
  return (
    <div className="gcard g-glass" style={accent(cue)} dir={dir} key={cue.id}>
      <div className="kicker">{kicker}</div>
      <div className={`title ${rtl ? "rtl" : ""}`}>{cue.title}</div>
      {cue.body && <div className={`body ${rtl ? "rtl" : ""}`}>{cue.body}</div>}
      {cue.kind === "pass_card" && f.passer_accuracy !== undefined && !p.moment_kind && (
        <div className="body mono" style={{ fontSize: "0.78em" }}>{Math.round(f.ball_speed_kmh)} km/h · {label(l, "passer_acc", { n: f.passer_accuracy })}</div>
      )}
      {cue.kind === "pass_card" && (
        <>
          <div className="metrics">
            <div className="metric"><b>{Math.round(f.difficulty)}</b><span>{label(l, "difficulty")}</span></div>
            <div className="metric"><b>{Math.round(f.length_m)}</b><span>{label(l, "metres")}</span></div>
            <div className="metric"><b>{f.opponents_bypassed}</b><span>{label(l, "bypassed")}</span></div>
          </div>
          <div className="meter"><i style={{ width: `${f.difficulty}%` }} /></div>
        </>
      )}
      {(p.moment_kind === "big_chance" || p.moment_kind === "thunderbolt") && (
        <div className="metrics">
          <div className="metric"><b>{Number(f.xg ?? 0).toFixed(2)}</b><span>xG</span></div>
          <div className="metric"><b>{Math.round(f.shot_speed_kmh ?? 0)}</b><span>km/h</span></div>
          <div className="metric"><b>{Math.round(f.distance_m ?? 0)}</b><span>m</span></div>
        </div>
      )}
      {p.moment_kind === "press_shift" && <PressViz f={f} locale={l} />}
      {p.moment_kind === "control_chaos" && <FactorViz factors={f.factors ?? []} />}
      {p.moment_kind === "momentum_swing" && <Spark series={(f.series ?? []).map((s: any) => s.value)} color={match?.home.primary} />}
      {p.explainer && <div className={`body ${rtl ? "rtl" : ""}`} style={{ opacity: 0.85 }}>{p.explainer}</div>}
      {receipts && <Receipt cue={cue} detail={detail} />}
    </div>
  );
}

function PressViz({ f, locale }: { f: any; locale: string }) {
  const nb = f.players_near_ball_before ?? 0;
  const na = f.players_near_ball_after ?? 0;
  const lb = f.line_height_before_m ?? 0;
  const la = f.line_height_after_m ?? 0;
  const maxN = Math.max(nb, na, 0.1);
  const maxL = Math.max(lb, la, 1);
  return (
    <div className="beforeafter">
      <span className="muted">{label(locale, "near_ball")}</span>
      <div style={{ display: "grid", gap: "0.2em" }}>
        <div className="b" style={{ width: `${(nb / maxN) * 100}%` }} />
        <div className="a" style={{ width: `${(na / maxN) * 100}%` }} />
      </div>
      <span className="mono">{nb.toFixed(1)}→{na.toFixed(1)}</span>
      <span className="muted">{label(locale, "line_m")}</span>
      <div style={{ display: "grid", gap: "0.2em" }}>
        <div className="b" style={{ width: `${(lb / maxL) * 100}%` }} />
        <div className="a" style={{ width: `${(la / maxL) * 100}%` }} />
      </div>
      <span className="mono">{Math.round(lb)}→{Math.round(la)}</span>
    </div>
  );
}

function FactorViz({ factors }: { factors: any[] }) {
  return (
    <div>
      {factors.slice(0, 3).map((x) => {
        const z = Math.max(-3, Math.min(3, x.z));
        const left = z >= 0 ? 50 : 50 + (z / 3) * 50;
        const width = Math.abs(z / 3) * 50;
        return (
          <div className="factor" key={x.label}>
            <span>{x.label}</span><span className="mono">{x.detail}</span>
            <div className="bar"><i style={{ left: `${left}%`, width: `${width}%`, background: x.pushes === "control" ? "var(--ok)" : "var(--warn)" }} /></div>
          </div>
        );
      })}
    </div>
  );
}

export function Spark({ series, color, height = 34 }: { series: number[]; color?: string; height?: number }) {
  if (series.length < 2) return null;
  const w = 220;
  const pts = series.map((v, i) => `${(i / (series.length - 1)) * w},${height / 2 - (v / 100) * (height / 2 - 2)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${height}`} style={{ width: "100%", height: "2.4em", marginTop: "0.4em" }} aria-hidden>
      <line x1="0" x2={w} y1={height / 2} y2={height / 2} stroke="rgba(31,0,36,0.35)" strokeDasharray="4 3" />
      <polyline points={pts} fill="none" stroke={color ?? "#1f0024"} strokeWidth="3" strokeLinejoin="miter" />
    </svg>
  );
}
