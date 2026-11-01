"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";
import { getCoOccurrenceEdges, getCollaborationEdges, getCreatorSummaries, getMentionEdges, getSharedBrandEdges } from "@/lib/api";
import type { GraphEdge, InfluencerRecommendation, SpilloverBasis } from "@/types";

// Force-directed view of the creator graph the GAIL branch reads. Four link types from GET /feature-store/edges/*:
// collaboration and @mention (direct ties), co-occurrence (named in the same Reddit thread) and shared brand (both promoted the same brand).
// Creators with no visible link are left out of the picture and counted. Weights are raw counts from the feature store; learned per-relation attention
// (PendingWork E6) is not served by the API, so it is not shown. Pan by dragging, zoom with the wheel or the buttons, search a creator by name.

const WIDTH = 900;
const HEIGHT = 580;
const PAD = 14;

type Relation = "collaborates_with" | "mentions" | "co_occurs_with" | "shared_brand";
type ColorBy = "category" | "basis";

interface Link {
  a: string;
  b: string;
  weight: number;
  relation: Relation;
}

interface LayoutNode extends SimulationNodeDatum {
  id: string;
}

const RELATIONS: Relation[] = ["collaborates_with", "mentions", "co_occurs_with", "shared_brand"];

const RELATION_LABEL: Record<Relation, string> = {
  collaborates_with: "Collaboration",
  mentions: "@mention",
  co_occurs_with: "Co-occurrence",
  shared_brand: "Shared brand",
};

const RELATION_HELP: Record<Relation, string> = {
  collaborates_with: "listed collaborator or co-author post",
  mentions: "one tags the other in a title, description or caption",
  co_occurs_with: "named in the same Reddit thread",
  shared_brand: "both promoted the same brand",
};

const RELATION_STROKE: Record<Relation, string> = {
  collaborates_with: "stroke-amber-500",
  mentions: "stroke-rose-500",
  co_occurs_with: "stroke-sky-500",
  shared_brand: "stroke-emerald-500",
};

const RELATION_SWATCH: Record<Relation, string> = {
  collaborates_with: "bg-amber-500",
  mentions: "bg-rose-500",
  co_occurs_with: "bg-sky-500",
  shared_brand: "bg-emerald-500",
};

const BASIS_FILL: Record<SpilloverBasis, string> = {
  trained: "fill-emerald-500",
  inferred: "fill-violet-500",
  placeholder: "fill-zinc-400",
  isolated: "fill-zinc-400",
};

const CATEGORY_FILL: Record<string, string> = {
  fitness_influencer: "fill-emerald-500",
  athlete: "fill-amber-500",
  team: "fill-sky-500",
  league: "fill-slate-500",
  lifestyle_influencer: "fill-pink-500",
  other: "fill-zinc-400",
};
const CATEGORY_SWATCH: Record<string, string> = {
  fitness_influencer: "bg-emerald-500",
  athlete: "bg-amber-500",
  team: "bg-sky-500",
  league: "bg-slate-500",
  lifestyle_influencer: "bg-pink-500",
  other: "bg-zinc-400",
};
const CATEGORY_LABEL: Record<string, string> = {
  fitness_influencer: "fitness",
  athlete: "athlete",
  team: "team",
  league: "league",
  lifestyle_influencer: "lifestyle",
  other: "other",
};

// Deterministic: d3-force starts nodes on a phyllotaxis spiral, so the same links always give the same picture. Run to rest instead of animating.
function computeLayout(links: Link[]): Map<string, { x: number; y: number }> {
  const ids = [...new Set(links.flatMap((l) => [l.a, l.b]))];
  const nodes: LayoutNode[] = ids.map((id) => ({ id }));
  const pairs = new Map<string, { source: string; target: string; strength: number }>();
  for (const l of links) {
    const key = [l.a, l.b].sort().join("|");
    const prev = pairs.get(key);
    pairs.set(key, { source: l.a, target: l.b, strength: (prev?.strength ?? 0) + Math.log1p(l.weight) });
  }
  const sim = forceSimulation(nodes)
    .force(
      "link",
      forceLink<LayoutNode, { source: string; target: string; strength: number }>([...pairs.values()])
        .id((d) => d.id)
        .distance(34)
        .strength((l) => Math.min(0.5, 0.1 + 0.08 * l.strength))
    )
    .force("charge", forceManyBody().strength(-70))
    .force("x", forceX(WIDTH / 2).strength(0.09))
    .force("y", forceY(HEIGHT / 2).strength(0.09))
    .force("collide", forceCollide(8))
    .stop();
  for (let i = 0; i < 420; i++) sim.tick();
  const xs = nodes.map((n) => n.x ?? 0);
  const ys = nodes.map((n) => n.y ?? 0);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const scale = Math.min((WIDTH - 2 * PAD) / (maxX - minX || 1), (HEIGHT - 2 * PAD) / (maxY - minY || 1));
  const offX = (WIDTH - (maxX - minX) * scale) / 2 - minX * scale;
  const offY = (HEIGHT - (maxY - minY) * scale) / 2 - minY * scale;
  return new Map(nodes.map((n) => [n.id, { x: (n.x ?? 0) * scale + offX, y: (n.y ?? 0) * scale + offY }]));
}

// The endpoints return each relationship once per direction (A->B and B->A), so keep one link per unordered pair.
function toLinks(edges: GraphEdge[], relation: Relation): Link[] {
  const byPair = new Map<string, Link>();
  for (const e of edges) {
    const key = [e.source_creator_id, e.target_creator_id].sort().join("|");
    const prev = byPair.get(key);
    if (!prev || e.weight > prev.weight) byPair.set(key, { a: e.source_creator_id, b: e.target_creator_id, weight: e.weight, relation });
  }
  return [...byPair.values()];
}

export default function CreatorGraph({ results }: { results: InfluencerRecommendation[] | null }) {
  const [names, setNames] = useState<Map<string, string>>(new Map());
  const [categories, setCategories] = useState<Map<string, string>>(new Map());
  const [allLinks, setAllLinks] = useState<Link[] | null>(null);
  const [totalCreators, setTotalCreators] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [on, setOn] = useState<Record<Relation, boolean>>({ collaborates_with: true, mentions: true, co_occurs_with: true, shared_brand: false });
  const [colorBy, setColorBy] = useState<ColorBy>("category");
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState(0);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const drag = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    const add = (extra: Link[]) => setAllLinks((prev) => [...(prev ?? []), ...extra]);
    // Collaboration and co-occurrence come back in under a second, so the picture appears at once. @mention (about 10 s: it reads every video text) and
    // shared brand are added as they arrive.
    Promise.all([getCreatorSummaries(), getCollaborationEdges(), getCoOccurrenceEdges()])
      .then(([creators, collab, cooc]) => {
        if (cancelled) return;
        setNames(new Map(creators.map((c) => [c.creator_id, c.name])));
        setCategories(new Map(creators.map((c) => [c.creator_id, c.category ?? "other"])));
        setTotalCreators(creators.length);
        setAllLinks([...toLinks(collab, "collaborates_with"), ...toLinks(cooc, "co_occurs_with")]);
        setPending(2);
        getMentionEdges().then((e) => !cancelled && add(toLinks(e, "mentions"))).catch(() => undefined).finally(() => !cancelled && setPending((n) => n - 1));
        getSharedBrandEdges().then((e) => !cancelled && add(toLinks(e, "shared_brand"))).catch(() => undefined).finally(() => !cancelled && setPending((n) => n - 1));
      })
      .catch(() => {
        if (!cancelled)
          setError("Couldn't load the graph. Is the backend running at " + (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000") + "?");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Wheel zoom needs a non-passive listener so the page does not scroll at the same time.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const px = ((e.clientX - rect.left) / rect.width) * WIDTH;
      const py = ((e.clientY - rect.top) / rect.height) * HEIGHT;
      setView((v) => {
        const k = Math.min(8, Math.max(0.6, v.k * (e.deltaY < 0 ? 1.15 : 1 / 1.15)));
        return { k, x: px - ((px - v.x) / v.k) * k, y: py - ((py - v.y) / v.k) * k };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [allLinks]);

  const links = useMemo(() => (allLinks ? allLinks.filter((l) => on[l.relation]) : null), [allLinks, on]);
  const positions = useMemo(() => (links ? computeLayout(links) : null), [links]);
  const scored = useMemo(() => new Map((results ?? []).map((r) => [r.creator_id, r])), [results]);
  const degree = useMemo(() => {
    const d = new Map<string, number>();
    for (const l of links ?? []) {
      d.set(l.a, (d.get(l.a) ?? 0) + 1);
      d.set(l.b, (d.get(l.b) ?? 0) + 1);
    }
    return d;
  }, [links]);

  if (error) return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>;
  if (!allLinks || !links || !positions) return <p className="text-sm text-zinc-500">Loading the graph from the database (a few seconds)…</p>;

  const nameOf = (id: string) => names.get(id) ?? id;
  const neighbours = new Set<string>();
  if (selected) {
    for (const l of links) {
      if (l.a === selected) neighbours.add(l.b);
      if (l.b === selected) neighbours.add(l.a);
    }
  }
  const dim = (id: string) => selected !== null && id !== selected && !neighbours.has(id);
  const incident = (l: Link) => selected !== null && (l.a === selected || l.b === selected);
  const selectedLinks = selected
    ? links.filter(incident).map((l) => ({ id: l.a === selected ? l.b : l.a, relation: l.relation, weight: l.weight })).sort((x, y) => y.weight - x.weight)
    : [];
  const selectedScore = selected ? scored.get(selected) : undefined;
  const connected = positions.size;
  const counts = Object.fromEntries(RELATIONS.map((r) => [r, allLinks.filter((l) => l.relation === r).length])) as Record<Relation, number>;
  const topNames = new Set([...degree.entries()].sort((x, y) => y[1] - x[1]).slice(0, 14).map(([id]) => id));
  const showLabel = (id: string) => id === selected || (selected !== null && neighbours.has(id)) || (selected === null && topNames.has(id)) || view.k >= 3;
  const matches = query.trim().length >= 2 ? [...names.entries()].filter(([id, n]) => positions.has(id) && n.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 6) : [];

  const focus = (id: string) => {
    const p = positions.get(id);
    setSelected(id);
    setQuery("");
    if (p) setView({ k: 2.4, x: WIDTH / 2 - p.x * 2.4, y: HEIGHT / 2 - p.y * 2.4 });
  };
  const zoom = (f: number) =>
    setView((v) => {
      const k = Math.min(8, Math.max(0.6, v.k * f));
      return { k, x: WIDTH / 2 - ((WIDTH / 2 - v.x) / v.k) * k, y: HEIGHT / 2 - ((HEIGHT / 2 - v.y) / v.k) * k };
    });
  const nodeFill = (id: string) => {
    const r = scored.get(id);
    if (colorBy === "basis" && r) return BASIS_FILL[r.spillover_basis ?? "placeholder"];
    return CATEGORY_FILL[categories.get(id) ?? "other"] ?? CATEGORY_FILL.other;
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {RELATIONS.map((r) => (
          <button
            key={r}
            type="button"
            title={RELATION_HELP[r]}
            aria-pressed={on[r]}
            onClick={() => setOn((o) => ({ ...o, [r]: !o[r] }))}
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition ${
              on[r] ? "border-zinc-400 bg-zinc-100 font-medium dark:border-zinc-600 dark:bg-zinc-900" : "border-zinc-200 text-zinc-500 dark:border-zinc-800"
            }`}
          >
            <span className={`inline-block h-2 w-4 rounded-sm ${RELATION_SWATCH[r]} ${on[r] ? "" : "opacity-30"}`} />
            {RELATION_LABEL[r]} <span className="tabular-nums text-zinc-500">{counts[r]}</span>
          </button>
        ))}
        <select
          value={colorBy}
          onChange={(e) => setColorBy(e.target.value as ColorBy)}
          aria-label="Colour the dots by"
          className="rounded-md border border-zinc-300 bg-transparent px-2 py-1 text-xs dark:border-zinc-700"
        >
          <option value="category">Colour by category</option>
          <option value="basis" disabled={!results || results.length === 0}>
            Colour by spillover basis
          </option>
        </select>
        <div className="relative ml-auto">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find a creator…"
            aria-label="Find a creator in the graph"
            className="w-44 rounded-md border border-zinc-300 bg-transparent px-2.5 py-1 text-xs placeholder:text-zinc-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30 dark:border-zinc-700"
          />
          {matches.length > 0 && (
            <ul className="absolute right-0 z-10 mt-1 w-56 rounded-md border border-zinc-200 bg-white py-1 text-xs shadow-lg dark:border-zinc-700 dark:bg-zinc-900">
              {matches.map(([id, n]) => (
                <li key={id}>
                  <button type="button" onClick={() => focus(id)} className="block w-full truncate px-3 py-1 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800">
                    {n}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-600 dark:text-zinc-400">
        <span>
          {connected} creators shown{totalCreators !== null && ` (${totalCreators - connected} of ${totalCreators} have no link of the types switched on)`}
        </span>
        {pending > 0 && <span className="italic text-zinc-500">still loading {pending} more link type{pending === 1 ? "" : "s"}…</span>}
        {colorBy === "category" ? (
          Object.keys(CATEGORY_LABEL).map((c) => (
            <span key={c} className="flex items-center gap-1">
              <span className={`inline-block h-2.5 w-2.5 rounded-full ${CATEGORY_SWATCH[c]}`} /> {CATEGORY_LABEL[c]}
            </span>
          ))
        ) : (
          <>
            <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" /> trained</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full bg-violet-500" /> inferred</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full bg-zinc-400" /> other</span>
          </>
        )}
      </div>

      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="group"
          aria-label="Creator graph"
          className="w-full cursor-grab touch-none rounded-lg border border-zinc-200 bg-white active:cursor-grabbing dark:border-zinc-800 dark:bg-zinc-950"
          onPointerDown={(e) => {
            drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false };
          }}
          onPointerMove={(e) => {
            const d = drag.current;
            const el = svgRef.current;
            if (!d || !el) return;
            const rect = el.getBoundingClientRect();
            const dx = ((e.clientX - d.x) / rect.width) * WIDTH;
            const dy = ((e.clientY - d.y) / rect.height) * HEIGHT;
            if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
            if (d.moved) setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }));
          }}
          onPointerUp={() => {
            const moved = drag.current?.moved;
            drag.current = null;
            if (!moved) setSelected(null);
          }}
          onPointerLeave={() => {
            drag.current = null;
          }}
        >
          <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
            <g>
              {links.map((l, i) => {
                const p = positions.get(l.a);
                const q = positions.get(l.b);
                if (!p || !q) return null;
                const hot = incident(l);
                return (
                  <line
                    key={i}
                    x1={p.x}
                    y1={p.y}
                    x2={q.x}
                    y2={q.y}
                    className={RELATION_STROKE[l.relation]}
                    strokeWidth={(hot ? 2.4 : 0.5 + Math.log1p(l.weight) * 0.45) / Math.sqrt(view.k)}
                    strokeOpacity={selected ? (hot ? 0.95 : 0.05) : l.relation === "shared_brand" ? 0.2 : 0.4}
                  />
                );
              })}
            </g>
            <g>
              {[...positions.entries()].map(([id, p]) => {
                const r = scored.get(id);
                const radius = (r ? 4.5 + (r.final_score / 100) * 6 : 3.2 + Math.sqrt(degree.get(id) ?? 1) * 1.1) / Math.sqrt(view.k);
                return (
                  <circle
                    key={id}
                    cx={p.x}
                    cy={p.y}
                    r={radius}
                    className={`${nodeFill(id)} cursor-pointer stroke-white dark:stroke-zinc-950`}
                    strokeWidth={(id === selected ? 2.6 : 0.9) / Math.sqrt(view.k)}
                    opacity={dim(id) ? 0.12 : 1}
                    tabIndex={0}
                    role="button"
                    aria-label={`${nameOf(id)}${r ? `, score ${r.final_score.toFixed(0)}` : ""}`}
                    aria-pressed={id === selected}
                    onPointerDown={(e) => e.stopPropagation()}
                    onPointerUp={(e) => e.stopPropagation()}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelected(id === selected ? null : id);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelected(id === selected ? null : id);
                      }
                    }}
                  >
                    <title>{`${nameOf(id)} · ${CATEGORY_LABEL[categories.get(id) ?? "other"] ?? "other"} · ${degree.get(id) ?? 0} links`}</title>
                  </circle>
                );
              })}
            </g>
            <g pointerEvents="none">
              {[...positions.entries()]
                .filter(([id]) => showLabel(id) && !dim(id))
                .map(([id, p]) => (
                  <text
                    key={id}
                    x={p.x + 6 / Math.sqrt(view.k)}
                    y={p.y - 5 / Math.sqrt(view.k)}
                    fontSize={10 / Math.sqrt(view.k)}
                    paintOrder="stroke"
                    strokeWidth={3 / Math.sqrt(view.k)}
                    className="fill-zinc-800 stroke-white font-medium dark:fill-zinc-100 dark:stroke-zinc-950"
                  >
                    {nameOf(id)}
                  </text>
                ))}
            </g>
          </g>
        </svg>
        <div className="absolute right-2 top-2 flex flex-col gap-1">
          {[
            { label: "+", title: "Zoom in", f: () => zoom(1.4) },
            { label: "−", title: "Zoom out", f: () => zoom(1 / 1.4) },
            { label: "⟲", title: "Reset the view", f: () => setView({ x: 0, y: 0, k: 1 }) },
          ].map((b) => (
            <button
              key={b.title}
              type="button"
              title={b.title}
              aria-label={b.title}
              onPointerDown={(e) => e.stopPropagation()}
              onClick={b.f}
              className="grid h-7 w-7 place-items-center rounded-md border border-zinc-300 bg-white/90 text-sm shadow-sm hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900/90 dark:hover:bg-zinc-800"
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>

      {selected ? (
        <div className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="font-medium">
              {nameOf(selected)} <span className="ml-1 text-xs font-normal text-zinc-500">{CATEGORY_LABEL[categories.get(selected) ?? "other"] ?? "other"}</span>
            </h3>
            <button type="button" onClick={() => setSelected(null)} className="text-xs text-zinc-500 underline">
              clear
            </button>
          </div>
          {selectedScore ? (
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              score {selectedScore.final_score.toFixed(0)} ({selectedScore.confidence_low.toFixed(0)}–{selectedScore.confidence_high.toFixed(0)}), spillover basis{" "}
              {selectedScore.spillover_basis ?? "placeholder"}, spillover {selectedScore.score_breakdown.spillover_score.toFixed(2)}
            </p>
          ) : (
            <p className="mt-1 text-xs text-zinc-500">Not in the current recommendation results, so no score is shown.</p>
          )}
          <p className="mt-2 text-xs text-zinc-500">
            {selectedLinks.length} link{selectedLinks.length === 1 ? "" : "s"} of the types switched on. GAIL passes information along these links; the weights are raw counts.
          </p>
          <ul className="mt-1 grid grid-cols-1 gap-x-6 gap-y-0.5 text-xs sm:grid-cols-2">
            {selectedLinks.slice(0, 12).map((l, i) => (
              <li key={i} className="flex justify-between gap-2">
                <button type="button" onClick={() => focus(l.id)} className="truncate text-left underline-offset-2 hover:underline">
                  {nameOf(l.id)}
                </button>
                <span className="shrink-0 text-zinc-500">
                  {RELATION_LABEL[l.relation]} ×{l.weight}
                </span>
              </li>
            ))}
          </ul>
          {selectedLinks.length > 12 && <p className="mt-1 text-xs text-zinc-500">and {selectedLinks.length - 12} more</p>}
        </div>
      ) : (
        <p className="text-xs text-zinc-500">
          Click a creator to highlight their links, drag to move, scroll to zoom. Switch link types on or off above; shared-brand links are many and weak, so they start off.
          {results && results.length > 0 ? " Larger dots score higher in the current results." : ""}
        </p>
      )}
    </div>
  );
}
