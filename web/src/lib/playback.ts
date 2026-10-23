import type { Frame } from "./types";

/** Seconds between frames in the feed (the simulation records five a second). */
const FRAME_GAP = 0.2;
/** Match seconds of ball trail behind the ball. */
const TRAIL_S = 3;
/** Frames further apart than this (half-time, a dropped connection) are cut between, not glided across. */
const MAX_GAP = 2.5;

export interface Pose {
  players: ([number, number] | null)[];
  ball: [number, number, number];
  /** the ball's path over the last few match seconds, ending at the ball */
  trail: [number, number, number][];
  /** the match time on screen */
  t: number;
}

/** Plays the match back smoothly. Frames arrive in bursts (the server sends ten times a second, and over a long network
 *  path they bunch up), so drawing the newest one makes players lurch and the ball cut corners. Instead the screen runs
 *  its own clock at the playback speed, a moment behind the newest frame, and draws the exact in-between of the two
 *  frames either side of that clock. */
export class Playback {
  frames: Frame[] = [];
  /** the match time on screen; NaN until the first step */
  t = NaN;
  /** holding the picture until enough frames are in hand to play smoothly (after a jump, or if the feed ran dry) */
  private waiting = true;
  /** how far the clock has drifted from where it should be, averaged over about a second so bursts don't ripple it */
  private drift = 0;

  /** A new match or a seek: start again from this frame. */
  reset(frame: Frame | null | undefined) {
    this.frames = frame ? [frame] : [];
    this.t = NaN;
    this.waiting = true;
    this.drift = 0;
  }

  push(frames: Frame[]) {
    for (const f of frames) {
      const last = this.frames[this.frames.length - 1];
      // Seeks and new matches have an explicit reset. A late/duplicate frame must never rewind that timeline.
      if (last && f.t <= last.t) continue;
      this.frames.push(f);
    }
    this.trim();
  }

  /** Advance the screen clock by `dt` wall seconds at `rate` match seconds per second (0 when paused). `jitter` is the
   *  wall time to stay behind the feed, to ride out late messages. */
  step(dt: number, rate: number, jitter = 0.25): Pose | null {
    const fs = this.frames;
    if (!fs.length) return null;
    const newest = fs[fs.length - 1].t;
    if (rate > 0) {
      // run one frame gap plus the jitter allowance behind the newest frame, so there is always a frame ahead
      const want = FRAME_GAP + jitter * Math.max(1, rate);
      const goal = newest - want;
      if (!Number.isFinite(this.t) || Math.abs(goal - this.t) > Math.max(4, 3 * want)) {
        this.t = Math.max(fs[0].t, goal); // a new match, a seek or a long stall: jump
        this.waiting = true;
        this.drift = 0;
      }
      // Compare with this draw's expected time, not the previous draw's time. Otherwise normal progress looks like
      // drift, speeding up until the buffer runs dry (especially with the reduced-motion half-second draw interval).
      const expected = this.t + (this.waiting ? 0 : dt * rate);
      this.drift += (goal - expected - this.drift) * Math.min(1, dt);
      if (this.waiting) this.waiting = newest - this.t < want - 1e-6;
      else this.t += dt * rate + this.drift * Math.min(1, dt * 0.5); // the playback speed, drifting back gently
      if (this.t >= newest) this.waiting = true; // ran dry: hold rather than step frame by frame
    } else if (!Number.isFinite(this.t)) {
      this.t = newest; // paused: hold still where we are
    }
    this.t = Math.min(newest, Math.max(fs[0].t, this.t));
    this.trim();

    // the two frames either side of the clock
    let i = fs.length - 1;
    while (i > 0 && fs[i].t > this.t) i--;
    const a = fs[i];
    const b = fs[Math.min(i + 1, fs.length - 1)];
    const span = b.t - a.t;
    let u = span > 0 ? (this.t - a.t) / span : 0;
    u = span > MAX_GAP ? (u < 1 ? 0 : 1) : Math.min(1, Math.max(0, u));
    // players and the ball's height follow a smooth curve through the frames (runs bend, lofted balls arc); the ball
    // along the ground stays on straight lines, so a kick changes its direction at once, as a kick does
    const before = fs[Math.max(0, i - 1)];
    const after = fs[Math.min(fs.length - 1, i + 2)];
    const even = span > 0 && span <= MAX_GAP && Math.abs(a.t - before.t - span) < 0.05 && Math.abs(after.t - b.t - span) < 0.05;
    const curve = (q0: number, q1: number, q2: number, q3: number) =>
      even ? q1 + 0.5 * u * (q2 - q0 + u * (2 * q0 - 5 * q1 + 4 * q2 - q3 + u * (3 * (q1 - q2) + q3 - q0))) : q1 + (q2 - q1) * u;
    const players = a.p.map((p1, k): [number, number] | null => {
      const p2 = b.p[k];
      // Do not introduce a player before their first tracked frame (including across a tracking gap).
      if (!p1) return null;
      if (!p2) return [p1[0], p1[1]];
      const p0 = before.p[k] ?? p1;
      const p3 = after.p[k] ?? p2;
      return [curve(p0[0], p1[0], p2[0], p3[0]), curve(p0[1], p1[1], p2[1], p3[1])];
    });
    const ball: [number, number, number] = [
      a.b[0] + (b.b[0] - a.b[0]) * u, a.b[1] + (b.b[1] - a.b[1]) * u,
      a.b[2] === 0 && b.b[2] === 0 ? 0 : Math.max(0, curve(before.b[2], a.b[2], b.b[2], after.b[2])),
    ];
    const trail: [number, number, number][] = [];
    for (let k = 0; k <= i; k++) if (fs[k].t > this.t - TRAIL_S) trail.push(fs[k].b);
    trail.push(ball);
    return { players, ball, trail, t: this.t };
  }

  /** Keep only what the clock and the trail can still reach. */
  private trim() {
    const fs = this.frames;
    const from = (Number.isFinite(this.t) ? this.t : fs[fs.length - 1]?.t ?? 0) - TRAIL_S - 1;
    let k = 0;
    while (k < fs.length - 2 && fs[k + 1].t < from) k++;
    if (k) fs.splice(0, k);
    if (fs.length > 600) fs.splice(0, fs.length - 600);
  }
}
