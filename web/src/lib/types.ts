// Mirrors backend/regista/schema/*.py (Graphics Cue Protocol v1 and the match feed).

export type Lang = "en" | "es" | "fr" | "ar" | "pt";
export type Mode = "casual" | "analyst" | "player_cam" | "new_fan";

export interface Profile {
  id: string;
  mode: Mode;
  language: Lang;
  favorite_team: string | null;
  favorite_player: string | null;
  focus_metric: string;
  spoiler_free: boolean;
  max_cues_per_minute: number;
}

export interface PlayerInfo {
  id: string; name: string; short_name: string; number: number; position: string;
  nationality: string; age: number; starting: boolean; top_speed_kmh: number;
}
export interface TeamInfo {
  id: string; name: string; short_name: string; abbr: string; primary: string; secondary: string;
  formation: string; style: string; players: PlayerInfo[];
}
export interface MatchInfo {
  match_id: string; competition: string; venue: string; kickoff_utc: string; referee: string; weather: string;
  seed: number; home: TeamInfo; away: TeamInfo; roster: string[];
}

export interface Frame { t: number; b: [number, number, number]; p: ([number, number] | null)[] }

export interface Provenance {
  agent: string; model: string; verified: boolean; fallback: boolean; latency_ms: number; attempts: number;
}

export interface Cue {
  v: 1; id: string; match_id: string; kind: string; slot: string; t_in: number; t_out: number; priority: number;
  locale: string; audience: string; title: string; body: string; payload: Record<string, any>;
  evidence: string[]; follow: string | null; moment_id: string | null; provenance: Provenance;
}

export interface TeamView { id: string; name: string; [k: string]: any }
export interface Snapshot {
  match_id: string; t: number; clock: string; period: number; status: string;
  score: Record<string, number>; teams: Record<string, TeamView>;
  win_probability: { home: number; draw: number; away: number }; momentum: number; ball_speed_kmh: number;
  timeline: any[]; top_players: any[];
}

export interface Moment {
  id: string; t: number; clock: string; kind: string; team: string | null; players: string[]; importance: number;
  headline: string; facts: Record<string, any>; why: any[]; evidence: string[]; lane: "fast" | "story";
  /** per fact: "observed" in the feed or "model estimate" (xG, win probability, difficulty...) */
  fact_kinds?: Record<string, string>;
  copy?: Record<string, { caption: string; line: string; explainer: string }>; story?: Story | null;
}

export interface Span {
  id: string; agent: string; status: string; ms: number; model: string; job: string; moment_id: string | null;
  attempt: number; detail: string; t_match: number; wall: number;
}

export interface Story {
  job: string; insight: any; verdict: any; attempts: number; fallback_langs: string[]; latency_ms: number;
  models: Record<string, string>; trace: Span[]; narration: Record<string, Record<string, { caption: string; line: string; explainer: string }>>;
}

export interface Control {
  playing: boolean; speed: number; clock: string; t: number; t_end: number;
  params: { home: string; away: string; seed: number; scenario: string };
  chaos: { fail_rate: number; latency_ms: number }; breaker: any; bus: string;
}

export const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "EN" }, { id: "es", label: "ES" }, { id: "fr", label: "FR" }, { id: "ar", label: "عربي" }, { id: "pt", label: "PT" },
];

export const MODES: { id: Mode; label: string }[] = [
  { id: "casual", label: "Casual" }, { id: "analyst", label: "Analyst" }, { id: "new_fan", label: "New fan" }, { id: "player_cam", label: "Player cam" },
];

export const FOCUS: { id: string; label: string }[] = [
  { id: "none", label: "None" }, { id: "pass_difficulty", label: "Pass difficulty" }, { id: "speed", label: "Speed" },
  { id: "xg", label: "xG" }, { id: "pressing", label: "Pressing" }, { id: "distance", label: "Distance" },
];

/** A viewer profile as URL parameters, shared by the overlay, the on-air feed and the phone link. */
export function profileQuery(p: Profile): URLSearchParams {
  const q = new URLSearchParams({ mode: p.mode, lang: p.language });
  if (p.favorite_team) q.set("team", p.favorite_team);
  if (p.favorite_player) q.set("player", p.favorite_player);
  if (p.focus_metric && p.focus_metric !== "none") q.set("focus", p.focus_metric);
  return q;
}

/** The profile fields carried by a link such as /#/?mode=new_fan&lang=es&team=NOR (null when it carries none).
 *  Every value is whitelisted: the server drops a whole profile with one invalid field, so a mangled link
 *  must lose only its bad keys, not reset the viewer to the defaults. */
export function profileFromQuery(q: URLSearchParams): Partial<Profile> | null {
  const out: Partial<Profile> = {};
  const mode = q.get("mode");
  const lang = q.get("lang");
  const team = q.get("team");
  const player = q.get("player");
  const focus = q.get("focus");
  if (mode && MODES.some((m) => m.id === mode)) out.mode = mode as Mode;
  if (lang && LANGS.some((l) => l.id === lang)) out.language = lang as Lang;
  if (team !== null && (team === "" || /^[A-Z]{2,4}$/.test(team))) out.favorite_team = team || null;
  if (player !== null && (player === "" || /^[A-Z]{2,4}-\d{1,3}$/.test(player))) out.favorite_player = player || null;
  if (focus && FOCUS.some((f) => f.id === focus)) out.focus_metric = focus;
  return Object.keys(out).length ? out : null;
}

export const defaultProfile = (over: Partial<Profile> = {}): Profile => ({
  id: Math.random().toString(36).slice(2, 8), mode: "casual", language: "en", favorite_team: null, favorite_player: null,
  focus_metric: "none", spoiler_free: false, max_cues_per_minute: 6, ...over,
});
