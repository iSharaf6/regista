// The story workflow as backend/regista/agents/story.py builds it (build_story_workflow): the Analyst fans out to the
// Narrator (English) and the Localizer (every other market) in parallel; they join at the deterministic Verifier,
// which routes verified copy to the Producer, rejected languages to the Rewriter (and back), and exhausted drafts to
// the Fallback. A deterministic fast lane airs graphics from Interpret straight to the Producer.

interface Node { id: string; x: number; y: number; label: string; sub: string; llm?: boolean; agent?: string }

const W = 118;
const H = 50;
const NODES: Node[] = [
  { id: "feed", x: 12, y: 150, label: "Feed · bus", sub: "Event Hubs" },
  { id: "interpret", x: 150, y: 150, label: "Interpret", sub: "deterministic" },
  { id: "analyst", x: 288, y: 150, label: "Analyst", sub: "LLM agent", llm: true, agent: "Analyst" },
  { id: "narrator", x: 430, y: 78, label: "Narrator", sub: "English", llm: true, agent: "Narrator" },
  { id: "localizer", x: 430, y: 222, label: "Localizer", sub: "ES · FR · AR · PT", llm: true, agent: "Localizer" },
  { id: "verifier", x: 574, y: 150, label: "Verifier", sub: "deterministic", agent: "Verifier" },
  { id: "producer", x: 718, y: 150, label: "Producer", sub: "timed cues", agent: "Producer" },
  { id: "director", x: 862, y: 150, label: "Director ×N", sub: "one per viewer" },
  { id: "rewriter", x: 574, y: 292, label: "Rewriter", sub: "second drafts", llm: true, agent: "Rewriter" },
  { id: "fallback", x: 718, y: 292, label: "Fallback", sub: "grounded templates", agent: "Fallback" },
  { id: "pundit", x: 12, y: 292, label: "Pundit", sub: "on demand", llm: true, agent: "Pundit" },
  { id: "recap", x: 150, y: 292, label: "Recap", sub: "half & full time", llm: true, agent: "Recap" },
];
const at = (id: string) => NODES.find((n) => n.id === id)!;
const right = (id: string, dy = 0) => [at(id).x + W, at(id).y + H / 2 + dy] as const;
const left = (id: string, dy = 0) => [at(id).x, at(id).y + H / 2 + dy] as const;
const top = (id: string, dx = 0) => [at(id).x + W / 2 + dx, at(id).y] as const;
const bottom = (id: string, dx = 0) => [at(id).x + W / 2 + dx, at(id).y + H] as const;

type Pt = readonly [number, number];
const line = (a: Pt, b: Pt) => `M ${a[0]} ${a[1]} L ${b[0]} ${b[1]}`;

export function AgentGraph({ stats, pulses, flowing }: {
  stats: Record<string, { p50_ms?: number | null; calls?: number } | string>;
  pulses: Record<string, { k: string; bad: boolean }>;
  flowing: boolean;
}) {
  const flow = flowing ? "edge flow" : "edge";
  const edges: { d: string; cls: string }[] = [
    { d: line(right("feed"), left("interpret")), cls: flow },
    { d: line(right("interpret"), left("analyst")), cls: flow },
    { d: line(right("analyst", -10), left("narrator")), cls: flow },
    { d: line(right("analyst", 10), left("localizer")), cls: flow },
    { d: line(right("narrator"), left("verifier", -10)), cls: flow },
    { d: line(right("localizer"), left("verifier", 10)), cls: flow },
    { d: line(right("verifier"), left("producer")), cls: flow },
    { d: line(right("producer"), left("director")), cls: flow },
    { d: line(bottom("verifier", -16), top("rewriter", -16)), cls: "edge retry" },
    { d: line(top("rewriter", 16), bottom("verifier", 16)), cls: "edge retry" },
    { d: line(right("verifier", 18), top("fallback", -24)), cls: "edge retry" },
    { d: line(top("fallback"), bottom("producer")), cls: "edge" },
    // the fast lane: deterministic graphics from Interpret straight to the Producer, in milliseconds
    { d: `M ${top("interpret")[0]} ${top("interpret")[1]} C ${top("interpret")[0]} 26, ${top("producer")[0]} 26, ${top("producer")[0]} ${top("producer")[1]}`, cls: "edge fast" },
  ];
  return (
    <svg viewBox="0 0 1000 360" role="img"
      aria-label="Agent workflow: the Analyst fans out to the Narrator and the Localizer in parallel, they join at the Verifier, which sends verified copy to the Producer, rejected copy to the Rewriter and back, and exhausted drafts to the Fallback; a fast lane goes from Interpret straight to the Producer.">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 10 5 0 10z" fill="#1f0024" />
        </marker>
      </defs>
      {edges.map((e, i) => <path key={i} d={e.d} className={e.cls} markerEnd="url(#arr)" />)}
      <text x="500" y="20" className="edge-label" textAnchor="middle">fast lane · deterministic graphics in milliseconds</text>
      <text x="404" y="136" className="edge-label" textAnchor="middle">fan-out</text>
      <text x="556" y="136" className="edge-label" textAnchor="middle">fan-in</text>
      <text x="664" y="140" className="edge-label" textAnchor="middle">verified</text>
      <text x="633" y="356" className="edge-label warn" textAnchor="middle">rejected: rewrite with the fact-check notes</text>
      <text x="756" y="252" className="edge-label warn" textAnchor="start">out of drafts</text>
      {NODES.map((n) => {
        const s = n.agent ? stats[n.agent] : undefined;
        const pulse = n.agent ? pulses[n.agent] : undefined;
        // steps that call no model (routing, the Producer) are not timed: say they are rules, not "p50 -ms"
        const p50 = (ms: number) => (ms >= 1000 ? `p50 ${(ms / 1000).toFixed(1)} s` : `p50 ${Math.round(ms)} ms`);
        const sub = typeof s === "string" ? s : s ? `${s.p50_ms == null ? "rules" : p50(s.p50_ms)} · ${s.calls ?? 0}` : n.sub;
        return (
          <g key={n.id + (pulse?.k ?? "")} className={`node ${n.llm ? "llm" : ""} ${pulse ? "pulse" : ""} ${pulse?.bad ? "bad" : ""}`}>
            <rect x={n.x} y={n.y} width={W} height={H} />
            <text x={n.x + W / 2} y={n.y + 22} textAnchor="middle">{n.label.toUpperCase()}</text>
            <text className="sub" x={n.x + W / 2} y={n.y + 38} textAnchor="middle">{sub}</text>
          </g>
        );
      })}
    </svg>
  );
}
