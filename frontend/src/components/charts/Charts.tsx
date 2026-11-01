"use client";

import { useState } from "react";

// Small SVG chart set for the Insights page (1 Nov 2026). No chart library: everything is drawn here so there is nothing to install or break.
// Colours come from the design tokens (amber accent, teal signal) and a blue-slate scale; every chart has a hover readout.

const AMBER = "var(--accent)";
const TEAL = "var(--signal)";
const MUTED = ["#5d6f83", "#7d8fa3", "#4a5b6d", "#9aabbd"];
const GRID = "#1e2b37";
const TEXT = "#8497aa";

const lin = (d0: number, d1: number, r0: number, r1: number) => (v: number) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);

function ticks(min: number, max: number, count = 5): number[] {
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

function Readout({ children }: { children: React.ReactNode }) {
  return <div className="mt-2 min-h-[1.25rem] font-mono text-xs text-zinc-400">{children}</div>;
}

/** Estimate with a 95% interval per row, a zero line, and a hover readout. */
export function ForestPlot({ rows, domain, unit = "", digits = 2, hint }: { rows: { label: string; sub?: string; est: number; lo: number; hi: number; accent?: boolean }[]; domain: [number, number]; unit?: string; digits?: number; hint?: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, left = 200, right = 28, top = 14, rowH = 50, bottom = 34;
  const H = top + rows.length * rowH + bottom;
  const x = lin(domain[0], domain[1], left, W - right);
  const f = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(digits)}${unit}`;
  const r = hover === null ? null : rows[hover];
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Estimates with 95% intervals">
        {ticks(domain[0], domain[1], 6).map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={top} y2={H - bottom} stroke={GRID} />
            <text x={x(t)} y={H - bottom + 18} fill={TEXT} fontSize="11" textAnchor="middle" fontFamily="var(--font-data)">{t}</text>
          </g>
        ))}
        <line x1={x(0)} x2={x(0)} y1={top} y2={H - bottom} stroke="#aab9c8" strokeDasharray="4 4" />
        {rows.map((row, i) => {
          const y = top + i * rowH + rowH / 2;
          const on = hover === i;
          const colour = row.accent ? AMBER : TEAL;
          return (
            <g key={row.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} style={{ cursor: "default" }}>
              <rect x={0} y={y - rowH / 2} width={W} height={rowH} fill={on ? "rgba(245,184,61,0.06)" : "transparent"} />
              <text x={0} y={y - 3} fill="#e4ebf2" fontSize="12.5" fontFamily="var(--font-body)">{row.label}</text>
              {row.sub && <text x={0} y={y + 12} fill={TEXT} fontSize="10.5" fontFamily="var(--font-body)">{row.sub}</text>}
              <line x1={x(Math.max(row.lo, domain[0]))} x2={x(Math.min(row.hi, domain[1]))} y1={y} y2={y} stroke={colour} strokeWidth={on ? 4 : 2.5} strokeLinecap="round" opacity={0.9} />
              <line x1={x(Math.max(row.lo, domain[0]))} x2={x(Math.max(row.lo, domain[0]))} y1={y - 6} y2={y + 6} stroke={colour} strokeWidth="2" />
              <line x1={x(Math.min(row.hi, domain[1]))} x2={x(Math.min(row.hi, domain[1]))} y1={y - 6} y2={y + 6} stroke={colour} strokeWidth="2" />
              <circle cx={x(row.est)} cy={y} r={on ? 7 : 5.5} fill="#0a1016" stroke={colour} strokeWidth="2.5" />
            </g>
          );
        })}
      </svg>
      <Readout>{r ? `${r.label}: ${f(r.est)}  (95% ${f(r.lo)} to ${f(r.hi)})${r.lo <= 0 && r.hi >= 0 ? "  · includes zero" : ""}` : hint ?? "Hover a row"}</Readout>
    </div>
  );
}

/** Grouped bars: one group per setting, one bar per method. Highlighted methods get the accent colours. */
export function GroupedBars({ groups, methods, highlight }: { groups: { label: string; values: Record<string, number | null> }[]; methods: string[]; highlight: Record<string, string> }) {
  const [hover, setHover] = useState<{ g: number; m: string } | null>(null);
  const W = 640, H = 300, left = 44, right = 8, top = 12, bottom = 56;
  const max = Math.max(0.05, ...groups.flatMap((g) => methods.map((m) => g.values[m] ?? 0)));
  const y = lin(0, max * 1.1, H - bottom, top);
  const gw = (W - left - right) / groups.length;
  const bw = Math.min(22, (gw - 18) / methods.length);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Error of each method in each simulated setting">
        {ticks(0, max * 1.1, 5).map((t) => (
          <g key={t}>
            <line x1={left} x2={W - right} y1={y(t)} y2={y(t)} stroke={GRID} />
            <text x={left - 6} y={y(t) + 4} fill={TEXT} fontSize="10.5" textAnchor="end" fontFamily="var(--font-data)">{t.toFixed(2)}</text>
          </g>
        ))}
        {groups.map((g, gi) => {
          const cx = left + gi * gw + gw / 2;
          return (
            <g key={g.label}>
              {methods.map((m, mi) => {
                const v = g.values[m];
                if (v === null || v === undefined) return null;
                const bx = cx - (methods.length * bw) / 2 + mi * bw;
                const on = hover?.g === gi && hover.m === m;
                const colour = highlight[m] ?? MUTED[mi % MUTED.length];
                return <rect key={m} x={bx + 1} y={y(v)} width={bw - 2} height={H - bottom - y(v)} rx="2" fill={colour} opacity={hover && !on ? 0.45 : 1} onMouseEnter={() => setHover({ g: gi, m })} onMouseLeave={() => setHover(null)} />;
              })}
              <text x={cx} y={H - bottom + 18} fill="#cbd6e1" fontSize="11.5" textAnchor="middle" fontFamily="var(--font-body)">{g.label}</text>
            </g>
          );
        })}
      </svg>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-400">
        {methods.map((m, mi) => (
          <span key={m} className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: highlight[m] ?? MUTED[mi % MUTED.length] }} />
            {m}
          </span>
        ))}
      </div>
      <Readout>{hover ? `${hover.m} · ${groups[hover.g].label}: error ${groups[hover.g].values[hover.m]?.toFixed(3)}` : "Hover a bar. Lower is better."}</Readout>
    </div>
  );
}

/** Detection rate against effect size, one line per number of exposed observations. */
export function PowerLines({ effects, series, highlightN }: { effects: number[]; series: { n: number; share: number[] }[]; highlightN?: number | null }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, H = 300, left = 46, right = 16, top = 14, bottom = 44;
  const x = lin(0, 1.5, left, W - right);
  const y = lin(0, 1, H - bottom, top);
  const palette = ["#4a5b6d", "#63768a", "#8497aa", "#35d6c0", "#f5b83d"];
  const readN = hover ?? (highlightN ? series.find((s) => s.n >= highlightN)?.n ?? null : null);
  const cur = series.find((s) => s.n === readN);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Detection rate against effect size">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={left} x2={W - right} y1={y(t)} y2={y(t)} stroke={GRID} />
            <text x={left - 6} y={y(t) + 4} fill={TEXT} fontSize="10.5" textAnchor="end" fontFamily="var(--font-data)">{Math.round(t * 100)}%</text>
          </g>
        ))}
        <line x1={left} x2={W - right} y1={y(0.8)} y2={y(0.8)} stroke={AMBER} strokeDasharray="5 5" opacity="0.7" />
        <text x={W - right} y={y(0.8) - 5} fill={AMBER} fontSize="10.5" textAnchor="end" fontFamily="var(--font-body)">80% detection</text>
        {effects.map((e) => (
          <text key={e} x={x(e)} y={H - bottom + 18} fill={TEXT} fontSize="10.5" textAnchor="middle" fontFamily="var(--font-data)">{e}</text>
        ))}
        <text x={(left + W - right) / 2} y={H - 6} fill={TEXT} fontSize="11" textAnchor="middle" fontFamily="var(--font-body)">planted effect (log scale of engagement; 0.4 is about +50%)</text>
        {series.map((s, i) => {
          const on = readN === s.n;
          const colour = palette[i % palette.length];
          const pts = s.share.map((v, k) => `${x(effects[k])},${y(v)}`).join(" ");
          return (
            <g key={s.n} onMouseEnter={() => setHover(s.n)} onMouseLeave={() => setHover(null)} style={{ cursor: "default" }}>
              <polyline points={pts} fill="none" stroke={colour} strokeWidth={on ? 3.5 : 2} opacity={readN && !on ? 0.4 : 1} strokeLinejoin="round" />
              {s.share.map((v, k) => <circle key={k} cx={x(effects[k])} cy={y(v)} r={on ? 4 : 2.5} fill={colour} />)}
            </g>
          );
        })}
      </svg>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-400">
        {series.map((s, i) => (
          <button key={s.n} onMouseEnter={() => setHover(s.n)} onMouseLeave={() => setHover(null)} className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: palette[i % palette.length] }} />
            {s.n} exposed
          </button>
        ))}
      </div>
      <Readout>{cur ? `${cur.n} exposed observations: ` + cur.share.map((v, k) => `effect ${effects[k]} → ${Math.round(v * 100)}%`).join(" · ") : "Hover a line."}</Readout>
    </div>
  );
}

/** Histogram; `flag` marks values to draw in the accent colour. */
export function Histogram({ values, flags, domain, bins = 14, unit = "", digits = 2, label }: { values: number[]; flags?: boolean[]; domain: [number, number]; bins?: number; unit?: string; digits?: number; label: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, H = 220, left = 34, right = 10, top = 10, bottom = 34;
  const step = (domain[1] - domain[0]) / bins;
  const counts = Array.from({ length: bins }, () => ({ n: 0, flagged: 0 }));
  values.forEach((v, i) => {
    const b = Math.min(bins - 1, Math.max(0, Math.floor((v - domain[0]) / step)));
    counts[b].n += 1;
    if (flags?.[i]) counts[b].flagged += 1;
  });
  const max = Math.max(1, ...counts.map((c) => c.n));
  const x = lin(domain[0], domain[1], left, W - right);
  const y = lin(0, max, H - bottom, top);
  const bw = (W - left - right) / bins;
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={label}>
        {ticks(0, max, 4).map((t) => (
          <g key={t}>
            <line x1={left} x2={W - right} y1={y(t)} y2={y(t)} stroke={GRID} />
            <text x={left - 6} y={y(t) + 4} fill={TEXT} fontSize="10.5" textAnchor="end" fontFamily="var(--font-data)">{t}</text>
          </g>
        ))}
        {counts.map((c, i) => (
          <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <rect x={left + i * bw + 1} y={y(c.n)} width={bw - 2} height={H - bottom - y(c.n)} rx="2" fill={TEAL} opacity={hover !== null && hover !== i ? 0.4 : 0.85} />
            {c.flagged > 0 && <rect x={left + i * bw + 1} y={y(c.n)} width={bw - 2} height={y(c.n - c.flagged) - y(c.n)} rx="2" fill={AMBER} />}
          </g>
        ))}
        {domain[0] < 0 && domain[1] > 0 && <line x1={x(0)} x2={x(0)} y1={top} y2={H - bottom} stroke="#aab9c8" strokeDasharray="4 4" />}
        {ticks(domain[0], domain[1], 6).map((t) => (
          <text key={t} x={x(t)} y={H - bottom + 18} fill={TEXT} fontSize="10.5" textAnchor="middle" fontFamily="var(--font-data)">{t.toFixed(digits)}{unit}</text>
        ))}
      </svg>
      <Readout>
        {hover !== null
          ? `${(domain[0] + hover * step).toFixed(digits)}${unit} to ${(domain[0] + (hover + 1) * step).toFixed(digits)}${unit}: ${counts[hover].n} creators${counts[hover].flagged ? `, ${counts[hover].flagged} flagged` : ""}`
          : "Hover a bar."}
      </Readout>
    </div>
  );
}

/** One segmented bar with counts, for the evidence grades. */
export function SegmentBar({ parts }: { parts: { label: string; value: number; colour: string }[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const total = parts.reduce((s, p) => s + p.value, 0) || 1;
  return (
    <div>
      <div className="flex h-9 w-full overflow-hidden rounded-md">
        {parts.map((p) => (
          <div key={p.label} onMouseEnter={() => setHover(p.label)} onMouseLeave={() => setHover(null)} className="grid place-items-center text-xs font-semibold text-[#0a1016] transition-opacity" style={{ width: `${(100 * p.value) / total}%`, background: p.colour, opacity: hover && hover !== p.label ? 0.45 : 1 }}>
            {p.value / total > 0.06 ? p.label : ""}
          </div>
        ))}
      </div>
      <Readout>
        {hover ? (() => { const p = parts.find((q) => q.label === hover)!; return `${p.label}: ${p.value} creators (${Math.round((100 * p.value) / total)}%)`; })() : "Hover a segment."}
      </Readout>
    </div>
  );
}

/** Horizontal bars with values, for short rankings (Spearman by rule and similar). */
export function HBars({ rows, max, digits = 2 }: { rows: { label: string; value: number; accent?: boolean }[]; max: number; digits?: number }) {
  return (
    <ul className="flex flex-col gap-2.5">
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[minmax(0,1fr)_3.5rem] items-center gap-3 text-xs">
          <div>
            <div className="mb-1 truncate text-zinc-300" title={r.label}>{r.label}</div>
            <div className="h-2 rounded-full bg-zinc-800">
              <div className="h-2 rounded-full transition-all" style={{ width: `${Math.max(2, (100 * r.value) / max)}%`, background: r.accent ? AMBER : "#63768a" }} />
            </div>
          </div>
          <span className="text-right font-mono text-zinc-200">{r.value.toFixed(digits)}</span>
        </li>
      ))}
    </ul>
  );
}
