import qrcode from "qrcode-generator";
import { useMemo, useState } from "react";
import { type Profile, profileQuery } from "../lib/types";

/** "Watch on your phone": a QR code that opens this match on a phone, synced live and re-cut for that fan.
 *  The link carries the viewer profile (#/?mode=&lang=&team=...); every device keeps its own viewer id. */
export function SecondScreen({ profile }: { profile: Profile }) {
  const url = `${typeof location !== "undefined" ? location.origin : ""}/#/?${profileQuery(profile)}`;
  const cells = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(url);
    qr.make();
    const n = qr.getModuleCount();
    const out: [number, number][] = [];
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) out.push([c, r]);
    return { n, out };
  }, [url]);
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch { /* clipboard blocked: the link below stays selectable */ }
  };
  const pad = 2;
  const size = cells.n + pad * 2;
  return (
    <div className="card second-screen">
      <header><h3>Watch on your phone</h3></header>
      <div className="body">
        <div className="qr-row">
          <svg className="qr" viewBox={`0 0 ${size} ${size}`} shapeRendering="crispEdges" role="img" aria-label="QR code for this broadcast">
            <rect width={size} height={size} fill="#ffffff" />
            {cells.out.map(([x, y]) => <rect key={`${x}-${y}`} x={x + pad} y={y + pad} width="1.02" height="1.02" fill="#1f0024" />)}
          </svg>
          <div className="stack" style={{ gap: 8 }}>
            <div className="qr-title">Your own broadcast, synced live</div>
            <div className="muted" style={{ fontSize: 13.5 }}>
              Scan it in the pub or on the sofa: the same match, re-cut for you. Everyone in the room can pick a
              different language, club and viewing mode.
            </div>
            <div className="row" style={{ gap: 6 }}>
              <button className="btn small yellow" onClick={copy}>{copied ? "Copied" : "Copy link"}</button>
              <a className="btn small" href={url} target="_blank" rel="noreferrer">Open</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
