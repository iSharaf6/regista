import type { Feed } from "../lib/feed";

const SPEEDS = [1, 4, 10, 30, 60];

export function Transport({ feed }: { feed: Feed }) {
  const c = feed.control;
  const minute = c ? Math.floor(c.t / 60) : 0;
  return (
    <div className="transport" role="toolbar" aria-label="Playback">
      <button className="btn primary" onClick={() => feed.control$(c?.playing ? "pause" : "play")} aria-label={c?.playing ? "Pause" : "Play"}>
        {c?.playing ? "❚❚ Pause" : "▶ Play"}
      </button>
      <span className="clock">{feed.snap?.clock ?? "0'"}</span>
      <div className="seg" aria-label="Speed">
        {SPEEDS.map((s) => (
          <button key={s} className={c?.speed === s ? "on" : ""} onClick={() => feed.control$("speed", s)}>{s}×</button>
        ))}
      </div>
      <div className="scrub">
        <span className="muted mono">0'</span>
        <input type="range" min={0} max={95} step={1} value={Math.min(95, minute)} aria-label="Jump to minute"
          onChange={(e) => feed.control$("seek", Number(e.target.value))} />
        <span className="muted mono">90'+</span>
      </div>
      <button className="btn small" onClick={() => feed.control$("restart")}>↺ Kick-off</button>
    </div>
  );
}
