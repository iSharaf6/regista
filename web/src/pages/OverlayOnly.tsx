import { useEffect, useMemo, useRef } from "react";
import { Overlay } from "../components/Overlay";
import { useFeed } from "../lib/feed";
import { defaultProfile, type Lang, type Mode } from "../lib/types";

/** Transparent graphics-only page for OBS / vMix / CasparCG browser sources.
 *  /#/overlay?mode=analyst&lang=es&team=CAL&player=CAL-10&focus=xg&receipts=0 */
export function OverlayOnly({ query }: { query: URLSearchParams }) {
  const profile = useMemo(() => defaultProfile({
    id: "overlay", mode: (query.get("mode") as Mode) || "casual", language: (query.get("lang") as Lang) || "en",
    favorite_team: query.get("team"), favorite_player: query.get("player"), focus_metric: query.get("focus") || "none",
  }), [query]);
  const feed = useFeed(profile);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    document.documentElement.classList.add("overlay-mode");
    return () => document.documentElement.classList.remove("overlay-mode");
  }, []);
  return (
    <div style={{ position: "fixed", inset: 0, containerType: "inline-size" } as React.CSSProperties}>
      <Overlay ref={ref} feed={feed} receipts={query.get("receipts") === "1"} rtl={profile.language === "ar"} />
    </div>
  );
}
