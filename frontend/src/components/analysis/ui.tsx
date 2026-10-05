"use client";

import type { ReactNode } from "react";

// Small building blocks for the Analysis tab. Plain HTML/SVG, no chart library.

export type Tone = "good" | "warn" | "bad" | "info";

const TONE: Record<Tone, string> = {
  good: "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200",
  warn: "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200",
  bad: "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200",
  info: "border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-200",
};

const DOT: Record<Tone, string> = {
  good: "bg-emerald-500",
  warn: "bg-amber-500",
  bad: "bg-rose-500",
  info: "bg-sky-500",
};

export function Verdict({ tone, label, children }: { tone: Tone; label: string; children?: ReactNode }) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${TONE[tone]}`}>
      <div className="flex items-center gap-2 text-sm font-semibold">
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${DOT[tone]}`} />
        {label}
      </div>
      {children && <div className="mt-1 text-sm leading-relaxed opacity-90">{children}</div>}
    </div>
  );
}

export function Card({ title, subtitle, children, className = "" }: { title?: string; subtitle?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 ${className}`}>
      {title && <h3 className="text-sm font-semibold">{title}</h3>}
      {subtitle && <p className="mt-0.5 text-xs text-zinc-500">{subtitle}</p>}
      <div className={title || subtitle ? "mt-3" : ""}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: Tone }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className={`text-xl font-semibold ${tone === "bad" ? "text-rose-600 dark:text-rose-400" : tone === "good" ? "text-emerald-600 dark:text-emerald-400" : tone === "warn" ? "text-amber-600 dark:text-amber-400" : ""}`}>{value}</div>
      {hint && <div className="text-[11px] text-zinc-500">{hint}</div>}
    </div>
  );
}

export interface BarRow {
  label: string;
  value: number;
  note?: string;
  color?: string; // tailwind bg class
}

/** Horizontal bars. `max` defaults to the largest value. */
export function Bars({ rows, max, format = (v: number) => String(v), labelWidth = "11rem" }: { rows: BarRow[]; max?: number; format?: (v: number) => string; labelWidth?: string }) {
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="flex flex-col gap-1.5">
      {rows.map((r) => (
        <li key={r.label} className="grid items-center gap-2 text-xs" style={{ gridTemplateColumns: `minmax(0,${labelWidth}) 1fr auto` }}>
          <span className="truncate text-zinc-600 dark:text-zinc-400" title={r.label}>
            {r.label}
          </span>
          <span className="h-3 rounded-full bg-zinc-100 dark:bg-zinc-800">
            <span className={`block h-3 rounded-full ${r.color ?? "bg-sky-500"}`} style={{ width: `${Math.max(1, (100 * Math.max(0, r.value)) / top)}%` }} />
          </span>
          <span className="w-24 text-right tabular-nums text-zinc-700 dark:text-zinc-300">
            {format(r.value)}
            {r.note ? <span className="text-zinc-400"> {r.note}</span> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

export interface Series {
  name: string;
  points: [number, number][]; // [x, y]
  className: string; // tailwind stroke class, written out in full so Tailwind generates it
  dotClass?: string; // tailwind fill class for the points, same rule
}

/** Simple multi-series line chart with a zero line. x values are numbers (days, lags). */
export function LineChart({
  series,
  height = 190,
  xLabel,
  xTick = (x: number) => String(x),
  yDomain,
}: {
  series: Series[];
  height?: number;
  xLabel?: string;
  xTick?: (x: number) => string;
  yDomain?: [number, number];
}) {
  const W = 640;
  const H = height;
  const pad = { l: 34, r: 10, t: 10, b: 24 };
  const all = series.flatMap((s) => s.points);
  if (all.length === 0) return <p className="text-xs text-zinc-500">No data.</p>;
  const xs = all.map((p) => p[0]);
  const ys = all.map((p) => p[1]);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const [y0, y1] = yDomain ?? [Math.min(0, ...ys) - 0.2, Math.max(0, ...ys) + 0.2];
  const sx = (x: number) => pad.l + ((x - x0) / (x1 - x0 || 1)) * (W - pad.l - pad.r);
  const sy = (y: number) => H - pad.b - ((y - y0) / (y1 - y0 || 1)) * (H - pad.t - pad.b);
  const ticks = 5;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={series.map((s) => s.name).join(" and ")}>
      <line x1={pad.l} x2={W - pad.r} y1={sy(0)} y2={sy(0)} className="stroke-zinc-300 dark:stroke-zinc-700" strokeDasharray="3 3" />
      {Array.from({ length: ticks }, (_, i) => x0 + ((x1 - x0) * i) / (ticks - 1)).map((x, i) => (
        <text key={i} x={sx(x)} y={H - 6} textAnchor="middle" className="fill-zinc-500 text-[10px]">
          {xTick(x)}
        </text>
      ))}
      {[y0, 0, y1].map((y, i) => (
        <text key={i} x={pad.l - 4} y={sy(y) + 3} textAnchor="end" className="fill-zinc-500 text-[10px]">
          {y.toFixed(1)}
        </text>
      ))}
      {series.map((s) => (
        <g key={s.name}>
          <polyline fill="none" strokeWidth={1.8} className={s.className} points={[...s.points].sort((a, b) => a[0] - b[0]).map((p) => `${sx(p[0])},${sy(p[1])}`).join(" ")} />
          {s.dotClass && s.points.map((p, i) => <circle key={i} cx={sx(p[0])} cy={sy(p[1])} r={3} className={s.dotClass} />)}
        </g>
      ))}
      {xLabel && (
        <text x={W - pad.r} y={H - 6} textAnchor="end" className="fill-zinc-400 text-[10px]">
          {xLabel}
        </text>
      )}
    </svg>
  );
}

export function Legend({ items }: { items: { label: string; className: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-600 dark:text-zinc-400">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${i.className}`} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return <p className="text-xs leading-relaxed text-zinc-500">{children}</p>;
}

export function pct(k: number, n: number): string {
  return n ? `${((100 * k) / n).toFixed(0)}%` : "0%";
}
