import { useEffect, useState } from "react";
import { FactTable, HowChecked, isOfflineStory, TRUST } from "../components/Moments";
import { CueView } from "../components/Overlay";
import type { Cue, MatchInfo, Moment, Story } from "../lib/types";

interface ExploreFan {
  name: string; label: string; aired: boolean; cue: Cue | null;
  profile: { mode: string; language: string; favorite_team: string | null };
}
interface ExploreMoment { id: string; kind: string; clock: string; headline: string }
interface ExploreOut {
  curated: boolean; note: string; match: MatchInfo; moment: Moment; fans: ExploreFan[]; story: Partial<Story> & { drafts?: any };
  evidence: string[]; moments: ExploreMoment[];
  drill?: { lang: string; drafts: number; name: string; note: string } | null; drills?: string[];
}
type State = "loading" | "ok" | "busy" | "missing" | "error";

const KIND: Record<string, string> = {
  goal: "Goal", red_card: "Red card", master_pass: "Pass of quality", press_shift: "Tactical shift", momentum_swing: "Momentum swing",
};
// labelled recovery drills: a wrong goal count planted in Arabic, caught by the Verifier, fixed or replaced by the template
const DRILLS: { id: string | null; label: string }[] = [
  { id: null, label: "Normal run" },
  { id: "ar", label: "Recovery drill: Arabic fails once" },
  { id: "ar2", label: "Recovery drill: Arabic exhausts its drafts" },
];

/** Move to another moment, drill or view; everything lives in the link so a view can be shared. */
function go(next: { moment?: string | null; drill?: string | null; view?: string | null }) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(next)) if (v) q.set(k, v);
  location.hash = `#/explore?${q}`;
}

/** Explore one moment: a curated, private replay of one demo-match moment as Tom, Amira and Lucía each get it, with the
 *  facts and how every figure was checked. Nobody should have to sit through the live 90 minutes to see a goal. */
export function Explore({ query }: { query: URLSearchParams }) {
  const id = query.get("moment");
  const drill = query.get("drill");
  const view = query.get("view") === "same" ? "same" : null;
  const [data, setData] = useState<ExploreOut | null>(null);
  const [state, setState] = useState<State>("loading");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    setState("loading");
    const q = new URLSearchParams();
    if (id) q.set("moment", id);
    if (drill) q.set("drill", drill);
    fetch(`/api/explore${q.toString() ? `?${q}` : ""}`, { cache: "no-cache" })
      .then(async (r) => {
        const next: State = r.status === 429 ? "busy" : r.status === 404 ? "missing" : r.ok ? "ok" : "error";
        const body = next === "ok" ? await r.json() : null;
        if (!live) return;
        if (body) setData(body);
        setState(next);
      })
      .catch(() => { if (live) setState("error"); });
    return () => { live = false; };
  }, [id, drill, attempt]);
  const retry = <button className="btn small" onClick={() => setAttempt((a) => a + 1)}>Try again</button>;

  const moments = data?.moments ?? [];
  const current = id && id !== "highlight" ? id : data?.moment.id;
  const pending = moments.find((m) => m.id === id);
  const pick = (moment: string) => go({ moment, view }); // a drill belongs to its moment: a new moment starts clean
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
          <div className="chips" role="group" aria-label="Who to compare">
            <button aria-pressed={!view} className={!view ? "on" : ""} onClick={() => go({ moment: current, drill, view: null })}>Three fans</button>
            <button aria-pressed={view === "same"} className={view === "same" ? "on" : ""} onClick={() => go({ moment: current, drill, view: "same" })}>
              Same language: Tom vs Sam
            </button>
          </div>
          {(data?.drills ?? []).includes("ar") && (
            <div className="chips" role="group" aria-label="Recovery drill">
              {DRILLS.map((d) => (
                <button key={d.label} aria-pressed={drill === d.id} className={drill === d.id ? "on" : ""}
                  onClick={() => go({ moment: current, drill: d.id, view })}>{d.label}</button>
              ))}
            </div>
          )}
        </div>
      )}

      {state === "loading" && (
        <div className="card replaying" role="status">
          <span className="replay-badge">Replaying{pending ? ` to ${pending.clock}` : ""}</span>
          <div>
            <b>Running the match up to this moment, then the Analyst, Narrator, Localizers and Verifier.</b>
            <div className="muted">A new moment takes 10 to 40 seconds on the live model (the first after a quiet spell is the slowest); after that it loads instantly.</div>
          </div>
        </div>
      )}
      {state === "busy" && <div className="empty stack">Lots of new replays from your network just now: try again in a minute. Moments already replayed still load instantly.<div>{retry}</div></div>}
      {state === "missing" && (
        <div className="empty stack">That moment isn't in the demo match.
          <div><a className="btn small" href="#/explore">Open the first goal instead</a></div>
        </div>
      )}
      {state === "error" && <div className="empty stack">Couldn't reach the replay. Check the connection, then try again.<div>{retry}</div></div>}

      {state === "ok" && data && <Replay data={data} same={view === "same"} />}
    </div>
  );
}

function Replay({ data, same }: { data: ExploreOut; same: boolean }) {
  const m = data.moment;
  const story = data.story;
  const v = story.verdict;
  const rawQuery = new URLSearchParams({ moment: m.id });
  if (data.drill) rawQuery.set("drill", data.drill.name);
  const drillLanguage = data.drill?.lang === "es" ? "Spanish" : "Arabic";
  const analystSource = isOfflineStory(story) ? "offline rehearsal"
    : story.models?.Analyst === "deterministic" ? "deterministic fallback" : "AI";
  const why = (m.why ?? []).filter((w: any) => w.detail || (w.value !== null && w.value !== undefined && typeof w.value !== "object"));
  const fans = data.fans.filter((f) => (same ? ["Tom", "Sam"].includes(f.name) : f.name !== "Sam"));
  return (
    <>
      <div className="card explore-moment">
        <div className="body">
          <div className="row">
            <span className={`kind ${m.kind === "goal" ? "goal" : ""}`}>{KIND[m.kind] ?? m.kind} · {m.clock}</span>
            {v?.numbers_checked ? (
              <span className="verified" title={`${TRUST} Figures in this moment's copy, across every language and audience, matched to the match data.`}>
                ✓ checked · {v.numbers_supported}/{v.numbers_checked} figures · {v.names_checked} names
              </span>
            ) : null}
            <a className="raw" href={`/api/explore?${rawQuery}`} target="_blank" rel="noreferrer">raw JSON ↗</a>
          </div>
          <h3 className="cond">{m.headline}</h3>
          {story.insight?.tactical_read && <div className="muted">{story.insight.tactical_read}</div>}
        </div>
      </div>

      {data.drill && (
        <div className="card drill-note" role="note">
          <span className="drill-badge">Drill · {data.drill.lang.toUpperCase()} · {data.drill.drafts === 1 ? "fails once" : "fails every draft"}</span>
          <p>{data.drill.note} {data.drill.drafts === 1
            ? `Watch the ${drillLanguage} drafts below: the Verifier rejects the planted figure and the second draft airs. Only ${drillLanguage} is rewritten because of the drill; any other rewrite you see below is a genuine rejection.`
            : `Watch the ${drillLanguage} drafts below: both carry the planted figure, both are rejected, and ${drillLanguage} airs its grounded template. Any other rewrite you see below is a genuine rejection.`}</p>
        </div>
      )}
      <div className="section-title on-sky">{same ? "Same language, two fans" : "Same second, three broadcasts"}</div>
      <p className="explore-note">{same
        ? "Both in English: what changes is the viewer, not the translation. Tom gets the analyst's read, Sam (at a first match) the plain-words version."
        : "Each fan's Director previewing this one moment: what it would show them and why. Live, it also weighs timing and what is already on screen."}</p>
      <div className={`explore-fans n${fans.length}`}>
        {fans.map((f) => <FanView key={f.name} fan={f} match={data.match} />)}
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
                <div className="section-title" style={{ margin: "0 0 4px" }}>Analyst's read ({analystSource})</div>
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
        <span className={fan.aired ? "on" : "off"}>{fan.aired ? "Would air" : "Held back"}</span>
        {side && <span>{side === "for" ? `${fan.name}'s club` : `against ${fan.name}'s club`}</span>}
        {rel && <span>relevance {rel.score}{reasons.length ? `: ${reasons.join(", ")}` : ""}</span>}
      </div>
    </div>
  );
}
