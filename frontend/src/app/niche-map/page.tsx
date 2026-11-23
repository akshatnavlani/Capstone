"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import Avatar from "@/components/Avatar";
import Icon from "@/components/Icon";
import { postRecommendations } from "@/lib/api";

// Niche Map (22 Nov 2026, idea 3 of 3 Nov; made friendlier 23 Nov): every creator the model knows, placed by what their
// content looks and sounds like (CLIP thumbnail + BERT text vectors, PCA to 2D; data from scripts/export_niche_map.py ->
// /niche_map.json). Niches show as glowing islands; a product is placed among the creators whose content fits it best
// (fit-weighted centre of its top matches by the real creator_feature_score), and the map zooms to that neighbourhood.

type Point = { creator_id: string; name: string; category: string; niche: string; subscribers: number | null; x: number; y: number };
type MapData = { source: string; creators: number; variance_shown: number[]; points: Point[] };
type Box = { x: number; y: number; w: number; h: number };
type Match = { p: Point; fit: number };

// Categorical palette, dark-surface steps, fixed order (validated: dataviz validate_palette.js, surface #101820, all pass).
const NICHES = [
  { name: "Gym and bodybuilding", short: "Gym", icon: "dumbbell", color: "#3987e5" },
  { name: "Nutrition and health", short: "Nutrition", icon: "leaf", color: "#d95926" },
  { name: "Yoga and wellness", short: "Yoga", icon: "yoga", color: "#199e70" },
  { name: "Sports and athletes", short: "Sports", icon: "bat", color: "#c98500" },
  { name: "Running and endurance", short: "Running", icon: "run", color: "#d55181" },
  { name: "Lifestyle and other", short: "Lifestyle", icon: "sparkle", color: "#0ca30c" },
];
const BY_NICHE = Object.fromEntries(NICHES.map((n) => [n.name, n]));
const BRIEFS = [
  { label: "Fitness and gym", icon: "dumbbell", value: "fitness gym workout" },
  { label: "Protein and supplements", icon: "shake", value: "protein supplement whey nutrition" },
  { label: "Yoga and wellness", icon: "yoga", value: "yoga meditation wellness" },
  { label: "Running shoes", icon: "shoe", value: "shoes running sneakers footwear marathon" },
  { label: "Healthy food", icon: "leaf", value: "healthy food nutrition diet protein recipe" },
];
const W = 1000, H = 620, PAD = 36;
const FULL: Box = { x: 0, y: 0, w: W, h: H };
const sx = (x: number) => PAD + x * (W - 2 * PAD);
const sy = (y: number) => H - PAD - y * (H - 2 * PAD);
const subs = (n: number | null) => (n == null ? "" : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M subscribers` : n >= 1e3 ? `${Math.round(n / 1e3)}K subscribers` : `${n} subscribers`);
const TOP = 8;

/** The smallest box with the map's shape that holds these points, with some margin. */
function fitBox(xs: number[], ys: number[], margin = 60): Box {
  const x0 = Math.min(...xs) - margin, x1 = Math.max(...xs) + margin, y0 = Math.min(...ys) - margin, y1 = Math.max(...ys) + margin;
  let w = Math.max(x1 - x0, 260), h = Math.max(y1 - y0, 260 * (H / W));
  if (w / h > W / H) h = w * (H / W);
  else w = h * (W / H);
  return { x: (x0 + x1) / 2 - w / 2, y: (y0 + y1) / 2 - h / 2, w, h };
}

export default function NicheMapPage() {
  const [data, setData] = useState<MapData | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<string | null>(null);
  const [brief, setBrief] = useState<string | null>(null);
  const [placing, setPlacing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [vb, setVb] = useState<Box>(FULL);
  const vbRef = useRef<Box>(FULL);
  const anim = useRef(0);

  useEffect(() => {
    fetch("/niche_map.json")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setData)
      .catch(() => setLoadError(true));
  }, []);

  function zoomTo(t: Box) {
    cancelAnimationFrame(anim.current);
    const from = { ...vbRef.current };
    let t0 = -1;
    const step = (now: number) => {
      if (t0 < 0) t0 = now;
      const k = Math.min(1, (now - t0) / 750);
      const e = 1 - Math.pow(1 - k, 3);
      const b = { x: from.x + (t.x - from.x) * e, y: from.y + (t.y - from.y) * e, w: from.w + (t.w - from.w) * e, h: from.h + (t.h - from.h) * e };
      vbRef.current = b;
      setVb(b);
      if (k < 1) anim.current = requestAnimationFrame(step);
    };
    anim.current = requestAnimationFrame(step);
  }

  const byId = useMemo(() => new Map((data?.points ?? []).map((p) => [p.creator_id, p])), [data]);
  const islands = useMemo(() => {
    const med = (a: number[]) => [...a].sort((p, q) => p - q)[Math.floor(a.length / 2)];
    return NICHES.map((n) => {
      const ps = (data?.points ?? []).filter((p) => p.niche === n.name);
      return { ...n, count: ps.length, cx: ps.length ? med(ps.map((p) => sx(p.x))) : 0, cy: ps.length ? med(ps.map((p) => sy(p.y))) : 0, ps };
    });
  }, [data]);

  // Niches overlap on the map (similar-looking content across keyword niches), so their centres bunch together. Labels are
  // pushed apart until none overlap, each with a thin line back to its niche's true centre.
  const labels = useMemo(() => {
    const L = islands.filter((s) => s.count).map((s, i) => ({ name: s.name, x: s.cx + (i % 2 ? 1 : -1), y: s.cy, ax: s.cx, ay: s.cy }));
    const LW = 136, LH = 42;
    for (let it = 0; it < 200; it++) {
      for (let i = 0; i < L.length; i++)
        for (let j = i + 1; j < L.length; j++) {
          const dx = L[j].x - L[i].x, dy = L[j].y - L[i].y;
          const ox = LW - Math.abs(dx), oy = LH - Math.abs(dy);
          if (ox > 0 && oy > 0) {
            if (ox / LW < oy / LH) {
              const s = ((dx >= 0 ? 1 : -1) * ox) / 2;
              L[i].x -= s;
              L[j].x += s;
            } else {
              const s = ((dy >= 0 ? 1 : -1) * oy) / 2;
              L[i].y -= s;
              L[j].y += s;
            }
          }
        }
      for (const l of L) {
        l.x = Math.max(LW / 2 + 8, Math.min(W - LW / 2 - 8, l.x));
        l.y = Math.max(LH / 2 + 8, Math.min(H - LH / 2 - 8, l.y));
      }
    }
    return new Map(L.map((l) => [l.name, l]));
  }, [islands]);
  const [focus, setFocus] = useState<string | null>(null);
  // Zoom target for a niche: where most of its creators sit (the 60% closest to its centre), not its far-flung edges.
  const nicheBox = (s: (typeof islands)[number]) => {
    const near = [...s.ps].sort((a, b) => Math.hypot(sx(a.x) - s.cx, sy(a.y) - s.cy) - Math.hypot(sx(b.x) - s.cx, sy(b.y) - s.cy)).slice(0, Math.max(3, Math.ceil(s.ps.length * 0.6)));
    return fitBox(near.map((p) => sx(p.x)), near.map((p) => sy(p.y)));
  };

  const briefXY = useMemo(() => {
    if (!matches?.length) return null;
    const w = matches.reduce((s, m) => s + m.fit, 0) || 1;
    return { x: sx(matches.reduce((s, m) => s + m.p.x * m.fit, 0) / w), y: sy(matches.reduce((s, m) => s + m.p.y * m.fit, 0) / w) };
  }, [matches]);

  async function place(value: string) {
    setBrief(value);
    setPlacing(true);
    setError(null);
    setMatches(null);
    zoomTo(FULL);
    try {
      const res = await postRecommendations({ product_category: value, budget: 500000, max_results: 50 }); // backend limit (schemas.py: le=50)
      const onMap = res.results
        .filter((r) => byId.has(r.creator_id))
        .map((r) => ({ p: byId.get(r.creator_id)!, fit: r.score_breakdown.creator_feature_score }))
        .sort((a, b) => b.fit - a.fit)
        .slice(0, TOP);
      setMatches(onMap);
      if (onMap.length) {
        // After the pin lands, fly in to the neighbourhood.
        setTimeout(() => zoomTo(fitBox(onMap.map((m) => sx(m.p.x)), onMap.map((m) => sy(m.p.y)), 90)), 1400);
      }
    } catch {
      setError("Couldn't reach the backend at " + (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000") + ".");
    } finally {
      setPlacing(false);
    }
  }

  const matchIds = new Set(matches?.map((m) => m.p.creator_id) ?? []);
  const toggle = (n: string) =>
    setHidden((h) => {
      const s = new Set(h);
      if (s.has(n)) s.delete(n);
      else s.add(n);
      return s;
    });
  const k = vb.w / W; // keeps dots, labels and the pin the same size on screen while zooming
  const pct = (x: number, y: number) => ({ left: `${((x - vb.x) / vb.w) * 100}%`, top: `${((y - vb.y) / vb.h) * 100}%` });
  const zoomed = vb.w < W - 1;

  const mix = useMemo(() => {
    if (!matches?.length) return null;
    const c: Record<string, number> = {};
    for (const m of matches) c[m.p.niche] = (c[m.p.niche] ?? 0) + 1;
    const [name, n] = Object.entries(c).sort((a, b) => b[1] - a[1])[0];
    return { niche: BY_NICHE[name], n, of: matches.length };
  }, [matches]);
  const hp = hover ? byId.get(hover) : undefined;
  const briefLabel = BRIEFS.find((b) => b.value === brief);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-5 px-6 py-12">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-signal">Real data · AI content map</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
          Niche Map
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-zinc-400">The creator market as a map: creators who make similar content live close together.</p>
      </header>

      <ol className="grid gap-2 sm:grid-cols-3">
        {[
          ["1", "Pick your product"],
          ["2", "Watch your pin land on the map"],
          ["3", "Meet the creators in your neighbourhood"],
        ].map(([n, t], i) => {
          const done = (i === 0 && brief) || (i > 0 && matches);
          return (
            <li key={n} className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition-colors ${done ? "border-signal/50 text-zinc-100" : "border-line text-zinc-400"}`}>
              <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-bold ${done ? "bg-signal text-background" : "bg-line text-zinc-300"}`}>{done ? "✓" : n}</span>
              {t}
            </li>
          );
        })}
      </ol>

      <section className="flex flex-wrap gap-2">
        {BRIEFS.map((b) => (
          <button
            key={b.value}
            onClick={() => place(b.value)}
            disabled={placing || !data}
            className={`flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition-all hover:-translate-y-0.5 disabled:opacity-50 ${
              brief === b.value ? "border-accent bg-accent text-background shadow-[0_0_18px_rgba(245,184,61,0.35)]" : "border-line bg-panel text-zinc-200 hover:border-accent"
            }`}
          >
            <span aria-hidden>
              <Icon name={b.icon} size={18} />
            </span>
            {b.label}
          </button>
        ))}
        {error && <p className="w-full text-sm text-red-400">{error}</p>}
      </section>

      {loadError && <p className="text-sm text-red-400">The map data (/niche_map.json) could not be loaded.</p>}

      {data && (
        <section className="flex flex-col gap-3">
          <div className="relative overflow-hidden rounded-2xl border border-line bg-[#0b131a]">
            <svg
              viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
              className="block h-auto w-full"
              role="img"
              aria-label={`Map of ${data.creators} creators by content similarity`}
              onMouseLeave={() => setHover(null)}
            >
              <defs>
                <filter id="nm-blur" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="22" />
                </filter>
              </defs>

              {/* glow: where creators are busiest, or the chosen niche's own area in its colour */}
              <g filter="url(#nm-blur)">
                {data.points
                  .filter((p) => !hidden.has(p.niche) && (!focus || p.niche === focus))
                  .map((p) => (
                    <circle
                      key={`g${p.creator_id}`}
                      cx={sx(p.x)}
                      cy={sy(p.y)}
                      r={28}
                      fill={focus ? BY_NICHE[p.niche]?.color : "#35d6c0"}
                      fillOpacity={matches ? 0.05 : focus ? 0.26 : 0.08}
                    />
                  ))}
              </g>

              {matches &&
                briefXY &&
                matches.map((m, i) => (
                  <line
                    key={`l${m.p.creator_id}`}
                    x1={briefXY.x}
                    y1={briefXY.y}
                    x2={sx(m.p.x)}
                    y2={sy(m.p.y)}
                    pathLength={1}
                    stroke="#f5b83d"
                    strokeOpacity={0.6}
                    strokeWidth={1.8 * k}
                    className="lm-draw"
                    style={{ animationDelay: `${700 + i * 90}ms` }}
                  />
                ))}

              {data.points
                .filter((p) => !hidden.has(p.niche))
                .map((p) => {
                  const isMatch = matchIds.has(p.creator_id);
                  const dim = (matches && !isMatch) || (!matches && focus && p.niche !== focus);
                  const c = BY_NICHE[p.niche]?.color ?? "#63768a";
                  return (
                    <circle
                      key={p.creator_id}
                      cx={sx(p.x)}
                      cy={sy(p.y)}
                      r={(hover === p.creator_id ? 8 : 5) * k}
                      fill={c}
                      fillOpacity={dim ? 0.2 : 0.95}
                      stroke="#0b131a"
                      strokeWidth={1.5 * k}
                      className="lm-dot"
                      style={{ animationDelay: `${Math.round(Math.hypot(p.x - 0.5, p.y - 0.5) * 1600)}ms`, cursor: "pointer", transition: "fill-opacity 500ms" }}
                      onMouseEnter={() => setHover(p.creator_id)}
                    />
                  );
                })}

              {/* niche labels: hover to light up that niche, click to zoom to where most of its creators are */}
              {!matches &&
                islands
                  .filter((s) => s.count && !hidden.has(s.name))
                  .map((s) => {
                    const l = labels.get(s.name);
                    if (!l) return null;
                    // Label positions were spread at full-map size; when zoomed in they move with the map around the niche centre.
                    const lx = l.ax + (l.x - l.ax) * k, ly = l.ay + (l.y - l.ay) * k;
                    const on = focus === s.name;
                    return (
                      <g
                        key={s.name}
                        style={{ cursor: "pointer", opacity: focus && !on ? 0.45 : 1, transition: "opacity 250ms" }}
                        onMouseEnter={() => setFocus(s.name)}
                        onMouseLeave={() => setFocus(null)}
                        onClick={() => zoomTo(nicheBox(s))}
                        className="lm-fade"
                      >
                        <line x1={l.ax} y1={l.ay} x2={lx} y2={ly} stroke={s.color} strokeWidth={1.5 * k} strokeOpacity={0.8} />
                        <circle cx={l.ax} cy={l.ay} r={4 * k} fill={s.color} stroke="#0b131a" strokeWidth={1.5 * k} />
                        <g transform={`translate(${lx} ${ly}) scale(${k})`}>
                          <rect x={-64} y={-18} width={128} height={36} rx={18} fill={on ? s.color : "#0b131a"} fillOpacity={on ? 0.95 : 0.88} stroke={s.color} strokeWidth={2} />
                          <text x={0} y={5} textAnchor="middle" fontSize="14" fontWeight={600} fill={on ? "#0b131a" : "#f2f6fa"}>
                            {s.short} · {s.count}
                          </text>
                        </g>
                      </g>
                    );
                  })}

              {briefXY && (
                <g transform={`translate(${briefXY.x} ${briefXY.y}) scale(${k})`} style={{ pointerEvents: "none" }}>
                  {[0, 1, 2].map((i) => (
                    <circle key={i} r={14} fill="none" stroke="#f5b83d" strokeWidth={2} className="nm-ripple" style={{ animationDelay: `${600 + i * 600}ms` }} />
                  ))}
                  <g className="nm-drop">
                    <path d="M0 0 C -14 -18 -16 -26 -16 -32 A 16 16 0 1 1 16 -32 C 16 -26 14 -18 0 0 Z" fill="#f5b83d" stroke="#0b131a" strokeWidth={2} />
                    <g style={{ color: "#0b131a" }}>
                      <Icon name={briefLabel?.icon ?? "star"} x={-9} y={-41} size={18} strokeWidth={2.2} />
                    </g>
                  </g>
                </g>
              )}
            </svg>

            {/* photos of the matched creators, pinned to their dots */}
            {matches && (
              <div className="pointer-events-none absolute inset-0">
                {matches.map((m, i) => {
                  const big = i < 3;
                  return (
                    <div
                      key={m.p.creator_id}
                      className="pointer-events-auto absolute"
                      style={{ ...pct(sx(m.p.x), sy(m.p.y)), transform: "translate(-50%, -50%)", zIndex: big ? 3 : 2 }}
                      onMouseEnter={() => setHover(m.p.creator_id)}
                      onMouseLeave={() => setHover(null)}
                    >
                      <span className="lm-photo block rounded-full" style={{ animationDelay: `${1000 + i * 120}ms`, boxShadow: `0 0 0 3px ${big ? "#f5b83d" : BY_NICHE[m.p.niche]?.color}${big ? ", 0 0 18px rgba(245,184,61,0.55)" : ""}` }}>
                        <Avatar creatorId={m.p.creator_id} name={m.p.name} size={big ? 42 : 30} />
                      </span>
                      {big && (
                        <span className="lm-fade absolute left-1/2 top-full mt-1 -translate-x-1/2 whitespace-nowrap rounded-md bg-background/85 px-1.5 py-0.5 text-[11px] font-semibold text-zinc-50" style={{ animationDelay: `${1300 + i * 120}ms` }}>
                          {m.p.name}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* hover card */}
            {hp && (
              <div className="pointer-events-none absolute z-10 flex items-center gap-3 rounded-xl border border-line bg-background/95 p-2.5 pr-4 shadow-xl" style={{ ...pct(sx(hp.x), sy(hp.y)), transform: "translate(-50%, calc(-100% - 22px))" }}>
                <Avatar creatorId={hp.creator_id} name={hp.name} size={40} />
                <div className="text-xs">
                  <div className="font-semibold text-zinc-50">{hp.name}</div>
                  <div className="mt-0.5 text-zinc-400">
                    <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: BY_NICHE[hp.niche]?.color }} />
                    {hp.niche}
                  </div>
                  {hp.subscribers != null && <div className="text-zinc-500">{subs(hp.subscribers)}</div>}
                </div>
              </div>
            )}

            {/* searching: a radar sweeps while the backend scores every creator (about 20 s) */}
            {placing && (
              <div className="absolute inset-0 grid place-items-center bg-[#0b131a]/40">
                <div className="flex flex-col items-center gap-3">
                  <div className="relative h-40 w-40 rounded-full border border-signal/40">
                    <div className="nm-radar absolute inset-0 rounded-full" />
                    <div className="absolute inset-[30%] rounded-full border border-signal/30" />
                    <span className="absolute inset-0 grid place-items-center text-signal">
                      <Icon name={briefLabel?.icon ?? "star"} size={36} />
                    </span>
                  </div>
                  <p className="rounded-full bg-background/85 px-4 py-1.5 text-sm text-zinc-200">Finding where {briefLabel?.label.toLowerCase()} fits… (about 20 seconds)</p>
                </div>
              </div>
            )}

            {zoomed && (
              <button onClick={() => zoomTo(FULL)} className="absolute right-3 top-3 rounded-full border border-line bg-background/90 px-3 py-1.5 text-xs text-zinc-200 hover:border-accent hover:text-accent">
                ⤢ Whole map
              </button>
            )}
            {!matches && !placing && !zoomed && (
              <p className="pointer-events-none absolute bottom-3 left-3 rounded-full bg-background/80 px-3 py-1 text-[11px] text-zinc-400">Tip: hover a niche to light it up, click it to zoom in</p>
            )}
          </div>

          <ul className="flex flex-wrap gap-2" aria-label="Niches (click to show or hide)">
            {islands.map((n) => (
              <li key={n.name}>
                <button
                  onClick={() => toggle(n.name)}
                  onMouseEnter={() => !hidden.has(n.name) && setFocus(n.name)}
                  onMouseLeave={() => setFocus(null)}
                  aria-pressed={!hidden.has(n.name)}
                  className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs transition-colors ${hidden.has(n.name) ? "border-line text-zinc-600" : "border-line text-zinc-200 hover:border-zinc-500"}`}
                >
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: hidden.has(n.name) ? "transparent" : n.color, border: `2px solid ${n.color}` }} />
                  {n.short} <span className="text-zinc-500">{n.count}</span>
                </button>
              </li>
            ))}
          </ul>

          {matches && mix && (
            <div className="lm-rise flex flex-col gap-3 rounded-2xl border border-line bg-panel p-5">
              <p className="text-base text-zinc-100">
                <Icon name="pin" size={18} className="mr-1.5 inline -translate-y-0.5 text-accent" />
                Your product lives mostly in <span className="font-semibold" style={{ color: mix.niche?.color }}>{mix.niche?.short}</span>{" "}
                <span className="text-zinc-400">
                  ({mix.n} of your {mix.of} closest creators)
                </span>
              </p>
              <h2 className="text-sm font-semibold text-zinc-300">Your neighbours</h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {matches.map((m, i) => (
                  <Link
                    key={m.p.creator_id}
                    href={`/passport?creator=${m.p.creator_id}`}
                    onMouseEnter={() => setHover(m.p.creator_id)}
                    onMouseLeave={() => setHover(null)}
                    className={`lm-rise flex flex-col items-center gap-2 rounded-xl border bg-background/60 p-3 text-center transition-all hover:-translate-y-1 ${hover === m.p.creator_id ? "border-accent" : "border-line"}`}
                    style={{ animationDelay: `${i * 70}ms` }}
                  >
                    <Avatar creatorId={m.p.creator_id} name={m.p.name} size={52} />
                    <span className="line-clamp-2 text-sm font-medium text-zinc-100">{m.p.name}</span>
                    <span className="text-[11px] text-zinc-400">
                      <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: BY_NICHE[m.p.niche]?.color }} />
                      {BY_NICHE[m.p.niche]?.short}
                    </span>
                    <span className="w-full">
                      <span className="block h-1.5 overflow-hidden rounded-full bg-line">
                        <span className="lm-grow block h-full rounded-full bg-accent" style={{ width: `${m.fit * 100}%` }} />
                      </span>
                      <span className="mt-1 block text-[10px] text-zinc-500">content match {Math.round(m.fit * 100)}/100</span>
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          <details className="text-xs text-zinc-500">
            <summary className="cursor-pointer">How is this map made?</summary>
            <p className="mt-1">
              {data.creators} creators · position = CLIP (thumbnails) + BERT (titles, captions), reduced with PCA to two axes that show{" "}
              {Math.round((data.variance_shown[0] + data.variance_shown[1]) * 100)}% of the variation · colour = niche by channel keywords · your pin sits at the
              fit-weighted centre of your {TOP} best-fitting creators on the map.
            </p>
          </details>
        </section>
      )}
    </main>
  );
}
