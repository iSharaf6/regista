import { useState } from "react";
import { FanStudio, PersonaChips } from "../components/FanStudio";
import { MomentsList, Receipts } from "../components/Moments";
import { Pundit } from "../components/Pundit";
import { SecondScreen } from "../components/SecondScreen";
import { Stage } from "../components/Stage";
import { Transport } from "../components/Transport";
import { useFeed } from "../lib/feed";
import type { Moment, Profile } from "../lib/types";
import type { Cam } from "../components/Pitch";

export function Broadcast({ profile, setProfile }: { profile: Profile; setProfile: (p: Profile) => void }) {
  const feed = useFeed(profile);
  const [cam, setCam] = useState<Cam>("broadcast");
  const [lens, setLens] = useState(false);
  const [receipts, setReceipts] = useState(true);
  const [open, setOpen] = useState<Moment | null>(null);
  const [tab, setTab] = useState<"studio" | "pundit">("studio");
  const m = feed.match;
  return (
    <div className="page grid-broadcast">
      <section>
        <a className="start-here" href="#/explore?moment=m055">
          <span className="replay-badge">Start here</span>
          <span><b>See one goal through three fans</b>
            <small>The 74th-minute winner as Tom, Amira and Lucía get it, with every draft and every check · about a minute</small></span>
          <span className="go" aria-hidden>→</span>
        </a>
        <Welcome />
        <Stage feed={feed} favorite={profile.favorite_player} cam={cam} lens={lens} receipts={receipts} rtl={profile.language === "ar"}
          label={`${profile.mode.replace("_", " ")} · ${profile.language.toUpperCase()}`} />
        <PersonaChips profile={profile} setProfile={setProfile} className="persona-bar" />
        <Transport feed={feed} />
        <div className="row" style={{ marginTop: 10, justifyContent: "space-between" }}>
          <div className="row">
            <div className="seg" aria-label="Camera">
              <button className={cam === "broadcast" ? "on" : ""} aria-pressed={cam === "broadcast"} onClick={() => setCam("broadcast")}>Broadcast cam</button>
              <button className={cam === "tactical" ? "on" : ""} aria-pressed={cam === "tactical"} onClick={() => setCam("tactical")}>Tactical cam</button>
            </div>
            <div className="seg">
              <button className={lens ? "on" : ""} aria-pressed={lens} onClick={() => setLens(!lens)} title="Defensive lines and the 8 m pressing radius">Tactical lens</button>
              <button className={receipts ? "on" : ""} aria-pressed={receipts} onClick={() => setReceipts(!receipts)} title="Show on air whether each graphic's figures were checked">Receipts</button>
            </div>
          </div>
          {m && (
            <span className="meta-line">
              <span>{m.competition}</span><span>{m.venue}</span><span>{m.weather}</span><span>Ref. {m.referee}</span>
            </span>
          )}
        </div>
        <div className="card" style={{ marginTop: 14 }}>
          <header><h3>Key moments</h3><span className="muted" style={{ fontSize: 12 }}>tap any moment for the evidence behind it</span></header>
          <div className="body"><MomentsList feed={feed} onOpen={setOpen} /></div>
        </div>
      </section>
      <aside className="stack" style={{ position: "sticky", top: 70 }}>
        <div className="card">
          <header>
            <div className="seg">
              <button className={tab === "studio" ? "on" : ""} aria-pressed={tab === "studio"} onClick={() => setTab("studio")}>Fan Studio</button>
              <button className={tab === "pundit" ? "on" : ""} aria-pressed={tab === "pundit"} onClick={() => setTab("pundit")}>Ask the Pundit</button>
            </div>
          </header>
          <div className="body">
            {/* both stay mounted, so the Pundit conversation survives a trip to Fan Studio */}
            <div hidden={tab !== "studio"}><FanStudio profile={profile} setProfile={setProfile} match={m} /></div>
            <div hidden={tab !== "pundit"}><Pundit feed={feed} lang={profile.language} /></div>
          </div>
        </div>
        <SecondScreen profile={profile} />
        <LiveNumbers feed={feed} />
      </aside>
      {open && <Receipts moment={open} feed={feed} onClose={() => setOpen(null)} lang={profile.language} />}
    </div>
  );
}

function LiveNumbers({ feed }: { feed: ReturnType<typeof useFeed> }) {
  const s = feed.snap;
  const m = feed.match;
  if (!s || !m) return null;
  const h = s.teams[m.home.id];
  const a = s.teams[m.away.id];
  const rows: [string, string, number, number][] = [
    ["xG", "xg", h.xg, a.xg], ["Shots", "shots", h.shots, a.shots], ["Possession %", "possession", h.possession, a.possession],
    ["Pass accuracy %", "pass_accuracy", h.pass_accuracy, a.pass_accuracy], ["Avg pass difficulty", "d", h.avg_pass_difficulty, a.avg_pass_difficulty],
    ["Opponents bypassed", "b", h.opponents_bypassed, a.opponents_bypassed], ["Pressures", "p", h.pressures, a.pressures],
    ["High regains", "r", h.high_regains, a.high_regains], ["Max shot speed", "s", h.max_shot_speed_kmh, a.max_shot_speed_kmh],
  ];
  return (
    <div className="card">
      <header><h3>Live numbers</h3></header>
      <div className="body">
        <div className="teams-head">
          <span style={{ background: m.home.primary }}>{m.home.abbr}</span>
          <span style={{ background: m.away.primary }}>{m.away.abbr}</span>
        </div>
        {rows.map(([label, k, x, y]) => {
          const tot = (Number(x) || 0) + (Number(y) || 0) || 1;
          return (
            <div key={k} className="stat-row">
              <div className="row">
                <span className="mono">{fmt(x)}</span><span className="muted">{label}</span><span className="mono">{fmt(y)}</span>
              </div>
              <div className="stat-bar">
                <div style={{ width: `${(100 * (Number(x) || 0)) / tot}%`, background: m.home.primary }} />
                <div style={{ width: `${(100 * (Number(y) || 0)) / tot}%`, background: m.away.primary, marginLeft: "auto" }} />
              </div>
            </div>
          );
        })}
        <div className="section-title">Top performers</div>
        {s.top_players.slice(0, 4).map((p: any) => (
          <div key={p.id} className="performer">
            <span>{p.name} <span className="muted">· {p.position}</span></span>
            <span className="mono">{p.rating.toFixed(1)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** First-visit guide: what Regista is and the three things to try. Dismissal is remembered per browser. */
function Welcome() {
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem("regista.welcome") !== "0"; } catch { return true; }
  });
  if (!open) return null;
  const close = () => {
    setOpen(false);
    try { localStorage.setItem("regista.welcome", "0"); } catch { /* storage unavailable */ }
  };
  return (
    <div className="welcome" role="note">
      <span className="badge">HOW IT WORKS</span>
      <ol>
        <li><b>1</b>Pick who you are in Fan Studio</li>
        <li><b>2</b>Watch the graphics re-cut for you</li>
        <li><b>3</b>Tap a key moment for its receipts</li>
        <li><b>4</b><a href="#/explore">No time? Jump straight to a goal</a></li>
      </ol>
      <button className="x" onClick={close} aria-label="Dismiss">✕</button>
    </div>
  );
}

function fmt(v: any) {
  return typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(v < 10 ? 2 : 1)) : String(v ?? "-");
}
