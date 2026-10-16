import type { MatchInfo, Profile } from "../lib/types";
import { FOCUS, LANGS, MODES } from "../lib/types";

export const PRESETS: { label: string; profile: Partial<Profile> }[] = [
  { label: "Analyst · EN", profile: { mode: "analyst", language: "en", favorite_team: null, favorite_player: null, focus_metric: "pressing" } },
  { label: "Port Calder fan · عربي", profile: { mode: "casual", language: "ar", favorite_team: "CAL", favorite_player: null, focus_metric: "none" } },
  { label: "New to football · ES", profile: { mode: "new_fan", language: "es", favorite_team: "NOR", favorite_player: null, focus_metric: "xg" } },
  { label: "Player cam · Arata", profile: { mode: "player_cam", language: "en", favorite_team: "NOR", favorite_player: "NOR-10", focus_metric: "pass_difficulty" } },
];

export function FanStudio({ profile, setProfile, match, compact = false }: {
  profile: Profile; setProfile: (p: Profile) => void; match: MatchInfo | null; compact?: boolean;
}) {
  const set = (patch: Partial<Profile>) => setProfile({ ...profile, ...patch });
  const players = match ? [match.home, match.away] : [];
  return (
    <div className="stack">
      {!compact && (
        <div className="chips" aria-label="Presets">
          {PRESETS.map((p) => (
            <button key={p.label} onClick={() => set(p.profile)}>{p.label}</button>
          ))}
        </div>
      )}
      <label className="field">Viewing mode
        <div className="seg">
          {MODES.map((m) => <button key={m.id} className={profile.mode === m.id ? "on" : ""} onClick={() => set({ mode: m.id })}>{m.label}</button>)}
        </div>
      </label>
      <label className="field">Language
        <div className="seg">
          {LANGS.map((l) => <button key={l.id} className={profile.language === l.id ? "on" : ""} onClick={() => set({ language: l.id })}>{l.label}</button>)}
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
            {FOCUS.map((f) => <button key={f.id} className={profile.focus_metric === f.id ? "on" : ""} onClick={() => set({ focus_metric: f.id })}>{f.label}</button>)}
          </div>
        </label>
      )}
    </div>
  );
}
