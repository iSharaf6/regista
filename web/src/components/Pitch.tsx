import { useEffect, useRef } from "react";
import type { Feed } from "../lib/feed";

export type Cam = "broadcast" | "tactical";
const L = 105;
const W = 68;

// Voxel night match: flat colours, ink outlines, hard shadows falling to the right, purple stands under floodlights.
const C = {
  ink: "#1f0024", cream: "#ffffff", cream2: "#4a1450", cream3: "#3e0f44", sky: "#37003c",
  grassA: "#a2d65c", grassB: "#88c247", apron: "#79b941", yellow: "#00ff85", shadow: "rgba(31,0,36,0.3)",
};
const PX = '"Silkscreen", "Lilita One", sans-serif';
const SKIN = ["#f2c9a1", "#e3b183", "#c98b5e", "#9a6440", "#6b4430"];
const HAIR = ["#26262e", "#3a2a20", "#6b4430", "#26262e", "#c98b5e", "#3a2a20"];
const CROWD = ["#e90052", "#04f5ff", "#00ff85", "#ffffff", "#ffffff", "#1f0024", "#0E7C7B", "#E4572E", "#8a5cf6", "#17255A"];
const BOARDS: [string, string, string][] = [
  ["#00ff85", C.ink, "REGISTA"], ["#e90052", C.cream, "MATCH DIRECTOR"], ["#04f5ff", C.ink, "RECEIPTS ON"],
  ["#ffffff", "#37003c", "FAN STUDIO"], ["#37003c", "#00ff85", "LIVE DATA"],
];

interface Proj {
  pt: (x: number, y: number) => { x: number; y: number };
  ppm: (y: number) => number; // pixels per metre at a pitch row
}

function projection(cam: Cam, cw: number, ch: number): Proj {
  if (cam === "tactical") {
    const m = Math.min(cw, ch) * 0.06;
    const s = Math.min((cw - 2 * m) / L, (ch - 2 * m) / W);
    const ox = cw / 2 - (L / 2) * s;
    const oy = ch / 2 - (W / 2) * s;
    return { pt: (x, y) => ({ x: ox + x * s, y: oy + y * s }), ppm: () => s };
  }
  const top = ch * 0.2;
  const bottom = ch * 0.05;
  const hp = ch - top - bottom;
  const k = 0.6;
  const wTop = cw * 0.66;
  const wBot = cw * 1.04;
  const f = (v: number) => (v * (1 + k)) / (1 + k * v);
  const wAt = (v: number) => wTop + (wBot - wTop) * f(v);
  return {
    pt: (x, y) => {
      const v = y / W;
      return { x: cw / 2 + (x / L - 0.5) * wAt(v), y: top + hp * f(v) };
    },
    ppm: (y) => wAt(y / W) / L,
  };
}

function shade(hex: string, f: number): string {
  const n = parseInt(hex.slice(1, 7), 16);
  const ch = (v: number) => Math.max(0, Math.min(255, Math.round(v * f)));
  return `rgb(${ch((n >> 16) & 255)},${ch((n >> 8) & 255)},${ch(n & 255)})`;
}

function rng(seed: number) {
  let s = seed % 2147483647 || 1;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

function poly(ctx: CanvasRenderingContext2D, P: Proj, pts: [number, number][], close = false) {
  ctx.beginPath();
  pts.forEach(([x, y], i) => {
    const s = P.pt(x, y);
    if (i === 0) ctx.moveTo(s.x, s.y);
    else ctx.lineTo(s.x, s.y);
  });
  if (close) ctx.closePath();
}

function screenPoly(ctx: CanvasRenderingContext2D, pts: [number, number][]) {
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
  ctx.closePath();
}

function circlePts(cx: number, cy: number, r: number, a0 = 0, a1 = Math.PI * 2, n = 48): [number, number][] {
  const out: [number, number][] = [];
  for (let i = 0; i <= n; i++) {
    const a = a0 + ((a1 - a0) * i) / n;
    out.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
  }
  return out;
}

// ------------------------------------------------------------------ static scene (cached per size and camera)
function drawStands(ctx: CanvasRenderingContext2D, cw: number, boardTop: number) {
  const sky = Math.round(boardTop * 0.12);
  ctx.fillStyle = C.sky;
  ctx.fillRect(0, 0, cw, sky);
  // floodlights along the roof
  const lamp = Math.max(3, sky * 0.45);
  for (let x = cw * 0.08; x < cw; x += cw * 0.21) {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(x, (sky - lamp) / 2, lamp * 3, lamp);
    ctx.fillStyle = "#04f5ff";
    ctx.fillRect(x + lamp, (sky - lamp) / 2, lamp, lamp);
  }
  ctx.fillStyle = C.ink;
  ctx.fillRect(0, sky, cw, 3);
  const bs = Math.max(5, boardTop * 0.16);
  const rowH = bs * 1.25;
  const rows = Math.max(1, Math.floor((boardTop - sky - 3) / rowH));
  const r = rng(7);
  for (let row = 0; row < rows; row++) {
    const y0 = sky + 3 + row * rowH;
    ctx.fillStyle = row % 2 ? C.cream3 : C.cream2;
    ctx.fillRect(0, y0, cw, rowH);
    for (let x = -bs * 0.3 + (row % 2) * bs * 0.55; x < cw; x += bs * 1.12) {
      if (r() < 0.08) continue; // an empty seat
      const shirt = CROWD[Math.floor(r() * CROWD.length)];
      const skin = SKIN[Math.floor(r() * SKIN.length)];
      const jx = x + (r() - 0.5) * bs * 0.2;
      ctx.fillStyle = shirt;
      ctx.fillRect(jx, y0 + rowH * 0.55, bs * 0.9, rowH * 0.45);
      ctx.fillStyle = skin;
      ctx.fillRect(jx + bs * 0.12, y0 + rowH * 0.12, bs * 0.66, bs * 0.6);
      ctx.fillStyle = HAIR[Math.floor(r() * HAIR.length)];
      ctx.fillRect(jx + bs * 0.12, y0 + rowH * 0.12, bs * 0.66, bs * 0.18);
    }
  }
  ctx.fillStyle = shade(C.cream3, 0.85);
  ctx.fillRect(0, sky + 3 + rows * rowH, cw, Math.max(0, boardTop - (sky + 3 + rows * rowH)));
}

function drawBoards(ctx: CanvasRenderingContext2D, cw: number, top: number, h: number) {
  ctx.fillStyle = C.ink;
  ctx.fillRect(0, top - 2, cw, h + 4);
  const seg = Math.max(140, cw / 5);
  ctx.font = `700 ${Math.round(h * 0.52)}px ${PX}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  let i = 0;
  for (let x = -seg * 0.35; x < cw; x += seg, i++) {
    const [bg, fg, label] = BOARDS[i % BOARDS.length];
    ctx.fillStyle = bg;
    ctx.fillRect(x + 1, top, seg - 2, h);
    ctx.fillStyle = fg;
    ctx.fillText(label, x + seg / 2, top + h * 0.55, seg - 12);
  }
}

function drawGoal(ctx: CanvasRenderingContext2D, P: Proj, side: 0 | 1, cam: Cam) {
  const x0 = side ? L : 0;
  const d = side ? 1 : -1; // out of the pitch
  const lw = Math.max(2, P.ppm(W / 2) * 0.22);
  if (cam === "tactical") {
    poly(ctx, P, [[x0, W / 2 - 3.66], [x0 + d * 2, W / 2 - 3.66], [x0 + d * 2, W / 2 + 3.66], [x0, W / 2 + 3.66]], true);
    ctx.fillStyle = "rgba(251,251,244,0.55)";
    ctx.fill();
    ctx.strokeStyle = C.ink;
    ctx.lineWidth = lw + 2;
    ctx.stroke();
    ctx.strokeStyle = C.cream;
    ctx.lineWidth = lw;
    ctx.stroke();
    return;
  }
  const up = (x: number, y: number, h: number) => {
    const s = P.pt(x, y);
    return [s.x, s.y - h * P.ppm(y)] as [number, number];
  };
  const y1 = W / 2 - 3.66;
  const y2 = W / 2 + 3.66;
  const f1 = up(x0, y1, 0), f2 = up(x0, y2, 0), t1 = up(x0, y1, 2.44), t2 = up(x0, y2, 2.44);
  const b1 = up(x0 + d * 2, y1, 0), b2 = up(x0 + d * 2, y2, 0), bt1 = up(x0 + d * 2, y1, 1.9), bt2 = up(x0 + d * 2, y2, 1.9);
  ctx.fillStyle = "rgba(251,251,244,0.5)";
  for (const face of [[b1, b2, bt2, bt1], [t1, t2, bt2, bt1], [f1, t1, bt1, b1], [f2, t2, bt2, b2]] as [number, number][][]) {
    screenPoly(ctx, face);
    ctx.fill();
  }
  ctx.strokeStyle = "rgba(38,38,46,0.25)";
  ctx.lineWidth = 1;
  for (let i = 1; i < 8; i++) {
    const a = i / 8;
    ctx.beginPath();
    ctx.moveTo(bt1[0] + (bt2[0] - bt1[0]) * a, bt1[1] + (bt2[1] - bt1[1]) * a);
    ctx.lineTo(b1[0] + (b2[0] - b1[0]) * a, b1[1] + (b2[1] - b1[1]) * a);
    ctx.stroke();
  }
  const frame = () => {
    ctx.beginPath();
    ctx.moveTo(...f1);
    ctx.lineTo(...t1);
    ctx.lineTo(...t2);
    ctx.lineTo(...f2);
  };
  ctx.lineJoin = "miter";
  frame();
  ctx.strokeStyle = C.ink;
  ctx.lineWidth = lw + 3;
  ctx.stroke();
  frame();
  ctx.strokeStyle = C.cream;
  ctx.lineWidth = lw;
  ctx.stroke();
}

function drawScene(ctx: CanvasRenderingContext2D, P: Proj, cam: Cam, cw: number, ch: number) {
  if (cam === "broadcast") {
    const boardBottom = P.pt(L / 2, -2.5).y;
    const boardH = Math.max(10, ch * 0.05);
    const boardTop = boardBottom - boardH;
    drawStands(ctx, cw, boardTop - 2);
    ctx.fillStyle = C.apron;
    ctx.fillRect(0, boardBottom, cw, ch - boardBottom);
    drawBoards(ctx, cw, boardTop, boardH);
  } else {
    ctx.fillStyle = C.apron;
    ctx.fillRect(0, 0, cw, ch);
  }
  // mown stripes
  const bands = 14;
  for (let i = 0; i < bands; i++) {
    const x0 = (L / bands) * i;
    const x1 = (L / bands) * (i + 1);
    poly(ctx, P, [[x0, 0], [x1, 0], [x1, W], [x0, W]], true);
    ctx.fillStyle = i % 2 ? C.grassA : C.grassB;
    ctx.fill();
  }
  ctx.strokeStyle = C.cream;
  ctx.lineWidth = Math.max(1.5, P.ppm(W / 2) * 0.16);
  ctx.lineJoin = "miter";
  const stroke = (pts: [number, number][], close = false) => { poly(ctx, P, pts, close); ctx.stroke(); };
  stroke([[0, 0], [L, 0], [L, W], [0, W]], true);
  stroke([[L / 2, 0], [L / 2, W]]);
  stroke(circlePts(L / 2, W / 2, 9.15));
  const spot = (x: number, y: number) => {
    const s = P.pt(x, y);
    const r = Math.max(1.5, P.ppm(y) * 0.28);
    ctx.fillStyle = C.cream;
    ctx.fillRect(s.x - r, s.y - r * 0.7, r * 2, r * 1.4);
  };
  for (const side of [0, 1] as const) {
    const x0 = side ? L : 0;
    const d = side ? -1 : 1;
    stroke([[x0, W / 2 - 20.16], [x0 + d * 16.5, W / 2 - 20.16], [x0 + d * 16.5, W / 2 + 20.16], [x0, W / 2 + 20.16]]);
    stroke([[x0, W / 2 - 9.16], [x0 + d * 5.5, W / 2 - 9.16], [x0 + d * 5.5, W / 2 + 9.16], [x0, W / 2 + 9.16]]);
    const ps = x0 + d * 11;
    const arc = Math.acos(5.5 / 9.15);
    stroke(side ? circlePts(ps, W / 2, 9.15, Math.PI - arc, Math.PI + arc, 20) : circlePts(ps, W / 2, 9.15, -arc, arc, 20));
    spot(ps, W / 2);
  }
  spot(L / 2, W / 2);
  drawGoal(ctx, P, 0, cam);
  drawGoal(ctx, P, 1, cam);
}

// ------------------------------------------------------------------ actors
function drawPlayer(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, shirt: string, trim: string,
  skin: string, hair: string, num: number | undefined, cam: Cam) {
  ctx.lineWidth = Math.max(1, r * 0.11);
  ctx.strokeStyle = C.ink;
  ctx.lineJoin = "miter";
  if (cam === "tactical") {
    const s = r * 1.25;
    ctx.fillStyle = C.shadow;
    ctx.fillRect(x - s / 2 + r * 0.28, y - s / 2 + r * 0.28, s, s);
    ctx.fillStyle = shirt;
    ctx.fillRect(x - s / 2, y - s / 2, s, s);
    ctx.strokeRect(x - s / 2, y - s / 2, s, s);
    if (r >= 6 && num !== undefined) {
      ctx.fillStyle = trim;
      ctx.font = `700 ${Math.round(s * 0.62)}px ${PX}`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(num), x, y + s * 0.06);
    }
    return;
  }
  // hard sun shadow, thrown to the right like the game's
  ctx.fillStyle = C.shadow;
  screenPoly(ctx, [[x - r * 0.48, y], [x + r * 0.48, y], [x + r * 1.45, y - r * 0.42], [x + r * 0.5, y - r * 0.42]]);
  ctx.fill();
  const dx = r * 0.22;
  const dy = r * 0.16;
  const box = (x0: number, y0: number, w: number, h: number, front: string, side: string, top?: string) => {
    if (top) {
      ctx.fillStyle = top;
      screenPoly(ctx, [[x0, y0], [x0 + w, y0], [x0 + w + dx, y0 - dy], [x0 + dx, y0 - dy]]);
      ctx.fill();
      ctx.stroke();
    }
    ctx.fillStyle = side;
    screenPoly(ctx, [[x0 + w, y0], [x0 + w + dx, y0 - dy], [x0 + w + dx, y0 + h - dy], [x0 + w, y0 + h]]);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = front;
    ctx.fillRect(x0, y0, w, h);
    ctx.strokeRect(x0, y0, w, h);
  };
  // legs in the trim colour, the shirt, then the head with its hair on top
  const legSide = shade(trim, 0.8);
  box(x - r * 0.4, y - r * 0.42, r * 0.32, r * 0.42, trim, legSide);
  box(x + r * 0.08, y - r * 0.42, r * 0.32, r * 0.42, trim, legSide);
  box(x - r * 0.5, y - r * 1.22, r, r * 0.82, shirt, shade(shirt, 0.78));
  const hs = r * 0.66;
  box(x - hs / 2, y - r * 1.22 - hs, hs, hs, skin, shade(skin, 0.82), hair);
  ctx.fillStyle = C.ink;
  const eye = Math.max(1, hs * 0.14);
  ctx.fillRect(x - hs * 0.28, y - r * 1.22 - hs * 0.55, eye, Math.max(1, hs * 0.18));
  ctx.fillRect(x + hs * 0.14, y - r * 1.22 - hs * 0.55, eye, Math.max(1, hs * 0.18));
  if (r >= 11 && num !== undefined) {
    ctx.fillStyle = trim;
    ctx.font = `700 ${Math.round(r * 0.46)}px ${PX}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(num), x, y - r * 0.8);
  }
}

function drawMarker(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, now: number) {
  const bob = Math.round(Math.sin(now / 180) * 2) * r * 0.06;
  const w = r * 0.9;
  const h = r * 0.62;
  const top = y - bob;
  ctx.fillStyle = C.yellow;
  ctx.strokeStyle = C.ink;
  ctx.lineWidth = Math.max(1.5, r * 0.12);
  screenPoly(ctx, [[x - w / 2, top - h], [x + w / 2, top - h], [x, top]]);
  ctx.fill();
  ctx.stroke();
}

function drawBall(ctx: CanvasRenderingContext2D, x: number, groundY: number, by: number, br: number) {
  ctx.fillStyle = C.shadow;
  ctx.fillRect(x - br * 0.9 + (groundY - by) * 0.25, groundY - br * 0.35, br * 1.8, br * 0.7);
  const s = br * 2;
  ctx.fillStyle = C.cream;
  ctx.strokeStyle = C.ink;
  ctx.lineWidth = Math.max(1, br * 0.28);
  ctx.fillRect(x - br, by - br, s, s);
  ctx.strokeRect(x - br, by - br, s, s);
  ctx.fillStyle = C.ink;
  const p = Math.max(1, br * 0.55);
  ctx.fillRect(x - p / 2, by - p / 2, p, p);
}

export function Pitch({ feed, favorite, cam, lens, overlay }: {
  feed: Feed; favorite?: string | null; cam: Cam; lens: boolean; overlay: React.RefObject<HTMLDivElement | null>;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const props = useRef({ favorite, cam, lens, match: feed.match });
  props.current = { favorite, cam, lens, match: feed.match };

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let disp: ([number, number] | null)[] = [];
    let ball: [number, number, number] = [L / 2, W / 2, 0];
    let scene: { key: string; canvas: HTMLCanvasElement } | null = null;
    const draw = (now: number) => {
      raf = requestAnimationFrame(draw);
      const el = canvas.current;
      if (!el) return;
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const cw = el.clientWidth;
      const ch = el.clientHeight;
      if (!cw || !ch) return;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      if (el.width !== Math.round(cw * dpr) || el.height !== Math.round(ch * dpr)) {
        el.width = Math.round(cw * dpr);
        el.height = Math.round(ch * dpr);
      }
      const ctx = el.getContext("2d")!;
      const { favorite, cam, lens, match } = props.current;
      const P = projection(cam, cw, ch);
      // the scene is cached; redraw it once the pixel font arrives so the board lettering is crisp
      const fontsReady = document.fonts?.check?.(`700 12px ${PX}`) ? 1 : 0;
      const key = `${cam}:${cw}x${ch}@${dpr}:${fontsReady}`;
      if (!scene || scene.key !== key) {
        const off = document.createElement("canvas");
        off.width = el.width;
        off.height = el.height;
        const octx = off.getContext("2d")!;
        octx.setTransform(dpr, 0, 0, dpr, 0, 0);
        drawScene(octx, P, cam, cw, ch);
        scene = { key, canvas: off };
      }
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.drawImage(scene.canvas, 0, 0);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const f = feed.frame.current;
      if (!f || !match) return;
      const a = 1 - Math.exp(-dt * 9);
      disp = f.p.map((p, i) => {
        const d = disp[i];
        if (!p) return null;
        if (!d) return [p[0], p[1]];
        return [d[0] + (p[0] - d[0]) * a, d[1] + (p[1] - d[1]) * a];
      });
      ball = [ball[0] + (f.b[0] - ball[0]) * Math.min(1, a * 1.6), ball[1] + (f.b[1] - ball[1]) * Math.min(1, a * 1.6),
        ball[2] + (f.b[2] - ball[2]) * a];
      const roster = match.roster;
      const homeIds = new Set(match.home.players.map((p) => p.id));
      const gk = new Set([...match.home.players, ...match.away.players].filter((p) => p.position === "GK").map((p) => p.id));
      const numbers: Record<string, number> = {};
      for (const t of [match.home, match.away]) for (const p of t.players) numbers[p.id] = p.number;

      if (lens) drawLens(ctx, P, disp, roster, homeIds, gk, ball, match.home.primary, match.away.primary);

      // ball trail
      const tr = feed.trail.current;
      if (tr.length > 2) {
        ctx.lineCap = "square";
        for (let i = 1; i < tr.length; i++) {
          const p0 = P.pt(tr[i - 1][0], tr[i - 1][1]);
          const p1 = P.pt(tr[i][0], tr[i][1]);
          ctx.strokeStyle = `rgba(0,255,133,${(i / tr.length) * 0.8})`;
          ctx.lineWidth = Math.max(1.5, P.ppm(tr[i][1]) * 0.3 * (i / tr.length));
          ctx.beginPath();
          ctx.moveTo(p0.x, p0.y);
          ctx.lineTo(p1.x, p1.y);
          ctx.stroke();
        }
        ctx.lineCap = "butt";
      }
      // players and the ball, far to near so near ones overlap far ones
      const actors = disp.map((p, i) => [i, p ? p[1] : -1] as const).filter(([, y]) => y >= 0);
      actors.push([-1, ball[1]]);
      actors.sort((x, y) => x[1] - y[1]);
      for (const [i] of actors) {
        if (i < 0) {
          const g = P.pt(ball[0], ball[1]);
          const ppm = P.ppm(ball[1]);
          const br = Math.max(3, ppm * 0.55);
          const by = cam === "tactical" ? g.y : g.y - br - ball[2] * ppm * 0.9;
          drawBall(ctx, g.x, g.y, by, br);
          continue;
        }
        const p = disp[i]!;
        const pid = roster[i];
        const s = P.pt(p[0], p[1]);
        // players are drawn oversized, as in the game: about 1.5 m wide on the broadcast camera
        const r = Math.max(cam === "tactical" ? 4 : 6, P.ppm(p[1]) * (cam === "tactical" ? 0.95 : 1.5));
        const isHome = homeIds.has(pid);
        const team = isHome ? match.home : match.away;
        const keeper = gk.has(pid);
        const shirt = keeper ? (isHome ? "#ffd23a" : "#8a5cf6") : team.primary;
        const trim = keeper ? "#26262e" : team.secondary;
        drawPlayer(ctx, s.x, s.y, r, shirt, trim, SKIN[i % SKIN.length], HAIR[(i * 7) % HAIR.length], numbers[pid], cam);
        if (pid === favorite) drawMarker(ctx, s.x, cam === "tactical" ? s.y - r * 0.8 : s.y - r * 2.15, r, now);
      }

      // pin follow graphics (player tags, speed flashes) to their players
      const ov = overlay.current;
      if (ov) {
        ov.querySelectorAll<HTMLElement>("[data-follow]").forEach((node) => {
          const i = roster.indexOf(node.dataset.follow || "");
          const p = i >= 0 ? disp[i] : null;
          if (!p) { node.style.transform = "translate(-9999px,-9999px)"; return; }
          const s = P.pt(p[0], p[1]);
          node.style.transform = `translate(${s.x}px, ${s.y}px)`;
        });
      }
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [feed.frame, feed.trail, overlay]);

  return <canvas ref={canvas} aria-label="Live synthetic match: player and ball tracking" role="img" />;
}

function label(ctx: CanvasRenderingContext2D, text: string, x: number, y: number) {
  ctx.font = `700 11px ${PX}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const w = ctx.measureText(text).width + 12;
  ctx.fillStyle = C.ink;
  ctx.fillRect(x - w / 2, y - 9, w, 17);
  ctx.fillStyle = C.cream;
  ctx.fillText(text, x, y + 1);
}

function drawLens(ctx: CanvasRenderingContext2D, P: Proj, disp: ([number, number] | null)[], roster: string[],
  homeIds: Set<string>, gk: Set<string>, ball: [number, number, number], homeColor: string, awayColor: string) {
  for (const home of [true, false]) {
    const xs = disp
      .map((p, i) => (p && homeIds.has(roster[i]) === home && !gk.has(roster[i]) ? (home ? p[0] : L - p[0]) : null))
      .filter((v): v is number => v !== null)
      .sort((a, b) => a - b);
    if (xs.length < 4) continue;
    const depth = (xs[0] + xs[1] + xs[2] + xs[3]) / 4;
    const x = home ? depth : L - depth;
    ctx.save();
    poly(ctx, P, [[x, 0], [x, W]]);
    ctx.strokeStyle = C.ink;
    ctx.lineWidth = 5;
    ctx.stroke();
    ctx.setLineDash([10, 6]);
    ctx.strokeStyle = home ? homeColor : awayColor;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.restore();
    const s = P.pt(x, -1.2);
    label(ctx, `LINE ${depth.toFixed(0)}M`, s.x, s.y - 8);
  }
  // 8 m pressing radius around the ball, with who is inside it
  ctx.save();
  poly(ctx, P, circlePts(ball[0], ball[1], 8, 0, Math.PI * 2, 40), true);
  ctx.fillStyle = "rgba(0,255,133,0.2)";
  ctx.fill();
  ctx.setLineDash([6, 5]);
  ctx.strokeStyle = C.ink;
  ctx.lineWidth = 2.5;
  ctx.stroke();
  ctx.restore();
  let h = 0;
  let a = 0;
  disp.forEach((p, i) => {
    if (!p) return;
    if (Math.hypot(p[0] - ball[0], p[1] - ball[1]) < 8) {
      if (homeIds.has(roster[i])) h++;
      else a++;
    }
  });
  const s = P.pt(ball[0], ball[1] + 9);
  ctx.font = `700 12px ${PX}`;
  ctx.textBaseline = "middle";
  ctx.textAlign = "center";
  ctx.fillStyle = C.ink;
  ctx.fillRect(s.x - 34, s.y - 2, 68, 18);
  ctx.fillStyle = homeColor;
  ctx.fillRect(s.x - 28, s.y + 3, 8, 8);
  ctx.fillStyle = awayColor;
  ctx.fillRect(s.x + 20, s.y + 3, 8, 8);
  ctx.fillStyle = C.cream;
  ctx.fillText(`${h} V ${a}`, s.x, s.y + 8);
}
