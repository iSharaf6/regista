import type { Feed } from "../lib/feed";

const SPEEDS = [1, 4, 10, 30, 60];

export function Transport({ feed }: { feed: Feed }) {
  const c = feed.control;
  // Feed time includes the half-time break; the scrubber seeks football minutes.
  // First-half added time stays at 45 so it cannot masquerade as the second half.
  const [base, added = 0] = (feed.snap?.clock ?? c?.clock ?? "0").replace(/['’′]/g, "").split("+").map(Number);
  const minute = Number.isFinite(base) ? base + (base >= 90 ? added : 0) : 0;
  const off = !feed.connected; // a click while the socket reconnects would be lost: say so instead
  return (
    <div className="transport" role="toolbar" aria-label="Playback" title={off ? "Reconnecting…" : undefined}>
      <button className="btn primary" disabled={off} onClick={() => feed.control$(c?.playing ? "pause" : "play")} aria-label={c?.playing ? "Pause" : "Play"}>
        {c?.playing ? "❚❚ Pause" : "▶ Play"}
      </button>
      <span className="clock">{feed.snap?.clock ?? "0'"}</span>
      <div className="seg" aria-label="Speed">
        {SPEEDS.map((s) => (
          <button key={s} className={c?.speed === s ? "on" : ""} aria-pressed={c?.speed === s} disabled={off} onClick={() => feed.control$("speed", s)}>{s}×</button>
        ))}
      </div>
      <div className="scrub">
        <span className="muted mono">0'</span>
        <input type="range" min={0} max={95} step={1} value={Math.min(95, minute)} aria-label="Jump to minute" disabled={off}
          onChange={(e) => feed.control$("seek", Number(e.target.value))} />
        <span className="muted mono">90'+</span>
      </div>
      <button className="btn small" disabled={off} onClick={() => feed.control$("restart")}>↺ Kick-off</button>
      {off && <span className="muted" role="status">Reconnecting…</span>}
    </div>
  );
}
