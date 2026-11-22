"use client";

import { useEffect, useMemo, useState } from "react";
import { postRecommendations } from "@/lib/api";

// Niche Map (22 Nov 2026, idea 3 of 3 Nov): every creator the model knows, placed by what their content looks and sounds
// like (CLIP thumbnail + BERT text vectors, PCA to 2D; data from scripts/export_niche_map.py -> /niche_map.json).
// A brief is placed among the creators whose content fits it best (fit-weighted centre of its top matches).

type Point = { creator_id: string; name: string; category: string; niche: string; subscribers: number | null; x: number; y: number };
type MapData = { source: string; creators: number; variance_shown: number[]; points: Point[] };

// Categorical palette, dark-surface steps, fixed order (validated: dataviz validate_palette.js, surface #101820, all pass).
const NICHES = [
  { name: "Gym and bodybuilding", color: "#3987e5" },
  { name: "Nutrition and health", color: "#d95926" },
  { name: "Yoga and wellness", color: "#199e70" },
  { name: "Sports and athletes", color: "#c98500" },
  { name: "Running and endurance", color: "#d55181" },
  { name: "Lifestyle and other", color: "#0ca30c" },
];
const COLOR = Object.fromEntries(NICHES.map((n) => [n.name, n.color]));
const BRIEFS = [
  { label: "Fitness and gym", value: "fitness gym workout" },
  { label: "Protein and supplements", value: "protein supplement whey nutrition" },
  { label: "Yoga, meditation and wellness", value: "yoga meditation wellness" },
  { label: "Running and sports shoes", value: "shoes running sneakers footwear marathon" },
  { label: "Healthy food and nutrition", value: "healthy food nutrition diet protein recipe" },
];
const W = 1000, H = 620, PAD = 36;
const sx = (x: number) => PAD + x * (W - 2 * PAD);
const sy = (y: number) => H - PAD - y * (H - 2 * PAD);
const subs = (n: number | null) => (n == null ? "subscribers not available" : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M subscribers` : n >= 1e3 ? `${Math.round(n / 1e3)}K subscribers` : `${n} subscribers`);
const TOP = 8;

export default function NicheMapPage() {
  const [data, setData] = useState<MapData | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<Point | null>(null);
  const [brief, setBrief] = useState(BRIEFS[0].value);
  const [placing, setPlacing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [matches, setMatches] = useState<{ p: Point; fit: number }[] | null>(null);

  useEffect(() => {
    fetch("/niche_map.json")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setData)
      .catch(() => setLoadError(true));
  }, []);

  const byId = useMemo(() => new Map((data?.points ?? []).map((p) => [p.creator_id, p])), [data]);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const p of data?.points ?? []) c[p.niche] = (c[p.niche] ?? 0) + 1;
    return c;
  }, [data]);

  const briefXY = useMemo(() => {
    if (!matches?.length) return null;
    const w = matches.reduce((s, m) => s + m.fit, 0) || 1;
    return { x: matches.reduce((s, m) => s + m.p.x * m.fit, 0) / w, y: matches.reduce((s, m) => s + m.p.y * m.fit, 0) / w };
  }, [matches]);

  async function placeBrief() {
    setPlacing(true);
    setError(null);
    try {
      const res = await postRecommendations({ product_category: brief, budget: 500000, max_results: 50 }); // backend limit (schemas.py: le=50)
      const onMap = res.results
        .filter((r) => byId.has(r.creator_id))
        .map((r) => ({ p: byId.get(r.creator_id)!, fit: r.score_breakdown.creator_feature_score }))
        .sort((a, b) => b.fit - a.fit)
        .slice(0, TOP);
      setMatches(onMap);
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

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-12">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-signal">Real data · AI content map</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
          Niche Map
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-zinc-400">
          Every creator our models know, placed by what their content looks and sounds like. Creators close together post similar
          content. Place a brief to see which part of the market fits it.
        </p>
      </header>

      <section className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-panel p-4">
        <label className="flex flex-col gap-1 text-xs text-zinc-400">
          Brief
          <select value={brief} onChange={(e) => setBrief(e.target.value)} className="rounded-md border border-line bg-background px-3 py-2 text-sm text-zinc-100">
            {BRIEFS.map((b) => (
              <option key={b.value} value={b.value}>
                {b.label}
              </option>
            ))}
          </select>
        </label>
        <button onClick={placeBrief} disabled={placing || !data} className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background disabled:opacity-50">
          {placing ? "Placing…" : "Place brief on the map"}
        </button>
        {matches && (
          <button onClick={() => setMatches(null)} className="rounded-md border border-line px-4 py-2 text-sm text-zinc-300 hover:border-accent hover:text-accent">
            Clear
          </button>
        )}
        {error && <p className="w-full text-sm text-red-400">{error}</p>}
      </section>

      {loadError && <p className="text-sm text-red-400">The map data (/niche_map.json) could not be loaded.</p>}

      {data && (
        <section className="flex flex-col gap-3">
          <ul className="flex flex-wrap gap-2" aria-label="Niches (click to show or hide)">
            {NICHES.map((n) => (
              <li key={n.name}>
                <button
                  onClick={() => toggle(n.name)}
                  aria-pressed={!hidden.has(n.name)}
                  className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs transition-colors ${
                    hidden.has(n.name) ? "border-line text-zinc-600" : "border-line text-zinc-200 hover:border-zinc-500"
                  }`}
                >
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: hidden.has(n.name) ? "transparent" : n.color, border: `2px solid ${n.color}` }} />
                  {n.name} <span className="text-zinc-500">{counts[n.name] ?? 0}</span>
                </button>
              </li>
            ))}
          </ul>

          <div className="relative overflow-hidden rounded-xl border border-line bg-panel">
            <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" aria-label={`Map of ${data.creators} creators by content similarity`}>
              {matches && briefXY &&
                matches.map((m) => (
                  <line key={m.p.creator_id} x1={sx(briefXY.x)} y1={sy(briefXY.y)} x2={sx(m.p.x)} y2={sy(m.p.y)} stroke="var(--accent)" strokeOpacity="0.45" strokeWidth="1.5" strokeDasharray="4 4" />
                ))}
              {data.points
                .filter((p) => !hidden.has(p.niche))
                .map((p) => {
                  const isMatch = matchIds.has(p.creator_id);
                  const dim = matches && !isMatch;
                  return (
                    <g key={p.creator_id}>
                      <circle
                        cx={sx(p.x)}
                        cy={sy(p.y)}
                        r={isMatch ? 8 : 5}
                        fill={COLOR[p.niche] ?? "#63768a"}
                        fillOpacity={dim ? 0.25 : 0.95}
                        stroke={isMatch ? "var(--accent)" : "var(--panel)"}
                        strokeWidth={isMatch ? 2.5 : 2}
                      />
                      <circle cx={sx(p.x)} cy={sy(p.y)} r={11} fill="transparent" onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(null)}>
                        <title>{`${p.name} · ${p.niche}`}</title>
                      </circle>
                    </g>
                  );
                })}
              {matches?.slice(0, 3).map((m) => (
                <text key={m.p.creator_id} x={sx(m.p.x) + 12} y={sy(m.p.y) + 4} fontSize="14" fill="var(--foreground)" style={{ pointerEvents: "none" }}>
                  {m.p.name}
                </text>
              ))}
              {briefXY && (
                <g style={{ pointerEvents: "none" }}>
                  <rect x={sx(briefXY.x) - 9} y={sy(briefXY.y) - 9} width="18" height="18" transform={`rotate(45 ${sx(briefXY.x)} ${sy(briefXY.y)})`} fill="var(--accent)" stroke="var(--panel)" strokeWidth="2" />
                  <text x={sx(briefXY.x)} y={sy(briefXY.y) - 18} textAnchor="middle" fontSize="15" fontWeight="600" fill="var(--accent)">
                    Your brief
                  </text>
                </g>
              )}
            </svg>
            {hover && (
              <div className="pointer-events-none absolute left-3 top-3 rounded-md border border-line bg-background/95 px-3 py-2 text-xs shadow-lg">
                <div className="font-semibold text-zinc-50">{hover.name}</div>
                <div className="mt-0.5 flex items-center gap-1.5 text-zinc-400">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: COLOR[hover.niche] }} />
                  {hover.niche}
                </div>
                <div className="text-zinc-400">{subs(hover.subscribers)}</div>
              </div>
            )}
          </div>

          <p className="text-xs text-zinc-500">
            {data.creators} creators with content vectors · position = CLIP (thumbnails) + BERT (titles, captions), reduced to two
            axes that show {Math.round((data.variance_shown[0] + data.variance_shown[1]) * 100)}% of the variation · colour = niche by
            channel keywords · the brief sits at the fit-weighted centre of its {TOP} best-fitting creators on the map.
          </p>

          {matches && (
            <div className="rounded-xl border border-line bg-panel p-4">
              <h2 className="text-sm font-semibold text-zinc-100">Best-fitting creators for this brief</h2>
              <table className="mt-2 w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-zinc-500">
                    <th className="py-1 font-normal">Creator</th>
                    <th className="py-1 font-normal">Niche</th>
                    <th className="py-1 text-right font-normal">Content fit</th>
                  </tr>
                </thead>
                <tbody>
                  {matches.map((m) => (
                    <tr key={m.p.creator_id} className="border-t border-line/60">
                      <td className="py-1.5 text-zinc-100">{m.p.name}</td>
                      <td className="py-1.5 text-zinc-400">{m.p.niche}</td>
                      <td className="py-1.5 text-right font-mono text-zinc-100">{m.fit.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
