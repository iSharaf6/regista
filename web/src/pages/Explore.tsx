import { useEffect, useState } from "react";
import { FactTable, HowChecked } from "../components/Moments";
import { CueView } from "../components/Overlay";
import type { Cue, MatchInfo, Moment, Story } from "../lib/types";

interface ExploreFan {
  name: string; label: string; aired: boolean; cue: Cue | null;
  profile: { mode: string; language: string; favorite_team: string | null };
}
interface ExploreMoment { id: string; kind: string; clock: string; headline: string }
interface ExploreOut {
  curated: boolean; note: string; match: MatchInfo; moment: Moment; fans: ExploreFan[]; story: Partial<Story>;
  evidence: string[]; moments: ExploreMoment[];
}
type State = "loading" | "ok" | "busy" | "missing" | "error";

const KIND: Record<string, string> = {
  goal: "Goal", red_card: "Red card", master_pass: "Pass of quality", press_shift: "Tactical shift", momentum_swing: "Momentum swing",
};
const pick = (id: string) => { location.hash = `#/explore?moment=${encodeURIComponent(id)}`; };

/** Explore one moment: a curated, private replay of one demo-match moment as Tom, Amira and Lucía each get it, with the
 *  facts and how every figure was checked. Nobody should have to sit through the live 90 minutes to see a goal. */
export function Explore({ query }: { query: URLSearchParams }) {
  const id = query.get("moment");
  const [data, setData] = useState<ExploreOut | null>(null);
  const [state, setState] = useState<State>("loading");
  useEffect(() => {
    let live = true;
    setState("loading");
    fetch(`/api/explore${id ? `?moment=${encodeURIComponent(id)}` : ""}`, { cache: "no-cache" })
      .then(async (r) => {
        const next: State = r.status === 429 ? "busy" : r.status === 404 ? "missing" : r.ok ? "ok" : "error";
        const body = next === "ok" ? await r.json() : null;
        if (!live) return;
        if (body) setData(body);
        setState(next);
      })
      .catch(() => { if (live) setState("error"); });
    return () => { live = false; };
  }, [id]);

  const moments = data?.moments ?? [];
  const current = id ?? data?.moment.id;
  const pending = moments.find((m) => m.id === id);
  return (
    <div className="page">
      <div className="page-head">
        <span className="replay-badge">Curated replay</span>
        <h2 className="title-px">Explore <span className="y">one moment</span></h2>
        <p>
          Pick a moment from the demo match and see, in seconds, what three different fans get on screen, the facts behind it and how
          every figure was checked. It is replayed privately through the same agents: the live broadcast is unaffected.
        </p>
      </div>

      {moments.length > 0 && (
        <div className="card explore-pick">
          <label className="field">Moment
            <select value={current ?? ""} onChange={(e) => pick(e.target.value)}>
              {moments.map((m) => <option key={m.id} value={m.id}>{m.clock} · {m.headline}</option>)}
            </select>
          </label>
          <div className="chips" role="group" aria-label="Jump to a big moment">
            {moments.filter((m) => m.kind === "goal" || m.kind === "red_card").map((m) => (
              <button key={m.id} aria-pressed={m.id === current} className={m.id === current ? "on" : ""} onClick={() => pick(m.id)}>
                {m.clock} {KIND[m.kind]}
              </button>
            ))}
          </div>
        </div>
      )}

      {state === "loading" && (
        <div className="card replaying" role="status">
          <span className="replay-badge">Replaying{pending ? ` to ${pending.clock}` : ""}</span>
          <div>
            <b>Running the match up to this moment, then the Analyst, Narrator, Localizers and Verifier.</b>
            <div className="muted">The first visit to a moment takes about 15 seconds on the live model; after that it loads instantly.</div>
          </div>
        </div>
      )}
      {state === "busy" && <div className="empty">Lots of new replays from your network just now. Try again in a minute; moments already replayed still load instantly.</div>}
      {state === "missing" && <div className="empty">That moment isn't in the demo match. Pick one from the list.</div>}
      {state === "error" && <div className="empty">Couldn't reach the replay. Check the connection and reload.</div>}

      {state === "ok" && data && <Replay data={data} />}
    </div>
  );
}

function Replay({ data }: { data: ExploreOut }) {
  const m = data.moment;
  const story = data.story;
  const v = story.verdict;
  const why = (m.why ?? []).filter((w: any) => w.detail || (w.value !== null && w.value !== undefined && typeof w.value !== "object"));
  return (
    <>
      <div className="card explore-moment">
        <div className="body">
          <div className="row">
            <span className={`kind ${m.kind === "goal" ? "goal" : ""}`}>{KIND[m.kind] ?? m.kind} · {m.clock}</span>
            {v?.numbers_checked ? <span className="verified">✓ checked · {v.numbers_supported}/{v.numbers_checked} figures · {v.names_checked} names</span> : null}
            <a className="raw" href={`/api/explore?moment=${encodeURIComponent(m.id)}`} target="_blank" rel="noreferrer">raw JSON ↗</a>
          </div>
          <h3 className="cond">{m.headline}</h3>
          {story.insight?.tactical_read && <div className="muted">{story.insight.tactical_read}</div>}
        </div>
      </div>

      <div className="section-title on-sky">Same second, three broadcasts</div>
      <div className="explore-fans">
        {data.fans.map((f) => <FanView key={f.name} fan={f} match={data.match} />)}
      </div>

      <div className="ops-grid">
        <section className="card">
          <header><h3>The facts</h3><span className="muted" style={{ fontSize: 12 }}>observed in the feed, or a model estimate</span></header>
          <div className="body">
            <FactTable facts={m.facts ?? {}} kinds={m.fact_kinds ?? {}} match={data.match} />
            {why.length > 0 && (
              <>
                <div className="section-title">Why it matters</div>
                <ul className="why-list">{why.map((w: any) => <li key={w.label}><b>{w.label}</b> · {w.detail || `${w.value}${w.unit ?? ""}`}</li>)}</ul>
              </>
            )}
          </div>
        </section>
        <section className="card">
          <header><h3>How it was checked</h3></header>
          <div className="body">
            {story.insight?.claim && (
              <div className="card" style={{ padding: 10, marginBottom: 10 }}>
                <div className="section-title" style={{ margin: "0 0 4px" }}>Analyst's read (AI)</div>
                <b>{story.insight.claim}</b>
                <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{(story.insight.why ?? []).map((w: string) => <li key={w}>{w}</li>)}</ul>
              </div>
            )}
            <HowChecked story={story} />
          </div>
        </section>
      </div>
    </>
  );
}

function FanView({ fan, match }: { fan: ExploreFan; match: MatchInfo }) {
  const cue = fan.cue;
  const rel = cue?.payload?.relevance;
  const reasons: string[] = (rel?.reasons ?? []).filter((r: string) => !r.startsWith("base ")).map((r: string) => r.replace("_", " "));
  const side = cue?.payload?.partisan;
  return (
    <div className="explore-fan">
      <div className="fan-chip"><b>{fan.name}</b><span>{fan.label}</span></div>
      <div className={`stage-cards ${fan.aired ? "" : "held"}`}>
        {cue ? <CueView cue={cue} match={match} rtl={fan.profile.language === "ar"} /> : <div className="empty">Nothing for {fan.name} here.</div>}
      </div>
      <div className="fan-why">
        <span className={fan.aired ? "on" : "off"}>{fan.aired ? "On air" : "Held back"}</span>
        {side && <span>{side === "for" ? `${fan.name}'s club` : `against ${fan.name}'s club`}</span>}
        {rel && <span>relevance {rel.score}{reasons.length ? `: ${reasons.join(", ")}` : ""}</span>}
      </div>
    </div>
  );
}
