import type { MatchInfo, Profile } from "../lib/types";
import { FOCUS, LANGS, MODES } from "../lib/types";

export const PRESETS: { label: string; profile: Partial<Profile> }[] = [
  // the three fans of the demo story: one match, three broadcasts
  { label: "Tom · analyst · EN", profile: { mode: "analyst", language: "en", favorite_team: null, favorite_player: null, focus_metric: "pressing" } },
  { label: "Amira · Port Calder fan · عربي", profile: { mode: "casual", language: "ar", favorite_team: "CAL", favorite_player: null, focus_metric: "none" } },
  { label: "Lucía · first match · ES", profile: { mode: "new_fan", language: "es", favorite_team: "NOR", favorite_player: null, focus_metric: "xg" } },
  { label: "Player cam · Arata", profile: { mode: "player_cam", language: "en", favorite_team: "NOR", favorite_player: "NOR-10", focus_metric: "pass_difficulty" } },
];

const isPreset = (p: Profile, preset: Partial<Profile>) =>
  (Object.keys(preset) as (keyof Profile)[]).every((k) => p[k] === preset[k]);

/** One tap to become one of the story's fans. */
export function PersonaChips({ profile, setProfile, className = "" }: {
  profile: Profile; setProfile: (p: Profile) => void; className?: string;
}) {
  return (
    <div className={`chips ${className}`} role="group" aria-label="Watch as">
      {PRESETS.map((p) => (
        <button key={p.label} aria-pressed={isPreset(profile, p.profile)} onClick={() => setProfile({ ...profile, ...p.profile })}>
          {p.label}
        </button>
      ))}
    </div>
  );
}

export function FanStudio({ profile, setProfile, match, compact = false }: {
  profile: Profile; setProfile: (p: Profile) => void; match: MatchInfo | null; compact?: boolean;
}) {
  const set = (patch: Partial<Profile>) => setProfile({ ...profile, ...patch });
  const players = match ? [match.home, match.away] : [];
  return (
    <div className="stack">
      {!compact && <PersonaChips profile={profile} setProfile={setProfile} />}
      <label className="field">Viewing mode
        <div className="seg">
          {MODES.map((m) => <button key={m.id} className={profile.mode === m.id ? "on" : ""} aria-pressed={profile.mode === m.id} onClick={() => set({ mode: m.id })}>{m.label}</button>)}
        </div>
      </label>
      <label className="field">Language
        <div className="seg">
          {LANGS.map((l) => <button key={l.id} className={profile.language === l.id ? "on" : ""} aria-pressed={profile.language === l.id} onClick={() => set({ language: l.id })}>{l.label}</button>)}
        </div>
      </label>
      <div className="row" style={{ alignItems: "end" }}>
        <label className="field" style={{ flex: 1, minWidth: 130 }}>Favourite club
          <select value={profile.favorite_team ?? ""} onChange={(e) => set({ favorite_team: e.target.value || null })}>
            <option value="">Neutral</option>
            {players.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <label className="field" style={{ flex: 1, minWidth: 150 }}>Favourite player
          <select value={profile.favorite_player ?? ""} onChange={(e) => set({ favorite_player: e.target.value || null })}>
            <option value="">None</option>
            {players.map((t) => (
              <optgroup key={t.id} label={t.name}>
                {t.players.map((p) => <option key={p.id} value={p.id}>{p.number} · {p.name}</option>)}
              </optgroup>
            ))}
          </select>
        </label>
      </div>
      {!compact && (
        <label className="field">Focus metric
          <div className="seg">
            {FOCUS.map((f) => <button key={f.id} className={profile.focus_metric === f.id ? "on" : ""} aria-pressed={profile.focus_metric === f.id} onClick={() => set({ focus_metric: f.id })}>{f.label}</button>)}
          </div>
        </label>
      )}
    </div>
  );
}
