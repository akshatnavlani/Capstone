"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type Simulation, type SimulationNodeDatum } from "d3-force";
import Avatar from "@/components/Avatar";
import { getCoOccurrenceEdges, getCollaborationEdges, getCreatorSummaries, getMentionEdges, getSharedBrandEdges } from "@/lib/api";
import type { GraphEdge, InfluencerRecommendation, SpilloverBasis } from "@/types";

// "Constellation" view of the creator graph the GAIL branch reads (1 Nov 2026 redesign; the data and controls are unchanged).
// Four link types from GET /feature-store/edges/*: collaboration and @mention (direct ties), co-occurrence (named in the same Reddit thread) and
// shared brand (both promoted the same brand). Creators with no visible link are left out of the picture and counted. Weights are raw counts.
//
// New: nodes glow and can be DRAGGED (the neighbours follow on their links and the net springs back); a "Ripple" mode lets a visitor pick a creator and
// watch how far information could travel along the real links, hop by hop. The ripple is an illustration of the pathways GAIL reads, not an effect:
// on real data we find no detectable spillover, and the page says so. Pan by dragging the background, zoom with the wheel or the buttons.

const WIDTH = 900;
const HEIGHT = 580;
const PAD = 22;

type Relation = "collaborates_with" | "mentions" | "co_occurs_with" | "shared_brand";
type ColorBy = "category" | "basis";
type Mode = "network" | "ripple";

interface Link {
  a: string;
  b: string;
  weight: number;
  relation: Relation;
}

interface BaseNode extends SimulationNodeDatum {
  id: string;
}

interface LayoutNode extends BaseNode {
  hx: number;
  hy: number;
}

interface Point {
  x: number;
  y: number;
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

const RELATION_COLOR: Record<Relation, string> = {
  collaborates_with: "#f5b83d",
  mentions: "#ff6b8b",
  co_occurs_with: "#5aa9ff",
  shared_brand: "#46d68a",
};

const BASIS_COLOR: Record<SpilloverBasis, string> = {
  trained: "#35d6c0",
  inferred: "#b38cff",
  placeholder: "#63768a",
  isolated: "#63768a",
};

const CATEGORY_COLOR: Record<string, string> = {
  fitness_influencer: "#35d6c0",
  athlete: "#f5b83d",
  team: "#6aa9ff",
  league: "#8497aa",
  lifestyle_influencer: "#ff7ab6",
  other: "#63768a",
};
const CATEGORY_LABEL: Record<string, string> = {
  fitness_influencer: "fitness",
  athlete: "athlete",
  team: "team",
  league: "league",
  lifestyle_influencer: "lifestyle",
  other: "other",
};

const HOP_COLOR = ["#ffffff", "#f5b83d", "#35d6c0", "#6aa9ff"]; // 0 = the chosen creator, then one colour per hop
const HOP_ALPHA = [1, 0.95, 0.7, 0.5];

// Deterministic: d3-force starts nodes on a phyllotaxis spiral, so the same links always give the same picture. Run to rest instead of animating;
// the live, draggable simulation below starts from this resting picture.
function computeLayout(links: Link[]): Map<string, Point> {
  const ids = [...new Set(links.flatMap((l) => [l.a, l.b]))];
  const nodes: BaseNode[] = ids.map((id) => ({ id }));
  const pairs = new Map<string, { source: string; target: string; strength: number }>();
  for (const l of links) {
    const key = [l.a, l.b].sort().join("|");
    const prev = pairs.get(key);
    pairs.set(key, { source: l.a, target: l.b, strength: (prev?.strength ?? 0) + Math.log1p(l.weight) });
  }
  const sim = forceSimulation(nodes)
    .force(
      "link",
      forceLink<BaseNode, { source: string; target: string; strength: number }>([...pairs.values()])
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

function ZoomButton({ label, title, onClick }: { label: string; title: string; onClick: () => void }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onPointerDown={(e) => e.stopPropagation()}
      onClick={onClick}
      className="grid h-7 w-7 place-items-center rounded-md border border-line bg-zinc-900/90 text-sm text-zinc-200 shadow-sm transition hover:border-accent hover:text-accent"
    >
      {label}
    </button>
  );
}

export default function CreatorGraph({ results }: { results: InfluencerRecommendation[] | null }) {
  const [names, setNames] = useState<Map<string, string>>(new Map());
  const [categories, setCategories] = useState<Map<string, string>>(new Map());
  const [allLinks, setAllLinks] = useState<Link[] | null>(null);
  const [totalCreators, setTotalCreators] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [on, setOn] = useState<Record<Relation, boolean>>({ collaborates_with: true, mentions: true, co_occurs_with: true, shared_brand: false });
  const [colorBy, setColorBy] = useState<ColorBy>("category");
  const [mode, setMode] = useState<Mode>("network");
  const [hops, setHops] = useState(2);
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState(0);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const [reducedMotion] = useState(() => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [pressed, setPressed] = useState(false); // a dot is being held, so the hover card steps aside
  // positions while the net is moving; tagged with the layout they belong to so a stale snapshot is never used after the links change
  const [live, setLive] = useState<{ src: Map<string, Point>; map: Map<string, Point> } | null>(null);
  const pan = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);
  const nodeDrag = useRef<{ id: string; moved: boolean } | null>(null);
  const simRef = useRef<{ sim: Simulation<LayoutNode, undefined>; nodes: Map<string, LayoutNode>; idle: number } | null>(null);
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
  const adjacency = useMemo(() => {
    const adj = new Map<string, string[]>();
    for (const l of links ?? []) {
      (adj.get(l.a) ?? adj.set(l.a, []).get(l.a)!).push(l.b);
      (adj.get(l.b) ?? adj.set(l.b, []).get(l.b)!).push(l.a);
    }
    return adj;
  }, [links]);
  // Hop distance from the chosen creator along the visible links (breadth-first), for the ripple.
  const hopOf = useMemo(() => {
    const d = new Map<string, number>();
    if (!selected || !adjacency.has(selected)) return d;
    d.set(selected, 0);
    const queue = [selected];
    for (let i = 0; i < queue.length; i++) {
      const v = queue[i];
      const dv = d.get(v)!;
      if (dv >= 3) continue;
      for (const w of adjacency.get(v) ?? []) {
        if (!d.has(w)) {
          d.set(w, dv + 1);
          queue.push(w);
        }
      }
    }
    return d;
  }, [selected, adjacency]);

  // Live, draggable simulation. It starts at rest from the resting layout; dragging a dot warms it up, its neighbours follow along their links, and the net
  // settles back towards where it started. Nothing moves until a dot is touched.
  useEffect(() => {
    if (!positions || !links) return;
    const nodes: LayoutNode[] = [...positions.entries()].map(([id, p]) => ({ id, x: p.x, y: p.y, hx: p.x, hy: p.y }));
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const seen = new Set<string>();
    const simLinks: { source: LayoutNode; target: LayoutNode; len: number }[] = [];
    for (const l of links) {
      const key = [l.a, l.b].sort().join("|");
      const s = byId.get(l.a), t = byId.get(l.b);
      if (seen.has(key) || !s || !t) continue;
      seen.add(key);
      simLinks.push({ source: s, target: t, len: Math.hypot((s.x ?? 0) - (t.x ?? 0), (s.y ?? 0) - (t.y ?? 0)) + 1 });
    }
    // The net is never frozen: each dot drifts a little on its own (a slow, smooth wander), the links keep pulling neighbours along, and a very weak gravity keeps
    // everything in view. A dragged dot stays where it is dropped; nothing is pinned. "Reset" puts the original picture back.
    let t = 0;
    const phase = new Map(nodes.map((n, i) => [n.id, i * 2.399]));
    const wander = () => {
      t += 1;
      for (const n of nodes) {
        const ph = phase.get(n.id) ?? 0;
        n.vx = (n.vx ?? 0) + Math.cos(t * 0.035 + ph) * 0.045;
        n.vy = (n.vy ?? 0) + Math.sin(t * 0.03 + ph * 1.3) * 0.045;
      }
    };
    const sim = forceSimulation<LayoutNode>(nodes)
      .alpha(0)
      .alphaDecay(0.04)
      .velocityDecay(0.35)
      .force("link", forceLink<LayoutNode, (typeof simLinks)[number]>(simLinks).distance((d) => d.len).strength(0.35))
      .force("charge", forceManyBody<LayoutNode>().strength(-9).distanceMax(60))
      .force("collide", forceCollide<LayoutNode>(6))
      .force("gx", forceX<LayoutNode>(WIDTH / 2).strength(0.004))
      .force("gy", forceY<LayoutNode>(HEIGHT / 2).strength(0.004))
      .force("wander", wander);
    // We drive the ticks ourselves (about 30 a second) instead of letting d3 use animation frames, so the net also keeps moving when the page is not the
    // front tab, and so we can stop it when it is hidden.
    const idle = reducedMotion ? 0 : 0.03;
    sim.stop();
    sim.alphaTarget(idle).alpha(idle ? 0.05 : 0);
    const timer = setInterval(() => {
      if (document.hidden || sim.alpha() < sim.alphaMin()) return;
      sim.tick();
      setLive({ src: positions, map: new Map(nodes.map((n) => [n.id, { x: n.x ?? 0, y: n.y ?? 0 }])) });
    }, 33);
    simRef.current = { sim, nodes: byId, idle };
    return () => {
      clearInterval(timer);
      sim.stop();
      simRef.current = null;
    };
  }, [positions, links, reducedMotion]);

  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (!allLinks || !links || !positions) return <p className="text-sm text-zinc-500">Loading the graph from the database (a few seconds)…</p>;

  const pos = live && live.src === positions ? live.map : positions;
  const nameOf = (id: string) => names.get(id) ?? id;
  const ripple = mode === "ripple" && selected !== null && hopOf.size > 0;
  const neighbours = new Set<string>();
  if (selected) for (const w of adjacency.get(selected) ?? []) neighbours.add(w);
  const inRipple = (id: string) => ripple && (hopOf.get(id) ?? 99) <= hops;
  const dim = (id: string) => (ripple ? !inRipple(id) : selected !== null && id !== selected && !neighbours.has(id));
  const incident = (l: Link) => selected !== null && (l.a === selected || l.b === selected);
  const selectedLinks = selected
    ? links.filter(incident).map((l) => ({ id: l.a === selected ? l.b : l.a, relation: l.relation, weight: l.weight })).sort((x, y) => y.weight - x.weight)
    : [];
  const selectedScore = selected ? scored.get(selected) : undefined;
  const connected = positions.size;
  const counts = Object.fromEntries(RELATIONS.map((r) => [r, allLinks.filter((l) => l.relation === r).length])) as Record<Relation, number>;
  const hubs = [...degree.entries()].sort((x, y) => y[1] - x[1]).slice(0, 6);
  const topNames = new Set(hubs.concat([...degree.entries()].sort((x, y) => y[1] - x[1]).slice(6, 14)).map(([id]) => id));
  // A hub can have dozens of neighbours; name only the 10 best connected so the labels do not pile up.
  const labelled = new Set([...neighbours].sort((x, y) => (degree.get(y) ?? 0) - (degree.get(x) ?? 0)).slice(0, 10));
  const showLabel = (id: string) => id === selected || (selected !== null && labelled.has(id)) || (selected === null && topNames.has(id)) || view.k >= 3;
  const matches = query.trim().length >= 2 ? [...names.entries()].filter(([id, n]) => positions.has(id) && n.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 6) : [];
  const reach = [1, 2, 3].map((h) => [...hopOf.values()].filter((d) => d === h).length);

  const focus = (id: string) => {
    const p = pos.get(id);
    setSelected(id);
    setQuery("");
    if (p) setView({ k: 2.2, x: WIDTH / 2 - p.x * 2.2, y: HEIGHT / 2 - p.y * 2.2 });
  };
  const zoom = (f: number) =>
    setView((v) => {
      const k = Math.min(8, Math.max(0.6, v.k * f));
      return { k, x: WIDTH / 2 - ((WIDTH / 2 - v.x) / v.k) * k, y: HEIGHT / 2 - ((HEIGHT / 2 - v.y) / v.k) * k };
    });
  const chooseMode = (m: Mode) => {
    setMode(m);
    if (m === "ripple" && !selected && hubs[0]) setSelected(hubs[0][0]);
  };
  const resetLayout = () => {
    simRef.current?.nodes.forEach((n) => {
      n.x = n.hx;
      n.y = n.hy;
      n.vx = n.vy = 0;
      n.fx = n.fy = null;
    });
    setLive(null);
    setView({ x: 0, y: 0, k: 1 });
  };
  const nodeColor = (id: string) => {
    const r = scored.get(id);
    if (colorBy === "basis" && r) return BASIS_COLOR[r.spillover_basis ?? "placeholder"];
    return CATEGORY_COLOR[categories.get(id) ?? "other"] ?? CATEGORY_COLOR.other;
  };
  // pointer position -> graph coordinates (undo the pan and zoom)
  const toGraph = (e: { clientX: number; clientY: number }): Point | null => {
    const el = svgRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * WIDTH;
    const py = ((e.clientY - rect.top) / rect.height) * HEIGHT;
    return { x: (px - view.x) / view.k, y: (py - view.y) / view.k };
  };
  const endNodeDrag = () => {
    const d = nodeDrag.current;
    nodeDrag.current = null;
    setPressed(false);
    const s = simRef.current;
    if (!d || !s) return;
    const n = s.nodes.get(d.id);
    if (n) n.fx = n.fy = null;
    s.sim.alphaTarget(s.idle);
    if (!d.moved) setSelected((cur) => (cur === d.id ? null : d.id));
  };
  const sw = (n: number) => n / Math.sqrt(view.k);
  const hoverPoint = hovered ? pos.get(hovered) : undefined;
  const hoverScore = hovered ? scored.get(hovered) : undefined;
  const selPoint = selected ? pos.get(selected) : undefined;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="View mode" className="flex overflow-hidden rounded-full border border-line text-xs">
          {([["network", "Network"], ["ripple", "Ripple"]] as const).map(([m, label]) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => chooseMode(m)}
              className={`px-3.5 py-1 transition ${mode === m ? "bg-accent font-semibold text-[#1a1306]" : "text-zinc-300 hover:text-accent"}`}
            >
              {label}
            </button>
          ))}
        </div>
        {RELATIONS.map((r) => (
          <button
            key={r}
            type="button"
            title={RELATION_HELP[r]}
            aria-pressed={on[r]}
            onClick={() => setOn((o) => ({ ...o, [r]: !o[r] }))}
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition ${on[r] ? "border-zinc-500 bg-zinc-900 font-medium" : "border-line text-zinc-500"}`}
          >
            <span className="inline-block h-1.5 w-4 rounded-full" style={{ background: RELATION_COLOR[r], opacity: on[r] ? 1 : 0.3, boxShadow: on[r] ? `0 0 8px ${RELATION_COLOR[r]}` : "none" }} />
            {RELATION_LABEL[r]} <span className="tabular-nums text-zinc-500">{counts[r]}</span>
          </button>
        ))}
        <select
          value={colorBy}
          onChange={(e) => setColorBy(e.target.value as ColorBy)}
          aria-label="Colour the dots by"
          className="rounded-md border border-line bg-zinc-900 px-2 py-1 text-xs"
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
            className="w-44 rounded-md border border-line bg-transparent px-2.5 py-1 text-xs placeholder:text-zinc-500 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
          />
          {matches.length > 0 && (
            <ul className="absolute right-0 z-10 mt-1 w-56 rounded-md border border-line bg-zinc-900 py-1 text-xs shadow-lg">
              {matches.map(([id, n]) => (
                <li key={id}>
                  <button type="button" onClick={() => focus(id)} className="block w-full truncate px-3 py-1 text-left hover:bg-zinc-800">
                    {n}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-400">
        <span>
          {connected} creators shown{totalCreators !== null && ` (${totalCreators - connected} of ${totalCreators} have no link of the types switched on)`}
        </span>
        {pending > 0 && <span className="italic text-zinc-500">still loading {pending} more link type{pending === 1 ? "" : "s"}…</span>}
        {colorBy === "category" ? (
          Object.keys(CATEGORY_LABEL).map((c) => (
            <span key={c} className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: CATEGORY_COLOR[c], boxShadow: `0 0 6px ${CATEGORY_COLOR[c]}` }} /> {CATEGORY_LABEL[c]}
            </span>
          ))
        ) : (
          (["trained", "inferred", "placeholder"] as const).map((b) => (
            <span key={b} className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: BASIS_COLOR[b] }} /> {b === "placeholder" ? "other" : b}
            </span>
          ))
        )}
      </div>

      {hubs.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-zinc-500">Most connected:</span>
          {hubs.map(([id, d]) => (
            <button
              key={id}
              type="button"
              onClick={() => focus(id)}
              className={`rounded-full border px-2.5 py-0.5 transition hover:border-accent hover:text-accent ${id === selected ? "border-accent text-accent" : "border-line text-zinc-300"}`}
            >
              {nameOf(id)} <span className="tabular-nums text-zinc-500">{d}</span>
            </button>
          ))}
        </div>
      )}

      <div className="relative overflow-hidden rounded-xl border border-line" style={{ background: "radial-gradient(ellipse at 50% 40%, #121d28 0%, #0a1016 70%)" }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="group"
          aria-label="Creator graph"
          className="block w-full cursor-grab touch-none active:cursor-grabbing"
          onPointerDown={(e) => {
            pan.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false };
          }}
          onPointerMove={(e) => {
            const nd = nodeDrag.current;
            if (nd) {
              const g = toGraph(e);
              const s = simRef.current;
              const n = s?.nodes.get(nd.id);
              if (g && s && n) {
                nd.moved = true;
                n.fx = g.x;
                n.fy = g.y;
                s.sim.alphaTarget(0.3).alpha(Math.max(s.sim.alpha(), 0.3));
              }
              return;
            }
            const d = pan.current;
            const el = svgRef.current;
            if (!d || !el) return;
            const rect = el.getBoundingClientRect();
            const dx = ((e.clientX - d.x) / rect.width) * WIDTH;
            const dy = ((e.clientY - d.y) / rect.height) * HEIGHT;
            if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
            if (d.moved) setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }));
          }}
          onPointerUp={() => {
            if (nodeDrag.current) return endNodeDrag();
            const moved = pan.current?.moved;
            pan.current = null;
            if (!moved) setSelected(null);
          }}
          onPointerLeave={() => {
            pan.current = null;
            if (nodeDrag.current) endNodeDrag();
          }}
        >
          <defs>
            <filter id="cg-glow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="2.6" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
            <g>
              {links.map((l, i) => {
                const p = pos.get(l.a);
                const q = pos.get(l.b);
                if (!p || !q) return null;
                const ha = hopOf.get(l.a), hb = hopOf.get(l.b);
                const lit = ripple && ha !== undefined && hb !== undefined && Math.min(ha, hb) < hops && Math.max(ha, hb) <= hops;
                const hot = !ripple && incident(l);
                const h = lit ? Math.min(ha!, hb!) + 1 : 0;
                const color = lit ? HOP_COLOR[h] : RELATION_COLOR[l.relation];
                const base = l.relation === "shared_brand" ? 0.16 : 0.32;
                const opacity = ripple ? (lit ? HOP_ALPHA[h] : 0.035) : selected ? (hot ? 0.95 : 0.04) : base;
                return (
                  <line
                    key={i}
                    x1={p.x}
                    y1={p.y}
                    x2={q.x}
                    y2={q.y}
                    stroke={color}
                    strokeWidth={lit ? sw(2.2) : sw(hot ? 2.4 : 0.5 + Math.log1p(l.weight) * 0.45)}
                    strokeOpacity={opacity}
                    strokeDasharray={lit && !reducedMotion ? "5 4" : undefined}
                    style={lit && !reducedMotion ? { animation: `dash ${0.9 + h * 0.5}s linear infinite`, animationDelay: `${h * 0.18}s` } : undefined}
                  />
                );
              })}
            </g>
            <g filter="url(#cg-glow)">
              {[...pos.entries()].map(([id, p]) => {
                const r = scored.get(id);
                const hop = ripple ? hopOf.get(id) : undefined;
                const radius = (r ? 4.5 + (r.final_score / 100) * 6 : 3.2 + Math.sqrt(degree.get(id) ?? 1) * 1.1) / Math.sqrt(view.k);
                const ringed = hop !== undefined && hop >= 1 && hop <= hops;
                return (
                  <circle
                    key={id}
                    cx={p.x}
                    cy={p.y}
                    r={id === selected ? radius * 1.35 : radius}
                    fill={nodeColor(id)}
                    stroke={id === selected ? "#ffffff" : ringed ? HOP_COLOR[hop!] : "#0a1016"}
                    strokeWidth={sw(id === selected ? 2.4 : ringed ? 2 : 0.9)}
                    opacity={dim(id) ? 0.1 : 1}
                    className="cursor-pointer"
                    tabIndex={0}
                    role="button"
                    aria-label={`${nameOf(id)}${r ? `, score ${r.final_score.toFixed(0)}` : ""}`}
                    aria-pressed={id === selected}
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      nodeDrag.current = { id, moved: false };
                      setPressed(true);
                    }}
                    onPointerUp={(e) => {
                      e.stopPropagation();
                      endNodeDrag();
                    }}
                    onPointerEnter={() => setHovered(id)}
                    onPointerLeave={() => setHovered((h) => (h === id ? null : h))}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelected(id === selected ? null : id);
                      }
                    }}
                  />
                );
              })}
            </g>
            {ripple && selPoint && !reducedMotion && (
              <g pointerEvents="none">
                {[0, 1, 2].map((i) => (
                  <circle key={i} cx={selPoint.x} cy={selPoint.y} fill="none" stroke="#f5b83d" strokeWidth={sw(1.5)}>
                    <animate attributeName="r" from={sw(8)} to={sw(8 + 34 * hops)} dur="3s" begin={`${i}s`} repeatCount="indefinite" />
                    <animate attributeName="opacity" from="0.7" to="0" dur="3s" begin={`${i}s`} repeatCount="indefinite" />
                  </circle>
                ))}
              </g>
            )}
            <g pointerEvents="none">
              {[...pos.entries()]
                .filter(([id]) => showLabel(id) && !dim(id))
                .map(([id, p]) => (
                  <text
                    key={id}
                    x={p.x + sw(7)}
                    y={p.y - sw(6)}
                    fontSize={sw(10)}
                    paintOrder="stroke"
                    stroke="#0a1016"
                    strokeWidth={sw(3)}
                    fill="#e8eef4"
                    className="font-medium"
                  >
                    {nameOf(id)}
                  </text>
                ))}
            </g>
          </g>
        </svg>

        {hoverPoint && hovered && hovered !== selected && !pressed && (
          <div
            className="pointer-events-none absolute z-10 max-w-[220px] -translate-x-1/2 -translate-y-full rounded-md border border-line bg-zinc-900/95 px-2.5 py-1.5 text-xs shadow-lg"
            style={{ left: `${((hoverPoint.x * view.k + view.x) / WIDTH) * 100}%`, top: `${((hoverPoint.y * view.k + view.y) / HEIGHT) * 100}%`, marginTop: -10 }}
          >
            <div className="flex items-center gap-2 font-medium text-zinc-100">
              <Avatar creatorId={hovered} name={nameOf(hovered)} size={22} />
              {nameOf(hovered)}
            </div>
            <div className="text-zinc-400">
              {CATEGORY_LABEL[categories.get(hovered) ?? "other"] ?? "other"} · {degree.get(hovered) ?? 0} links
              {hoverScore ? ` · score ${hoverScore.final_score.toFixed(0)}` : ""}
            </div>
          </div>
        )}

        <div className="absolute right-2 top-2 flex flex-col gap-1">
          <ZoomButton label="+" title="Zoom in" onClick={() => zoom(1.4)} />
          <ZoomButton label="−" title="Zoom out" onClick={() => zoom(1 / 1.4)} />
          <ZoomButton label="⟲" title="Reset the layout and the view" onClick={() => resetLayout()} />
        </div>

        {mode === "ripple" && (
          <div className="absolute bottom-2 left-2 flex items-center gap-2 rounded-lg border border-line bg-zinc-900/90 px-3 py-1.5 text-xs" onPointerDown={(e) => e.stopPropagation()}>
            <span className="text-zinc-400">Reach</span>
            {[1, 2, 3].map((h) => (
              <button
                key={h}
                type="button"
                aria-pressed={hops === h}
                onClick={() => setHops(h)}
                className={`rounded-full border px-2 py-0.5 tabular-nums transition ${hops === h ? "border-transparent font-semibold text-[#0a1016]" : "border-line text-zinc-300 hover:border-accent"}`}
                style={hops === h ? { background: HOP_COLOR[h] } : undefined}
              >
                {h} hop{h > 1 ? "s" : ""}
              </button>
            ))}
            {selected && <span className="text-zinc-300">reaches <b className="tabular-nums text-zinc-50">{reach.slice(0, hops).reduce((a, b) => a + b, 0)}</b> creators</span>}
          </div>
        )}
      </div>

      {mode === "ripple" && (
        <p className="text-xs leading-relaxed text-zinc-500">
          <span className="mr-1.5 rounded-full border border-signal/50 px-2 py-0.5 font-mono uppercase tracking-wider text-signal">illustration</span>
          The ripple shows how far information could travel from the chosen creator along the real links, one hop at a time. It is not an effect: on real data we find no
          detectable spillover.
        </p>
      )}

      {selected ? (
        <div className="rounded-xl border border-line p-4 text-sm">
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="flex items-center gap-2.5 font-medium text-zinc-50">
              <Avatar creatorId={selected} name={nameOf(selected)} size={34} />
              {nameOf(selected)} <span className="ml-1 text-xs font-normal text-zinc-500">{CATEGORY_LABEL[categories.get(selected) ?? "other"] ?? "other"}</span>
            </h3>
            <button type="button" onClick={() => setSelected(null)} className="text-xs text-zinc-500 underline hover:text-accent">
              clear
            </button>
          </div>
          {selectedScore ? (
            <p className="mt-1 text-xs text-zinc-400">
              score {selectedScore.final_score.toFixed(0)} ({selectedScore.confidence_low.toFixed(0)}–{selectedScore.confidence_high.toFixed(0)}), spillover basis{" "}
              {selectedScore.spillover_basis ?? "placeholder"}, spillover {selectedScore.score_breakdown.spillover_score.toFixed(2)} (context, not scored)
            </p>
          ) : (
            <p className="mt-1 text-xs text-zinc-500">Not in the current recommendation results, so no score is shown.</p>
          )}
          <p className="mt-2 text-xs text-zinc-500">
            {selectedLinks.length} link{selectedLinks.length === 1 ? "" : "s"} of the types switched on
            {hopOf.size > 0 && ` · within 1, 2, 3 hops: ${reach[0]}, ${reach[0] + reach[1]}, ${reach[0] + reach[1] + reach[2]} creators`}. GAIL passes information along these links; the
            weights are raw counts.
          </p>
          <ul className="mt-1 grid grid-cols-1 gap-x-6 gap-y-0.5 text-xs sm:grid-cols-2">
            {selectedLinks.slice(0, 12).map((l, i) => (
              <li key={i} className="flex justify-between gap-2">
                <button type="button" onClick={() => focus(l.id)} className="truncate text-left underline-offset-2 hover:text-accent hover:underline">
                  {nameOf(l.id)}
                </button>
                <span className="shrink-0 text-zinc-500">
                  <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full" style={{ background: RELATION_COLOR[l.relation] }} />
                  {RELATION_LABEL[l.relation]} ×{l.weight}
                </span>
              </li>
            ))}
          </ul>
          {selectedLinks.length > 12 && <p className="mt-1 text-xs text-zinc-500">and {selectedLinks.length - 12} more</p>}
        </div>
      ) : (
        <p className="text-xs text-zinc-500">
          Click a creator to light up their links, drag a dot and watch its neighbours follow, drag the background to pan, scroll to zoom. Try Ripple to see how far a link
          chain reaches. Shared-brand links are many and weak, so they start off.
          {results && results.length > 0 ? " Larger dots score higher in the current results." : ""}
        </p>
      )}
    </div>
  );
}
