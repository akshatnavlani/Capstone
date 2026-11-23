"use client";

import { useEffect, useState } from "react";
import { getTimeline, type CreatorTimeline } from "@/lib/api";

// One creator's recent YouTube videos and Instagram posts on one time axis, each post as a % of that platform's usual
// (the median of the posts shown, = 100%). Indexing both to their own usual puts views and likes on one common scale.
// Data: GET /platform-profiles/{id}/timeline (YouTube videos older than 7 days with views, Instagram posts with likes).
const SERIES = [
  { key: "youtube", label: "YouTube views", color: "#f5b83d", dash: undefined },
  { key: "instagram", label: "Instagram likes", color: "#35d6c0", dash: "6 4" },
] as const;

const WINDOW_DAYS = 90;

type Pt = { t: number; n: number; rel: number; sp: boolean };

export default function PlatformTimelineChart({ creatorId }: { creatorId: string }) {
  const [tl, setTl] = useState<CreatorTimeline | null>(null);
  const [failed, setFailed] = useState(false);
  const [hover, setHover] = useState<{ s: number; i: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getTimeline(creatorId)
      .then((d) => !cancelled && setTl(d))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [creatorId]);

  if (failed) return null;
  if (!tl) return <p className="mt-3 text-[11px] text-zinc-500">Loading the post-by-post chart…</p>;

  // Last 90 days before the newest post (the cards' "Posts, last 90 days" window), so a few old posts do not squeeze the recent ones.
  const newest = Math.max(0, ...tl.youtube.map((v) => new Date(v.at).getTime()), ...tl.instagram.map((v) => new Date(v.at).getTime()));
  const since = newest - WINDOW_DAYS * 86400000;
  const lines = SERIES.map((s) => {
    const raw = s.key === "youtube" ? tl.youtube.map((v) => ({ at: v.at, n: v.views, sp: v.sponsored })) : tl.instagram.map((v) => ({ at: v.at, n: v.likes, sp: v.sponsored }));
    const pos = raw.filter((p) => p.n > 0 && new Date(p.at).getTime() >= since);
    const sorted = pos.map((p) => p.n).sort((a, b) => a - b);
    const med = sorted.length ? sorted[Math.floor(sorted.length / 2)] : 1;
    const pts: Pt[] = pos.map((p) => ({ t: new Date(p.at).getTime(), n: p.n, rel: (100 * p.n) / med, sp: p.sp })).sort((a, b) => a.t - b.t);
    return { ...s, pts, ok: pts.length >= 3 };
  });
  const shown = lines.filter((l) => l.ok);
  if (shown.length === 0) return <p className="mt-3 text-[11px] text-zinc-500">Not enough recent posts with counts to draw a chart.</p>;

  const VW = 760, VH = 260, L = 56, R = 110, T = 16, B = 40;
  const ts = shown.flatMap((l) => l.pts.map((p) => p.t));
  const t0 = Math.min(...ts), t1 = Math.max(...ts);
  const rels = shown.flatMap((l) => l.pts.map((p) => p.rel));
  const y0 = Math.min(50, Math.min(...rels) / 1.2), y1 = Math.max(200, Math.max(...rels) * 1.15);
  const X = (t: number) => L + (t1 === t0 ? 0.5 : (t - t0) / (t1 - t0)) * (VW - L - R);
  const Y = (v: number) => VH - B - ((Math.log10(v) - Math.log10(y0)) / (Math.log10(y1) - Math.log10(y0))) * (VH - T - B);
  const ticks = [10, 25, 50, 100, 200, 400, 800, 1600, 3200].filter((v) => v >= y0 && v <= y1);
  const date = (t: number) => new Date(t).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  const xticks = Array.from({ length: 4 }, (_, k) => t0 + ((t1 - t0) * k) / 3);
  const hl = hover ? shown[hover.s] : undefined;
  const hp = hl && hover ? hl.pts[hover.i] : undefined;
  const latest = shown.map((l) => `${l.key === "youtube" ? "YouTube" : "Instagram"} ${Math.round(l.pts[l.pts.length - 1].rel)}%`);

  return (
    <div className="mt-3 rounded-md bg-zinc-50 p-3 dark:bg-zinc-900">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-xs font-medium">Post by post: YouTube vs Instagram</span>
        <span className="flex gap-3 text-[11px] text-zinc-400">
          {lines.map((l) => (
            <span key={l.key} className="flex items-center gap-1.5">
              <svg width="18" height="6" aria-hidden>
                <line x1="0" y1="3" x2="18" y2="3" stroke={l.color} strokeWidth="2" strokeDasharray={l.dash} />
              </svg>
              {l.label}
              {!l.ok && " (too few recent posts)"}
            </span>
          ))}
        </span>
      </div>
      <div className="relative">
        <svg viewBox={`0 0 ${VW} ${VH}`} className="mt-1 block h-auto w-full" role="img" aria-label="Recent posts on YouTube and Instagram compared with each platform's usual" onMouseLeave={() => setHover(null)}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={L} x2={VW - R} y1={Y(v)} y2={Y(v)} stroke="currentColor" className={v === 100 ? "text-zinc-500" : "text-zinc-800"} strokeDasharray={v === 100 ? "4 4" : undefined} strokeWidth={1} />
              <text x={L - 8} y={Y(v) + 4} textAnchor="end" fontSize="11" fill="currentColor" className="text-zinc-500">
                {v}%
              </text>
            </g>
          ))}
          <text x={VW - R + 6} y={Y(100) + 4} fontSize="11" fill="currentColor" className="text-zinc-400">
            usual
          </text>
          {xticks.map((t, k) => (
            <text key={k} x={X(t)} y={VH - B + 18} textAnchor="middle" fontSize="11" fill="currentColor" className="text-zinc-500">
              {date(t)}
            </text>
          ))}
          <text x={L + (VW - L - R) / 2} y={VH - 4} textAnchor="middle" fontSize="11" fill="currentColor" className="text-zinc-500">
            date posted
          </text>
          <text x={14} y={T + (VH - T - B) / 2} textAnchor="middle" fontSize="11" fill="currentColor" className="text-zinc-500" transform={`rotate(-90 14 ${T + (VH - T - B) / 2})`}>
            % of usual
          </text>
          {shown.map((l, si) => (
            <g key={l.key}>
              <polyline points={l.pts.map((p) => `${X(p.t)},${Y(p.rel)}`).join(" ")} fill="none" stroke={l.color} strokeWidth={2} strokeDasharray={l.dash} strokeLinejoin="round" />
              {l.pts.map((p, i) => (
                <g key={i}>
                  <circle cx={X(p.t)} cy={Y(p.rel)} r={p.sp ? 6 : 4} fill={p.sp ? "var(--panel)" : l.color} stroke={l.color} strokeWidth={2} />
                  <circle cx={X(p.t)} cy={Y(p.rel)} r={11} fill="transparent" onMouseEnter={() => setHover({ s: si, i })} />
                </g>
              ))}
              <text x={X(l.pts[l.pts.length - 1].t) + 10} y={Y(l.pts[l.pts.length - 1].rel) + 4} fontSize="11" fontWeight={600} fill="currentColor" className="text-zinc-300">
                {l.key === "youtube" ? "YouTube" : "Instagram"}
              </text>
            </g>
          ))}
        </svg>
        {hl && hp && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 rounded-md border border-line bg-background/95 px-2.5 py-1.5 text-[11px] shadow-lg"
            style={{ left: `${(X(hp.t) / VW) * 100}%`, top: `${(Y(hp.rel) / VH) * 100}%`, transform: "translate(-50%, 14px)" }}
          >
            <div className="font-medium text-zinc-100">
              {hl.key === "youtube" ? "YouTube" : "Instagram"} · {date(hp.t)}
              {hp.sp ? " · sponsored" : ""}
            </div>
            <div className="text-zinc-400">
              {hp.n.toLocaleString("en-IN")} {hl.key === "youtube" ? "views" : "likes"} · {Math.round(hp.rel)}% of usual
            </div>
          </div>
        )}
      </div>
      <p className="mt-1 text-[11px] text-zinc-500">
        Last {WINDOW_DAYS} days. Each point is one post; 100% is this creator&apos;s usual on that platform, so the two lines are comparable. Open rings are sponsored posts. Latest post: {latest.join(", ")}.
      </p>
    </div>
  );
}
