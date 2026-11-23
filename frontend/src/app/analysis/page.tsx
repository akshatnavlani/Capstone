"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import Avatar from "@/components/Avatar";
import Icon from "@/components/Icon";
import type { BrandRecommendationResponse, InfluencerRecommendation } from "@/types";

// Analysis for brands (23 Nov 2026): only the findings a brand can act on, as pictures. Numbers come from
// /brand_insights.json (scripts/export_brand_insights.py copies them from the result files) and, for the last section,
// from the brand's own last brief. The full team analysis (S1-S10) is at /research/analysis.

type Insights = {
  cross_platform: { creators: number; lag_days: [number, number]; instagram_to_youtube: { p: number }; youtube_to_instagram: { p: number } };
  stronger_platform: {
    matched_posts: number;
    counts: { Instagram: number; YouTube: number; balanced: number; not_enough: number };
    creators: { creator_id: string; name: string; stronger: "Instagram" | "YouTube" | "balanced" }[];
  };
  promotion: {
    sponsored_videos: number;
    share_disclosed: number;
    buying_ratio: number;
    buying_ratio_ci95: [number, number];
    placebo_ratio: number;
    response_creators: number;
    creators_more: number;
    creators_same: number;
    creators_fewer: number;
  };
  ad_load: { creators: number; videos: number; views_slope: number; views_ci95: [number, number] };
};

const YT = "#d95926", IG = "#3987e5", EVEN = "#8497aa";

function useInView<T extends Element>() {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Seen once its top has come into view, including when a fast scroll or a jump goes straight past it.
    const check = () => {
      if (el.getBoundingClientRect().top < window.innerHeight * 0.92) {
        setSeen(true);
        stop();
      }
    };
    const io = new IntersectionObserver(check, { threshold: [0, 0.08] });
    const stop = () => {
      io.disconnect();
      window.removeEventListener("scroll", check, true);
    };
    io.observe(el);
    window.addEventListener("scroll", check, { capture: true, passive: true });
    return stop;
  }, []);
  return [ref, seen] as const;
}

function useCountUp(target: number, run: boolean, ms = 1000) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!run) return;
    let id = 0;
    const t0 = performance.now();
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      setV(target * (1 - Math.pow(1 - k, 3)));
      if (k < 1) id = requestAnimationFrame(step);
    };
    id = requestAnimationFrame(step);
    return () => cancelAnimationFrame(id);
  }, [target, run, ms]);
  return v;
}

function Section({ n, icon, title, children }: { n: number; icon: string; title: string; children: (seen: boolean) => React.ReactNode }) {
  const [ref, seen] = useInView<HTMLElement>();
  return (
    <section ref={ref} className={`rounded-2xl border border-line bg-panel p-5 transition-all duration-700 sm:p-6 ${seen ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"}`}>
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-full bg-accent-soft text-accent" aria-hidden>
          <Icon name={icon} size={20} />
        </span>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-signal">Insight {n}</div>
          <h2 className="text-xl font-semibold tracking-tight text-zinc-50">{title}</h2>
        </div>
      </div>
      <div className="mt-4">{children(seen)}</div>
    </section>
  );
}

function Takeaway({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-4 flex gap-2 rounded-lg border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-zinc-100">
      <Icon name="bulb" size={18} className="mt-0.5 shrink-0 text-accent" />
      <span>{children}</span>
    </p>
  );
}

function Small({ children }: { children: React.ReactNode }) {
  return <p className="mt-2 text-[11px] text-zinc-500">{children}</p>;
}

// ---- 1. Cross-platform timing ----
function CrossPlatform({ d, seen }: { d: Insights["cross_platform"]; seen: boolean }) {
  const n = useCountUp(d.creators, seen);
  const dayX = (k: number) => 200 + k * 130;
  return (
    <>
      <svg viewBox="0 0 800 210" className="block h-auto w-full" role="img" aria-label="An Instagram post is followed by more YouTube comments over the next 1 to 3 days">
        <defs>
          <linearGradient id="an-ig" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="#3987e5" />
            <stop offset="1" stopColor="#6aa9ff" />
          </linearGradient>
          <linearGradient id="an-yt" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="#d95926" />
            <stop offset="1" stopColor="#f08a5d" />
          </linearGradient>
        </defs>
        <rect x={dayX(1) - 40} y={40} width={dayX(3) - dayX(1) + 80} height={120} rx={14} fill="#35d6c0" fillOpacity={0.07} stroke="#35d6c0" strokeOpacity={0.35} strokeDasharray="4 4" />
        <text x={(dayX(1) + dayX(3)) / 2} y={32} textAnchor="middle" fontSize="13" fontWeight={600} fill="#35d6c0">
          within 1 to 3 days
        </text>
        <line x1={150} x2={660} y1={100} y2={100} stroke="#2e3c4a" strokeWidth={3} strokeLinecap="round" />
        {[0, 1, 2, 3].map((k) => (
          <g key={k}>
            <circle cx={dayX(k)} cy={100} r={6} fill={k === 0 ? IG : "#cbd6e1"} />
            <text x={dayX(k)} y={185} textAnchor="middle" fontSize="12" fill="#8497aa">
              {k === 0 ? "Day 0" : `Day ${k}`}
            </text>
          </g>
        ))}
        {seen &&
          [0, 1, 2, 3, 4, 5].map((i) => (
            <circle
              key={i}
              r={5}
              fill="#f5b83d"
              className="lm-pulse"
              style={{ "--x0": "150px", "--y0": "100px", "--x1": "660px", "--y1": "100px", animationDelay: `${i * 0.35}s`, animationDuration: "2.2s" } as React.CSSProperties}
            />
          ))}
        {seen &&
          [1, 2, 3].map((k) => (
            <g key={k} className="lm-photo" style={{ animationDelay: `${600 + k * 350}ms`, transformBox: "fill-box", transformOrigin: "center" }}>
              <rect x={dayX(k) - 22} y={56} width={44} height={26} rx={8} fill="#f2f6fa" />
              <path d={`M ${dayX(k) - 4} 82 l 4 8 l 4 -8 z`} fill="#f2f6fa" />
              <g style={{ color: "#0b131a" }}>
                <Icon name="chat" x={dayX(k) - 8} y={61} size={16} />
              </g>
            </g>
          ))}
        <g>
          <rect x={10} y={62} width={140} height={76} rx={14} fill="url(#an-ig)" />
          <text x={80} y={94} textAnchor="middle" fontSize="15" fontWeight={700} fill="#0a1016">
            Instagram
          </text>
          <text x={80} y={114} textAnchor="middle" fontSize="12" fill="#0a1016">
            new post
          </text>
        </g>
        <g>
          <rect x={660} y={62} width={130} height={76} rx={14} fill="url(#an-yt)" />
          <text x={725} y={94} textAnchor="middle" fontSize="15" fontWeight={700} fill="#0a1016">
            YouTube
          </text>
          <text x={725} y={114} textAnchor="middle" fontSize="12" fill="#0a1016">
            more comments
          </text>
        </g>
      </svg>
      <div className="mt-2 grid gap-3 sm:grid-cols-3">
        <Stat big={`${Math.round(n)}`} small="creators checked, YouTube and Instagram" />
        <Stat big={`${d.lag_days[0]}–${d.lag_days[1]} days`} small="when the YouTube comments pick up" />
        <Stat big="✓ passed" small={`a strict check against chance (p = ${d.instagram_to_youtube.p})`} />
      </div>
      <Takeaway>
        Plan Instagram and YouTube together. When a creator posts on Instagram, comments on their YouTube videos tend to pick up over the next 1 to 3 days, and it
        works the other way round too.
      </Takeaway>
      <Small>This shows what comes next, not proof of cause: fans may simply follow creators on both platforms.</Small>
    </>
  );
}

function Stat({ big, small }: { big: string; small: string }) {
  return (
    <div className="rounded-xl border border-line bg-background/60 p-3">
      <div className="font-mono text-2xl font-semibold text-zinc-50">{big}</div>
      <div className="text-xs text-zinc-400">{small}</div>
    </div>
  );
}

// ---- 2. Stronger platform per creator ----
const GROUP_ORDER = { Instagram: 0, YouTube: 1, balanced: 2 } as const;
function StrongerPlatform({ d, seen }: { d: Insights["stronger_platform"]; seen: boolean }) {
  const [hover, setHover] = useState<string | null>(null);
  const dots = useMemo(() => [...d.creators].sort((a, b) => GROUP_ORDER[a.stronger] - GROUP_ORDER[b.stronger] || a.name.localeCompare(b.name)), [d.creators]);
  const total = dots.length;
  const groups = [
    { key: "Instagram", label: "Stronger on Instagram", color: IG, n: d.counts.Instagram },
    { key: "YouTube", label: "Stronger on YouTube", color: YT, n: d.counts.YouTube },
    { key: "balanced", label: "About the same", color: EVEN, n: d.counts.balanced },
  ];
  const h = dots.find((c) => c.creator_id === hover);
  return (
    <>
      <p className="text-sm text-zinc-400">Each dot is one creator. We compared posts they put on both platforms within 24 hours, each against their own usual.</p>
      <div className="mt-4 grid gap-5 md:grid-cols-[1fr_260px]">
        <div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(26px,1fr))] gap-1.5" onMouseLeave={() => setHover(null)}>
            {dots.map((c, i) => (
              <button
                key={c.creator_id}
                onMouseEnter={() => setHover(c.creator_id)}
                onFocus={() => setHover(c.creator_id)}
                aria-label={`${c.name}: ${c.stronger === "balanced" ? "about the same on both" : `stronger on ${c.stronger}`}`}
                className={`aspect-square rounded-full transition-transform hover:scale-125 ${seen ? "lm-photo" : "opacity-0"}`}
                style={{ background: c.stronger === "Instagram" ? IG : c.stronger === "YouTube" ? YT : EVEN, animationDelay: `${i * 25}ms`, outline: hover === c.creator_id ? "2px solid #f2f6fa" : "none" }}
              />
            ))}
          </div>
          <div className="mt-3 flex h-12 items-center gap-3 text-sm">
            {h ? (
              <>
                <Avatar creatorId={h.creator_id} name={h.name} size={36} />
                <span className="text-zinc-100">{h.name}</span>
                <span className="text-zinc-400">{h.stronger === "balanced" ? "about the same on both" : `stronger on ${h.stronger}`}</span>
              </>
            ) : (
              <span className="text-xs text-zinc-500">Hover a dot to see the creator</span>
            )}
          </div>
        </div>
        <div className="flex flex-col gap-3">
          {groups.map((g) => (
            <GroupBar key={g.key} label={g.label} color={g.color} n={g.n} total={total} run={seen} />
          ))}
        </div>
      </div>
      <Takeaway>
        Most creators do better on Instagram ({d.counts.Instagram} of {total}), but {d.counts.YouTube} do better on YouTube. Don&apos;t assume: check each
        creator&apos;s stronger platform before you book.
      </Takeaway>
      <Small>
        {total} creators with enough matched posts ({d.matched_posts.toLocaleString()} posts in all); {d.counts.not_enough} more had too few to tell.
      </Small>
    </>
  );
}

function GroupBar({ label, color, n, total, run }: { label: string; color: string; n: number; total: number; run: boolean }) {
  const v = useCountUp(n, run);
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-zinc-300">{label}</span>
        <span className="font-mono text-lg font-semibold text-zinc-50">{Math.round(v)}</span>
      </div>
      <div className="mt-1 h-2.5 overflow-hidden rounded-full bg-line">
        <div className="h-full rounded-full transition-[width] duration-1000 ease-out" style={{ width: run ? `${(100 * n) / total}%` : "0%", background: color }} />
      </div>
    </div>
  );
}

// ---- 3. Sponsored posts: buying interest and labels ----
function Promotion({ d, seen }: { d: Insights["promotion"]; seen: boolean }) {
  const ratio = useCountUp(d.buying_ratio, seen);
  const pct = useCountUp(d.share_disclosed * 100, seen);
  const R = 52, C = 2 * Math.PI * R;
  const barH = (x: number) => `${(x / 2.4) * 100}%`; // headroom so the label above the taller bar stays inside
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div>
        <h3 className="text-sm font-semibold text-zinc-200">Buying-type comments (&quot;price?&quot;, &quot;where to buy?&quot;)</h3>
        <div className="mt-3 flex h-52 items-end justify-center gap-10 border-b border-line">
          {[
            { label: "Normal video", x: 1, color: "#4a5b6d" },
            { label: "Sponsored video", x: d.buying_ratio, color: "#f5b83d" },
          ].map((b, i) => (
            <div key={b.label} className="relative flex h-full w-24 flex-col items-center justify-end">
              <span className="mb-1 font-mono text-lg font-semibold text-zinc-50">{i === 0 ? "1×" : `${ratio.toFixed(1)}×`}</span>
              <div
                className="w-full rounded-t-lg transition-[height] duration-1000 ease-out"
                style={{ height: seen ? barH(b.x) : "0%", background: b.color, transitionDelay: `${i * 250}ms` }}
              />
              {i === 1 && seen && (
                <>
                  {[0, 1, 2].map((k) => (
                    <span key={k} className="an-float absolute text-accent" style={{ left: `${20 + k * 25}%`, bottom: barH(b.x), animationDelay: `${1.2 + k * 0.7}s` }} aria-hidden>
                      <Icon name="cart" size={18} />
                    </span>
                  ))}
                </>
              )}
            </div>
          ))}
        </div>
        <div className="mt-2 flex justify-center gap-10 text-xs text-zinc-400">
          <span className="w-24 text-center">Normal video</span>
          <span className="w-24 text-center">Sponsored video</span>
        </div>
        <Small>
          Median over {d.response_creators} creators (range {d.buying_ratio_ci95[0]}× to {d.buying_ratio_ci95[1]}×; a fake-label check gives {d.placebo_ratio}×). Per creator:{" "}
          {d.creators_more} more, {d.creators_same} about the same, {d.creators_fewer} fewer.
        </Small>
      </div>
      <div>
        <h3 className="text-sm font-semibold text-zinc-200">Sponsored videos that clearly say &quot;ad&quot;</h3>
        <div className="mt-3 flex items-center gap-5">
          <svg viewBox="0 0 130 130" className="h-40 w-40 shrink-0">
            <g transform="rotate(-90 65 65)">
              <circle cx="65" cy="65" r={R} fill="none" stroke="var(--line)" strokeWidth="14" />
              <circle cx="65" cy="65" r={R} fill="none" stroke="#d55181" strokeWidth="14" strokeLinecap="round" strokeDasharray={`${(pct / 100) * C} ${C}`} />
            </g>
            <text x="65" y="62" textAnchor="middle" fontSize="26" fontWeight={700} fill="#f2f6fa">
              {Math.round(pct)}%
            </text>
            <text x="65" y="82" textAnchor="middle" fontSize="10" fill="#8497aa">
              labelled
            </text>
          </svg>
          <p className="text-sm text-zinc-300">
            Only about <span className="font-semibold text-zinc-50">1 in 6</span> of the {d.sponsored_videos.toLocaleString()} sponsored videos we found clearly says it is an ad.
          </p>
        </div>
      </div>
      <div className="md:col-span-2">
        <Takeaway>
          Sponsored videos draw about {d.buying_ratio}× more buying-type comments, so audiences do respond. Ask your creators to label the post clearly as an ad: Indian
          advertising rules (ASCI) ask for it, and most creators skip it.
        </Takeaway>
        <Small>Buying-type comments are a sign of interest, not sales. YouTube only.</Small>
      </div>
    </div>
  );
}

// ---- 4. Ad load and views ----
function AdLoad({ d, seen }: { d: Insights["ad_load"]; seen: boolean }) {
  const VW = 640, VH = 280, L = 56, R = 20, T = 20, B = 46;
  const ks = [0, 1, 2, 3, 4, 5, 6];
  const y0 = 50, y1 = 125; // wide enough for the whole likely range at 6 ads (about 53% to 111%)
  const X = (k: number) => L + (k / 6) * (VW - L - R);
  const Y = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (VH - T - B);
  const f = (s: number, k: number) => Math.max(y0, Math.min(y1, 100 * Math.exp(s * k)));
  const line = ks.map((k) => `${k === 0 ? "M" : "L"} ${X(k)} ${Y(f(d.views_slope, k))}`).join(" ");
  const band = [...ks.map((k) => `${X(k)},${Y(f(d.views_ci95[1], k))}`), ...[...ks].reverse().map((k) => `${X(k)},${Y(f(d.views_ci95[0], k))}`)].join(" ");
  const per = Math.round(d.views_slope * 1000) / 10;
  return (
    <>
      <svg viewBox={`0 0 ${VW} ${VH}`} className="block h-auto w-full max-w-3xl" role="img" aria-label="Views compared with usual as a creator posts more sponsored videos">
        {[50, 75, 100, 125].map((t) => (
          <g key={t}>
            <line x1={L} x2={VW - R} y1={Y(t)} y2={Y(t)} stroke={t === 100 ? "#4a5b6d" : "#1e2b37"} strokeDasharray={t === 100 ? "5 4" : undefined} />
            <text x={L - 8} y={Y(t) + 4} fontSize="11" textAnchor="end" fill="#63768a">
              {t}%
            </text>
          </g>
        ))}
        {ks.map((k) => (
          <text key={k} x={X(k)} y={VH - B + 18} fontSize="11" textAnchor="middle" fill="#63768a">
            {k}
          </text>
        ))}
        <line x1={L} x2={VW - R} y1={VH - B} y2={VH - B} stroke="#8497aa" strokeWidth={1.5} />
        <line x1={L} x2={L} y1={T} y2={VH - B} stroke="#8497aa" strokeWidth={1.5} />
        <text x={(L + VW - R) / 2} y={VH - 8} fontSize="12" fontWeight={600} textAnchor="middle" fill="#cbd6e1">
          X axis: sponsored videos in the last 30 days
        </text>
        <text x={14} y={(T + VH - B) / 2} fontSize="12" fontWeight={600} textAnchor="middle" fill="#cbd6e1" transform={`rotate(-90 14 ${(T + VH - B) / 2})`}>
          Y axis: views vs usual
        </text>
        <text x={VW - R - 4} y={Y(100) - 6} fontSize="11" textAnchor="end" fill="#8497aa">
          usual views
        </text>
        {seen && (
          <>
            <polygon points={band} fill="#35d6c0" fillOpacity={0.12} className="lm-fade" />
            <path d={line} fill="none" stroke="#35d6c0" strokeWidth={3} strokeLinecap="round" pathLength={1} className="lm-draw" style={{ animationDuration: "1.6s" }} />
          </>
        )}
      </svg>
      <div className="mt-1 flex flex-wrap gap-4 text-[11px] text-zinc-400">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-5 rounded bg-signal" /> typical creator
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-5 rounded-sm bg-signal/20" /> likely range
        </span>
      </div>
      <Takeaway>
        No clear drop. Views dip by about {Math.abs(per)}% per extra ad, but the likely range still includes no change at all. A creator posting a few more ads is not a red
        flag on its own.
      </Takeaway>
      <Small>
        {d.creators} creators, {d.videos.toLocaleString()} non-sponsored YouTube videos; each creator compared with their own usual.
      </Small>
    </>
  );
}

// ---- 5. Re-rank the last brief by what the brand cares about ----
const WEIGHTS = [
  { key: "value", label: "Value for money", color: "#f5b83d" },
  { key: "mood", label: "Happy audience", color: "#35d6c0" },
  { key: "fit", label: "Content match", color: "#3987e5" },
] as const;
type WKey = (typeof WEIGHTS)[number]["key"];

function part(r: InfluencerRecommendation, k: WKey) {
  const b = r.score_breakdown;
  return k === "value" ? b.value_score ?? 0.5 : k === "mood" ? b.sentiment_risk_score : b.creator_feature_score;
}

function Rerank({ seen }: { seen: boolean }) {
  const raw = useSyncExternalStore(
    () => () => {},
    () => sessionStorage.getItem("recommendationResult"),
    () => null,
  );
  const result = useMemo(() => {
    try {
      return raw ? (JSON.parse(raw) as BrandRecommendationResponse) : null;
    } catch {
      return null;
    }
  }, [raw]);
  const [w, setW] = useState<Record<WKey, number>>({ value: 40, mood: 30, fit: 30 });
  const rows = useMemo(() => {
    if (!result) return [];
    const list = result.results.slice(0, 10);
    const base = [...list].sort((a, b) => b.final_score - a.final_score).map((r) => r.creator_id);
    const sum = w.value + w.mood + w.fit || 1;
    const scored = list.map((r) => ({ r, s: (100 * (w.value * part(r, "value") + w.mood * part(r, "mood") + w.fit * part(r, "fit"))) / sum }));
    const order = [...scored].sort((a, b) => b.s - a.s);
    return scored.map((x) => ({ ...x, rank: order.indexOf(x), was: base.indexOf(x.r.creator_id) }));
  }, [result, w]);

  if (!result) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm text-zinc-400">Run a brief first, then come back here to re-rank your creators by what matters most to you.</p>
        <Link href="/brand-input" className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-background">
          Start a brief
        </Link>
      </div>
    );
  }
  const ROW = 46;
  return (
    <>
      <p className="text-sm text-zinc-400">
        Your last brief: <span className="text-zinc-200">&quot;{result.query.product_category}&quot;</span>. Move the sliders and watch your top creators re-order.
      </p>
      <div className="mt-4 grid gap-6 md:grid-cols-[240px_1fr]">
        <div className="flex flex-col gap-4">
          {WEIGHTS.map((x) => (
            <label key={x.key} className="text-xs text-zinc-400">
              <span className="flex justify-between">
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: x.color }} />
                  {x.label}
                </span>
                <span className="font-mono text-zinc-100">{w[x.key]}</span>
              </span>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={w[x.key]}
                onChange={(e) => setW((o) => ({ ...o, [x.key]: Number(e.target.value) }))}
                className="mt-1 w-full"
                style={{ accentColor: x.color }}
              />
            </label>
          ))}
          <button onClick={() => setW({ value: 40, mood: 30, fit: 30 })} className="self-start text-xs text-zinc-500 hover:text-accent">
            ↺ Back to our default (40 · 30 · 30)
          </button>
        </div>
        <div className="relative" style={{ height: rows.length * ROW }}>
          {rows.map(({ r, s, rank, was }) => {
            const moved = was - rank;
            return (
              <div
                key={r.creator_id}
                className="absolute inset-x-0 flex items-center gap-3 rounded-lg px-2 transition-[top] duration-500 ease-out"
                style={{ top: rank * ROW, height: ROW - 6, opacity: seen ? 1 : 0 }}
              >
                <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full font-mono text-xs font-semibold ${rank < 3 ? "bg-accent text-background" : "bg-line text-zinc-300"}`}>{rank + 1}</span>
                <Avatar creatorId={r.creator_id} name={r.name} size={30} />
                <span className="min-w-0 flex-1 truncate text-sm text-zinc-100">{r.name}</span>
                <span className="hidden h-2 w-32 overflow-hidden rounded-full bg-line sm:block">
                  <span className="block h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${s}%` }} />
                </span>
                <span className="w-10 text-right font-mono text-sm text-zinc-50">{s.toFixed(0)}</span>
                <span className={`w-10 text-right text-xs ${moved > 0 ? "text-emerald-400" : moved < 0 ? "text-rose-400" : "text-zinc-600"}`}>
                  {moved > 0 ? `▲${moved}` : moved < 0 ? `▼${-moved}` : "–"}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <Small>Uses the real scores from your last brief. Our recommended mix is 40 · 30 · 30; arrows show the change from that ranking.</Small>
    </>
  );
}

export default function AnalysisPage() {
  const [d, setD] = useState<Insights | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    fetch("/brand_insights.json")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setD)
      .catch(() => setFailed(true));
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-12">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-signal">Analysis · real data</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
          What our data says about working with creators
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-zinc-400">Five things worth knowing before you plan a campaign, from our Indian fitness and wellness creators.</p>
      </header>
      {failed && <p className="text-sm text-red-400">Couldn&apos;t load the insights (/brand_insights.json).</p>}
      {d && (
        <>
          <Section n={1} icon="repeat" title="Post on Instagram, YouTube wakes up">
            {(seen) => <CrossPlatform d={d.cross_platform} seen={seen} />}
          </Section>
          <Section n={2} icon="phone" title="Where is each creator stronger?">
            {(seen) => <StrongerPlatform d={d.stronger_platform} seen={seen} />}
          </Section>
          <Section n={3} icon="cart" title="Do sponsored posts spark buying interest?">
            {(seen) => <Promotion d={d.promotion} seen={seen} />}
          </Section>
          <Section n={4} icon="trend" title="Does posting lots of ads hurt views?">
            {(seen) => <AdLoad d={d.ad_load} seen={seen} />}
          </Section>
          <Section n={5} icon="sliders" title="What matters most to you?">
            {(seen) => <Rerank seen={seen} />}
          </Section>
        </>
      )}
    </main>
  );
}
