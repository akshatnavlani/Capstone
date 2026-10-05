"use client";

import { useEffect, useMemo, useState } from "react";
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";
import { getCoOccurrenceEdges, getCollaborationEdges, getCreators } from "@/lib/api";
import type { GraphEdge, InfluencerRecommendation, SpilloverBasis } from "@/types";

// Force-directed view of the creator graph the GAIL branch reads: 'collaborates_with'
// and 'co_occurs_with' edges from GET /feature-store/edges/*. Creators with no edge
// (the 'isolated' ones) are left out of the picture and counted instead. Edge weights are
// the raw counts from the feature store; learned per-relation attention (PendingWork E6)
// is not served by the API yet, so it is not shown here.

const WIDTH = 720;
const HEIGHT = 520;
const PAD = 12;

type Relation = "collaborates_with" | "co_occurs_with";

interface Link {
  a: string;
  b: string;
  weight: number;
  relation: Relation;
}

interface LayoutNode extends SimulationNodeDatum {
  id: string;
}

const RELATION_LABEL: Record<Relation, string> = {
  collaborates_with: "Collaboration",
  co_occurs_with: "Co-occurrence",
};

const RELATION_STROKE: Record<Relation, string> = {
  collaborates_with: "stroke-amber-500",
  co_occurs_with: "stroke-sky-500",
};

const BASIS_FILL: Record<SpilloverBasis, string> = {
  trained: "fill-emerald-500",
  inferred: "fill-violet-500",
  placeholder: "fill-zinc-400",
  isolated: "fill-zinc-400",
};

// Deterministic: d3-force seeds its jiggle and starts nodes on a phyllotaxis spiral, so the
// same edges always give the same picture. Run to rest instead of animating.
function computeLayout(links: Link[]): Map<string, { x: number; y: number }> {
  const ids = [...new Set(links.flatMap((l) => [l.a, l.b]))];
  const nodes: LayoutNode[] = ids.map((id) => ({ id }));
  const pairs = new Map<string, { source: string; target: string; strength: number }>();
  for (const l of links) {
    const key = [l.a, l.b].sort().join("|");
    const prev = pairs.get(key);
    const add = Math.log1p(l.weight);
    pairs.set(key, { source: l.a, target: l.b, strength: (prev?.strength ?? 0) + add });
  }
  const sim = forceSimulation(nodes)
    .force(
      "link",
      forceLink<LayoutNode, { source: string; target: string; strength: number }>([...pairs.values()])
        .id((d) => d.id)
        .distance(40)
        .strength((l) => Math.min(0.5, 0.1 + 0.08 * l.strength))
    )
    .force("charge", forceManyBody().strength(-60))
    .force("x", forceX(WIDTH / 2).strength(0.1))
    .force("y", forceY(HEIGHT / 2).strength(0.1))
    .force("collide", forceCollide(9))
    .stop();
  for (let i = 0; i < 400; i++) sim.tick();
  // Scale (not clamp) the settled layout into the box so far-flung groups keep their shape.
  const xs = nodes.map((n) => n.x ?? 0);
  const ys = nodes.map((n) => n.y ?? 0);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const scale = Math.min((WIDTH - 2 * PAD) / (maxX - minX || 1), (HEIGHT - 2 * PAD) / (maxY - minY || 1));
  const offX = (WIDTH - (maxX - minX) * scale) / 2 - minX * scale;
  const offY = (HEIGHT - (maxY - minY) * scale) / 2 - minY * scale;
  return new Map(nodes.map((n) => [n.id, { x: (n.x ?? 0) * scale + offX, y: (n.y ?? 0) * scale + offY }]));
}

export default function CreatorGraph({ results }: { results: InfluencerRecommendation[] | null }) {
  const [names, setNames] = useState<Map<string, string>>(new Map());
  const [links, setLinks] = useState<Link[] | null>(null);
  const [totalCreators, setTotalCreators] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCreators(), getCollaborationEdges(), getCoOccurrenceEdges()])
      .then(([creators, collab, cooc]) => {
        if (cancelled) return;
        // The endpoints return each relationship once per direction (A->B and B->A), so keep
        // one link per unordered pair.
        const toLinks = (edges: GraphEdge[], relation: Relation): Link[] => {
          const byPair = new Map<string, Link>();
          for (const e of edges) {
            const key = [e.source_creator_id, e.target_creator_id].sort().join("|");
            const prev = byPair.get(key);
            if (!prev || e.weight > prev.weight)
              byPair.set(key, { a: e.source_creator_id, b: e.target_creator_id, weight: e.weight, relation });
          }
          return [...byPair.values()];
        };
        setNames(new Map(creators.map((c) => [c.creator_id, c.name])));
        setTotalCreators(creators.length);
        setLinks([...toLinks(collab, "collaborates_with"), ...toLinks(cooc, "co_occurs_with")]);
      })
      .catch(() => {
        if (!cancelled)
          setError(
            "Couldn't load the graph. Is the backend running at " +
              (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000") +
              "?"
          );
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const positions = useMemo(() => (links ? computeLayout(links) : null), [links]);
  const scored = useMemo(() => new Map((results ?? []).map((r) => [r.creator_id, r])), [results]);

  if (error) return <p className="text-sm text-red-600 dark:text-red-400">{error}</p>;
  if (!links || !positions) return <p className="text-sm text-zinc-500">Loading graph…</p>;

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
    ? links
        .filter(incident)
        .map((l) => ({ id: l.a === selected ? l.b : l.a, relation: l.relation, weight: l.weight }))
        .sort((x, y) => y.weight - x.weight)
    : [];
  const selectedScore = selected ? scored.get(selected) : undefined;
  const connected = positions.size;
  const undrawn = (results ?? []).filter((r) => !positions.has(r.creator_id)).length;
  const counts = {
    collaborates_with: links.filter((l) => l.relation === "collaborates_with").length,
    co_occurs_with: links.filter((l) => l.relation === "co_occurs_with").length,
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-600 dark:text-zinc-400">
        <span>
          {connected} connected creators
          {totalCreators !== null && ` (${totalCreators - connected} more have no edges and are not drawn)`}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-5 bg-amber-500" /> collaboration ({counts.collaborates_with} pairs)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-5 bg-sky-500" /> co-occurrence ({counts.co_occurs_with} pairs)
        </span>
        {results && results.length > 0 && (
          <>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500" /> trained
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-violet-500" /> inferred
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-zinc-400" /> not in current results
            </span>
          </>
        )}
      </div>

      {undrawn > 0 && (
        <p className="text-xs text-zinc-500">
          {undrawn} of the {results?.length} creators in the current results have no graph edges, so they are not drawn.
        </p>
      )}

      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="group"
        aria-label="Creator graph: collaboration and co-occurrence links"
        className="w-full rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
        onClick={() => setSelected(null)}
      >
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
                strokeWidth={hot ? 2.5 : 0.6 + Math.log1p(l.weight) * 0.5}
                strokeOpacity={selected ? (hot ? 0.95 : 0.06) : 0.45}
              />
            );
          })}
        </g>
        <g>
          {[...positions.entries()].map(([id, p]) => {
            const r = scored.get(id);
            const radius = r ? 5 + (r.final_score / 100) * 7 : 4;
            const fill = r ? BASIS_FILL[r.spillover_basis ?? "placeholder"] : "fill-zinc-400";
            return (
              <circle
                key={id}
                cx={p.x}
                cy={p.y}
                r={radius}
                className={`${fill} cursor-pointer stroke-white dark:stroke-zinc-950`}
                strokeWidth={id === selected ? 3 : 1}
                opacity={dim(id) ? 0.15 : r || !results?.length ? 1 : 0.55}
                tabIndex={0}
                role="button"
                aria-label={`${nameOf(id)}${r ? `, score ${r.final_score.toFixed(0)}` : ""}`}
                aria-pressed={id === selected}
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
                <title>{nameOf(id)}</title>
              </circle>
            );
          })}
        </g>
      </svg>

      {selected ? (
        <div className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="font-medium">{nameOf(selected)}</h3>
            <button type="button" onClick={() => setSelected(null)} className="text-xs text-zinc-500 underline">
              clear
            </button>
          </div>
          {selectedScore ? (
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              score {selectedScore.final_score.toFixed(0)} ({selectedScore.confidence_low.toFixed(0)}–
              {selectedScore.confidence_high.toFixed(0)}), spillover basis {selectedScore.spillover_basis ?? "placeholder"}, spillover{" "}
              {selectedScore.score_breakdown.spillover_score.toFixed(2)}
            </p>
          ) : (
            <p className="mt-1 text-xs text-zinc-500">Not in the current recommendation results, so no score is shown.</p>
          )}
          <p className="mt-2 text-xs text-zinc-500">
            {selectedLinks.length} link{selectedLinks.length === 1 ? "" : "s"}. GAIL passes information along these
            links; the weights below are the raw collaboration / co-occurrence counts.
          </p>
          <ul className="mt-1 grid grid-cols-1 gap-x-6 gap-y-0.5 text-xs sm:grid-cols-2">
            {selectedLinks.slice(0, 12).map((l, i) => (
              <li key={i} className="flex justify-between gap-2">
                <button type="button" onClick={() => setSelected(l.id)} className="truncate text-left underline-offset-2 hover:underline">
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
        <p className="text-xs text-zinc-500">Click a creator to highlight their links. Larger dots score higher in the current results.</p>
      )}
    </div>
  );
}
