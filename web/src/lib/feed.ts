import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Playback } from "./playback";
import type { Control, Cue, Frame, MatchInfo, Moment, Profile, Snapshot, Span, Story } from "./types";

export interface Feed {
  connected: boolean;
  /** this viewer's language, for the fixed labels around the graphics */
  language: string;
  match: MatchInfo | null;
  snap: Snapshot | null;
  control: Control | null;
  llm: { provider: string; model: string; offline: boolean } | null;
  moments: Moment[];
  cues: Cue[];
  stories: Record<string, Story>;
  spans: Span[];
  ops: any;
  recaps: any[];
  frame: React.MutableRefObject<Frame | null>;
  /** recent frames, played back on a steady clock by the pitch */
  playback: Playback;
  clock: React.MutableRefObject<number>;
  lastSpanByAgent: Record<string, Span>;
  send: (msg: any) => void;
  control$: (action: string, value?: any) => void;
  ask: (question: string) => Promise<any>;
}

const PERSISTENT = new Set(["score_bug", "momentum"]);
// minimum wall-clock seconds on screen, so graphics stay readable at 10x-60x replay speed
export const MIN_WALL: Record<string, number> = {
  lower_third: 7, side_panel: 8, upper_right: 5, ticker: 5, follow: 2.5,
};
export function isLive(c: Cue, t: number, now = performance.now()) {
  if (c.t_in <= t + 0.6 && t <= c.t_out) return true;
  const wall = (c as any)._wall as number | undefined;
  return wall !== undefined && now - wall < (MIN_WALL[c.slot] ?? 3) * 1000;
}

export function wsUrl(profile: Profile, ops: boolean) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws?ops=${ops ? 1 : 0}&profile=${encodeURIComponent(JSON.stringify(profile))}`;
}

export function useFeed(profile: Profile, opts: { ops?: boolean } = {}): Feed {
  const [connected, setConnected] = useState(false);
  const [match, setMatch] = useState<MatchInfo | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [control, setControl] = useState<Control | null>(null);
  const [llm, setLlm] = useState<Feed["llm"]>(null);
  const [moments, setMoments] = useState<Moment[]>([]);
  const [cueMap, setCueMap] = useState<Record<string, Cue>>({});
  const [stories, setStories] = useState<Record<string, Story>>({});
  const [spans, setSpans] = useState<Span[]>([]);
  const [lastSpanByAgent, setLast] = useState<Record<string, Span>>({});
  const [ops, setOps] = useState<any>(null);
  const [recaps, setRecaps] = useState<any[]>([]);
  const frame = useRef<Frame | null>(null);
  const [playback] = useState(() => new Playback());
  const clock = useRef(0);
  const ws = useRef<WebSocket | null>(null);
  const pending = useRef(new Map<string, (v: any) => void>());
  const profileRef = useRef(profile);
  profileRef.current = profile;

  useEffect(() => {
    let closed = false;
    let retry = 0;
    let timer: number | undefined;
    const resetTimeline = (msg: { snapshot: Snapshot; moments?: Moment[]; frame?: Frame | null }) => {
      const currentMoments = msg.moments ?? [];
      const currentStories: Record<string, Story> = {};
      for (const m of currentMoments) if (m.story) currentStories[m.id] = m.story;
      setSnap(msg.snapshot); setMoments(currentMoments); setCueMap({});
      // Moment ids repeat after a seek/new match: never attach evidence from the previous timeline.
      setStories(currentStories); setSpans([]); setLast({}); setOps(null); setRecaps([]);
      playback.reset(msg.frame);
      frame.current = msg.frame ?? null;
      clock.current = msg.frame?.t ?? msg.snapshot?.t ?? 0;
    };
    const connect = () => {
      if (closed) return;
      const sock = new WebSocket(wsUrl(profileRef.current, !!opts.ops));
      ws.current = sock;
      sock.onopen = () => {
        if (closed || ws.current !== sock) { sock.close(); return; }
        retry = 0; setConnected(true);
      };
      sock.onclose = () => {
        if (closed || ws.current !== sock) return;
        setConnected(false);
        if (!closed) timer = window.setTimeout(connect, Math.min(4000, 400 * 2 ** retry++));
      };
      sock.onmessage = (e) => {
        if (closed || ws.current !== sock) return;
        const msg = JSON.parse(e.data);
        switch (msg.type) {
          case "hello":
            setMatch(msg.match); setControl(msg.control); setLlm(msg.llm);
            resetTimeline(msg);
            break;
          case "reset":
            resetTimeline(msg);
            break;
          case "frames": {
            const fs: Frame[] = msg.frames ?? [];
            playback.push(fs);
            const last = playback.frames[playback.frames.length - 1];
            if (last) { frame.current = last; clock.current = last.t; }
            break;
          }
          case "state": setSnap(msg.snapshot); setControl(msg.control); break;
          case "control": setControl(msg.control); break;
          case "moment": setMoments((m) => [...m.slice(-150), msg.moment]); break;
          case "cue": case "cue_update":
            setCueMap((m) => ({ ...m, [msg.cue.id]: { ...msg.cue, _wall: (m[msg.cue.id] as any)?._wall ?? performance.now() } }));
            break;
          case "story":
            setStories((s) => ({ ...s, [msg.moment_id]: msg.story }));
            setMoments((ms) => ms.map((x) => (x.id === msg.moment_id ? { ...x, story: msg.story } : x)));
            break;
          case "span":
            setSpans((s) => [...s.slice(-199), msg.span]);
            setLast((l) => ({ ...l, [msg.span.agent]: msg.span }));
            break;
          case "ops": setOps(msg); break;
          case "recap": setRecaps((r) => [...r, msg.recap]); break;
          case "answer": {
            const fn = pending.current.get(msg.id);
            if (fn) { fn(msg); pending.current.delete(msg.id); }
            break;
          }
        }
      };
    };
    connect();
    return () => { closed = true; window.clearTimeout(timer); ws.current?.close(); };
  }, [opts.ops]);

  // profile changes are sent over the open socket: no reconnect, no lost state
  useEffect(() => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ type: "profile", profile }));
    setCueMap((m) => Object.fromEntries(Object.entries(m).filter(([, c]) => PERSISTENT.has(c.kind))));
  }, [profile]);

  // prune expired cues
  useEffect(() => {
    const id = window.setInterval(() => {
      const t = clock.current;
      setCueMap((m) => {
        let changed = false;
        const out: Record<string, Cue> = {};
        for (const [k, c] of Object.entries(m)) {
          // the player-cam card is pinned until its next refresh replaces it (one id per player)
          if (PERSISTENT.has(c.kind) || c.kind === "player_focus" || c.t_out > t - 0.5 || isLive(c, t)) out[k] = c;
          else changed = true;
        }
        return changed ? out : m;
      });
    }, 400);
    return () => window.clearInterval(id);
  }, []);

  const send = useCallback((msg: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(msg));
  }, []);
  const control$ = useCallback((action: string, value?: any) => send({ type: "control", action, value }), [send]);
  const ask = useCallback((question: string) => new Promise<any>((resolve) => {
    if (ws.current?.readyState !== WebSocket.OPEN) {
      resolve({ answer: "Reconnecting to the match: ask again in a moment.", tools: [] });
      return;
    }
    const id = Math.random().toString(36).slice(2);
    pending.current.set(id, resolve);
    send({ type: "ask", id, question });
    window.setTimeout(() => {
      if (pending.current.has(id)) { pending.current.delete(id); resolve({ answer: "No answer (timeout).", tools: [] }); }
    }, 30000);
  }), [send]);

  const cues = useMemo(() => Object.values(cueMap), [cueMap]);
  return { connected, language: profile.language, match, snap, control, llm, moments, cues, stories, spans, ops, recaps, frame, playback, clock,
    lastSpanByAgent, send, control$, ask };
}

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

export function playerIndex(match: MatchInfo | null) {
  const map: Record<string, { name: string; short: string; number: number; team: string; position: string }> = {};
  if (!match) return map;
  for (const t of [match.home, match.away]) {
    for (const p of t.players) map[p.id] = { name: p.name, short: p.short_name, number: p.number, team: t.id, position: p.position };
  }
  return map;
}
