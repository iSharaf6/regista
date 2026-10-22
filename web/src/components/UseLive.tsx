import { useState } from "react";
import { LANGS, MODES, type MatchInfo, type Profile, profileQuery } from "../lib/types";
import { PersonaChips, PRESETS } from "./FanStudio";

/** Who the exports are for, in words: "Amira · casual · عربي · Port Calder". */
function exportSummary(p: Profile, match: MatchInfo | null): string {
  const preset = PRESETS.find((x) => (Object.keys(x.profile) as (keyof Profile)[]).every((k) => p[k] === x.profile[k]));
  const team = p.favorite_team ? [match?.home, match?.away].find((t) => t?.id === p.favorite_team)?.name ?? p.favorite_team : "neutral";
  return [preset ? preset.label.split(" · ")[0] : "Custom viewer", MODES.find((m) => m.id === p.mode)?.label.toLowerCase() ?? p.mode,
          LANGS.find((l) => l.id === p.language)?.label ?? p.language, team].join(" · ");
}

/** Copy-ready endpoints for real productions, built for the viewer profile chosen in Fan Studio. */
export function UseLive({ profile, setProfile, match }: { profile: Profile; setProfile: (p: Profile) => void; match: MatchInfo | null }) {
  const origin = typeof location !== "undefined" ? location.origin : "";
  const q = profileQuery(profile);
  const items: { label: string; hint: string; url: string; open?: boolean }[] = [
    { label: "Overlay", hint: "OBS / vMix browser source, transparent", url: `${origin}/#/overlay?${q}`, open: true },
    { label: "On-air JSON", hint: "vMix Data Sources, CasparCG, any poller", url: `${origin}/api/onair?${q}`, open: true },
    { label: "MCP", hint: "GitHub Copilot or any MCP client", url: `${origin}/mcp` },
    { label: "Live feed", hint: "push your own tracking and events", url: `${origin}/docs#/live%20feed`, open: true },
  ];
  return (
    <div className="card">
      <header><h3>Use it live</h3></header>
      <div className="body stack">
        <div className="muted" style={{ fontSize: 13.5 }}>
          Plug Regista into a real production. These links follow your Fan Studio profile; pick another viewer here.
        </div>
        <PersonaChips profile={profile} setProfile={setProfile} />
        <div className="export-for" role="status"><b>Exporting:</b> <span dir="auto">{exportSummary(profile, match)}</span></div>
        {items.map((it) => <Endpoint key={it.label} {...it} />)}
        <a href={`${origin}/docs`} target="_blank" rel="noreferrer">Full REST reference ↗</a>
      </div>
    </div>
  );
}

function Endpoint({ label, hint, url, open }: { label: string; hint: string; url: string; open?: boolean }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch { /* clipboard blocked: the link stays selectable */ }
  };
  return (
    <div className="endpoint">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span><span className="kind">{label}</span> <span className="muted" style={{ fontSize: 12.5 }}>{hint}</span></span>
        <span className="row" style={{ gap: 6 }}>
          {open && <a className="btn small" href={url} target="_blank" rel="noreferrer">Open</a>}
          <button className="btn small yellow" onClick={copy} aria-label={`Copy ${label} link`}>{copied ? "Copied" : "Copy"}</button>
        </span>
      </div>
      <code className="url">{url}</code>
    </div>
  );
}
