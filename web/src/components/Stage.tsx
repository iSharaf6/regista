import { useEffect, useRef, useState } from "react";
import { type Feed, isLive } from "../lib/feed";
import { Overlay, OverlayCards } from "./Overlay";
import { type Cam, Pitch } from "./Pitch";

/** Below this width the broadcast cards would shrink past legibility, so they move under the pitch. */
const SPLIT_BELOW = 640;

export function Stage({ feed, favorite, cam, lens, receipts, rtl, label }: {
  feed: Feed; favorite?: string | null; cam: Cam; lens: boolean; receipts: boolean; rtl: boolean; label?: string;
}) {
  const overlay = useRef<HTMLDivElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const [split, setSplit] = useState(false);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSplit(e.contentRect.width < SPLIT_BELOW));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const t = feed.clock.current;
  const tactical = feed.cues.some((c) => c.payload?.moment_kind === "press_shift" && isLive(c, t));
  return (
    <div className="stage-wrap" ref={wrap}>
      <div className="stage">
        <Pitch feed={feed} favorite={favorite} cam={cam} lens={lens || tactical} overlay={overlay} />
        <Overlay ref={overlay} feed={feed} receipts={receipts} rtl={rtl} cards={!split} />
        <div className="stage-label">
          <span className="live-badge">{feed.connected ? "Live" : "Reconnecting"}</span>
          {label ? ` · ${label}` : ""} · synthetic feed
        </div>
      </div>
      {split && <OverlayCards feed={feed} receipts={receipts} rtl={rtl} />}
    </div>
  );
}
