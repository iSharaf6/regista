import { useRef } from "react";
import { type Feed, isLive } from "../lib/feed";
import { Overlay } from "./Overlay";
import { type Cam, Pitch } from "./Pitch";

export function Stage({ feed, favorite, cam, lens, receipts, rtl, label }: {
  feed: Feed; favorite?: string | null; cam: Cam; lens: boolean; receipts: boolean; rtl: boolean; label?: string;
}) {
  const overlay = useRef<HTMLDivElement>(null);
  const t = feed.clock.current;
  const tactical = feed.cues.some((c) => c.payload?.moment_kind === "press_shift" && isLive(c, t));
  return (
    <div className="stage">
      <Pitch feed={feed} favorite={favorite} cam={cam} lens={lens || tactical} overlay={overlay} />
      <Overlay ref={overlay} feed={feed} receipts={receipts} rtl={rtl} />
      <div className="stage-label">
        <span className="live-badge">{feed.connected ? "Live" : "Reconnecting"}</span>
        {label ? ` · ${label}` : ""} · synthetic feed
      </div>
    </div>
  );
}
