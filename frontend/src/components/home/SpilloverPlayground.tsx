"use client";

import { useEffect, useMemo, useState } from "react";

// A small interactive network for the home page (1 Nov 2026). Click a dot to "sponsor" that creator and watch the effect travel to neighbours, weaker with each hop.
// It is an ILLUSTRATION of the idea the project tests, with an assumed strength; it is not data, and it says so.

const NODES = [
  { x: 70, y: 210 }, { x: 150, y: 110 }, { x: 150, y: 310 }, { x: 240, y: 200 }, { x: 250, y: 70 }, { x: 255, y: 335 },
  { x: 340, y: 130 }, { x: 345, y: 270 }, { x: 430, y: 60 }, { x: 440, y: 200 }, { x: 425, y: 340 }, { x: 510, y: 130 },
  { x: 515, y: 285 }, { x: 330, y: 205 },
];
const EDGES: [number, number][] = [
  [0, 1], [0, 2], [0, 3], [1, 3], [1, 4], [2, 3], [2, 5], [3, 13], [3, 4], [3, 5], [4, 6], [5, 7], [13, 6], [13, 7], [13, 9],
  [6, 8], [6, 9], [7, 9], [7, 10], [8, 11], [9, 11], [9, 12], [10, 12], [11, 12],
];
const DECAY = 0.55; // assumed share of the effect that survives each hop

function hops(from: number): number[] {
  const adj: number[][] = NODES.map(() => []);
  EDGES.forEach(([a, b]) => {
    adj[a].push(b);
    adj[b].push(a);
  });
  const d = NODES.map(() => Infinity);
  d[from] = 0;
  const q = [from];
  while (q.length) {
    const v = q.shift()!;
    adj[v].forEach((w) => {
      if (d[w] === Infinity) {
        d[w] = d[v] + 1;
        q.push(w);
      }
    });
  }
  return d;
}

export default function SpilloverPlayground() {
  const [sel, setSel] = useState(3);
  const [touched, setTouched] = useState(false);
  const dist = useMemo(() => hops(sel), [sel]);

  // idle: wander from creator to creator until the visitor takes over
  useEffect(() => {
    if (touched || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => setSel((s) => (s + 5) % NODES.length), 2600);
    return () => clearInterval(t);
  }, [touched]);

  const reached = dist.filter((d) => d > 0 && d <= 3).length;
  return (
    <div className="select-none">
      <svg viewBox="0 0 580 400" className="w-full" role="img" aria-label="Interactive illustration: sponsoring one creator and the effect spreading to neighbours">
        <defs>
          <radialGradient id="glow">
            <stop offset="0%" stopColor="#f5b83d" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#f5b83d" stopOpacity="0" />
          </radialGradient>
        </defs>
        {EDGES.map(([a, b], i) => {
          const da = dist[a], db = dist[b];
          const live = Math.min(da, db) < 3 && Number.isFinite(da) && Number.isFinite(db);
          const strength = live ? Math.pow(DECAY, Math.min(da, db)) : 0;
          return (
            <line key={i} x1={NODES[a].x} y1={NODES[a].y} x2={NODES[b].x} y2={NODES[b].y} stroke={live ? "#f5b83d" : "#2e3c4a"} strokeWidth={live ? 1 + 2.4 * strength : 1} opacity={live ? 0.35 + 0.65 * strength : 0.7} strokeDasharray={live ? "6 5" : undefined} style={live ? { animation: "dash 1.2s linear infinite" } : undefined} />
          );
        })}
        {NODES.map((n, i) => {
          const d = dist[i];
          const on = d <= 3;
          const strength = on ? Math.pow(DECAY, d) : 0;
          return (
            <g key={i} onClick={() => { setSel(i); setTouched(true); }} onMouseEnter={() => { if (touched) setSel(i); }} style={{ cursor: "pointer" }}>
              {on && <circle cx={n.x} cy={n.y} r={14 + 26 * strength} fill="url(#glow)" />}
              <circle cx={n.x} cy={n.y} r={i === sel ? 11 : 7.5} fill={i === sel ? "#f5b83d" : on ? "#1a1306" : "#131c25"} stroke={i === sel ? "#ffe3a1" : on ? "#f5b83d" : "#4a5b6d"} strokeWidth={i === sel ? 3 : 2} opacity={on ? 0.45 + 0.55 * strength : 1} style={{ transition: "all 220ms ease" }} />
              <circle cx={n.x} cy={n.y} r="18" fill="transparent" />
            </g>
          );
        })}
      </svg>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-zinc-400">
        <span className="rounded-full border border-signal/50 px-2 py-0.5 uppercase tracking-wider text-signal">illustration</span>
        <span>{touched ? "Sponsor one creator:" : "Tap a dot to sponsor a creator:"} the effect reaches {reached} others, weaker with each hop (assumed).</span>
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">This is the idea we test. On real creators we find no detectable spillover.</p>
    </div>
  );
}
