"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import { Network } from "vis-network/standalone";
import { DataSet } from "vis-data/peer";
import {
  getCreators,
  getCollaborationEdges,
  getCoOccurrenceEdges,
  getSponsorshipEdges,
} from "@/lib/api";
import { useStoredRecommendationResult } from "@/lib/useStoredRecommendationResult";
import type { SpilloverBasis } from "@/types";

type CreatorLite = { creator_id: string; name: string; category: string | null };

const CATEGORY_COLOR: Record<string, string> = {
  athlete: "#0ea5e9",
  team: "#8b5cf6",
  league: "#f59e0b",
  fitness_influencer: "#10b981",
  lifestyle_influencer: "#ec4899",
  other: "#71717a",
};

const BASIS_COLOR: Record<SpilloverBasis, string> = {
  trained: "#059669",
  inferred: "#7c3aed",
  placeholder: "#a1a1aa",
  isolated: "#a1a1aa",
};

export default function CollabGraph() {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const nodesDataSetRef = useRef<DataSet<any> | null>(null);
  const edgesDataSetRef = useRef<DataSet<any> | null>(null);

  const [creators, setCreators] = useState<CreatorLite[]>([]);
  const [collabEdges, setCollabEdges] = useState<any[]>([]);
  const [coEdges, setCoEdges] = useState<any[]>([]);
  const [sponsorEdges, setSponsorEdges] = useState<any[]>([]);
  const [brands, setBrands] = useState<Map<string, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [selectedBases, setSelectedBases] = useState<Set<SpilloverBasis>>(new Set());
  const [edgeTypes, setEdgeTypes] = useState<Set<string>>(new Set(["collab", "coOccurrence", "sponsorship"]));
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [weightThreshold, setWeightThreshold] = useState<number>(1);

  const result = useStoredRecommendationResult();
  const highlightedIds = useMemo(() => new Set(result?.results.map((r) => r.creator_id) ?? []), [result]);
  const basisById = useMemo(() => {
    const m = new Map<string, SpilloverBasis>();
    result?.results.forEach((r) => {
      if (r.spillover_basis) m.set(r.creator_id, r.spillover_basis as SpilloverBasis);
    });
    return m;
  }, [result]);

  // Fetch all data once
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const [creatorsRaw, collab, coOcc, sponsor] = await Promise.all([
          getCreators() as Promise<any[]>,
          getCollaborationEdges(),
          getCoOccurrenceEdges(),
          getSponsorshipEdges(),
        ]);
        if (cancelled) return;
        // creatorsRaw is CreatorFeatureRecord[] with category; normalize
        const lite: CreatorLite[] = creatorsRaw.map((c: any) => ({
          creator_id: c.creator_id,
          name: c.name,
          category: c.category ?? null,
        }));
        setCreators(lite);
        setCollabEdges(collab);
        setCoEdges(coOcc);
        setSponsorEdges(sponsor);
        // collect brand ids for display (optional)
        const b = new Map<string, string>();
        sponsor.forEach((s: any) => {
          if (!b.has(s.brand_id)) b.set(s.brand_id, s.brand_id.slice(0, 8));
        });
        setBrands(b);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? "Failed to load graph data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // Build vis-network once data ready
  useEffect(() => {
    if (!containerRef.current || creators.length === 0) return;
    if (networkRef.current) return; // init once

    const nodes = new DataSet<any>([]);
    const edges = new DataSet<any>([]);
    nodesDataSetRef.current = nodes;
    edgesDataSetRef.current = edges;

    const options: any = {
      nodes: {
        shape: "dot",
        size: 10,
        font: { size: 11, color: "#27272a" },
        borderWidth: 2,
        shadow: true,
      },
      edges: {
        smooth: { type: "continuous" },
        width: 1,
        shadow: true,
      },
      physics: {
        solver: "forceAtlas2Based",
        forceAtlas2Based: { gravitationalConstant: -45, centralGravity: 0.005, springLength: 85, springConstant: 0.08 },
        stabilization: { iterations: 250 },
      },
      interaction: { hover: true, tooltipDelay: 150, navigationButtons: false, keyboard: true },
    };

    const network = new Network(containerRef.current, { nodes, edges }, options);
    networkRef.current = network;
    network.on("stabilizationIterationsDone", () => network.fit({ animation: { duration: 600, easingFunction: "easeInOutQuad" } }));
    network.on("click", (params) => {
      if (params.nodes.length === 1) {
        const id = params.nodes[0] as string;
        // focus + keep highlight
        network.focus(id, { scale: 1.1, animation: { duration: 600, easingFunction: "easeInOutQuad" } });
      }
    });

    return () => {
      network.destroy();
      networkRef.current = null;
    };
  }, [creators.length]);

  // Apply filters -> rebuild DataSets
  useEffect(() => {
    if (!nodesDataSetRef.current || !edgesDataSetRef.current || creators.length === 0) return;

    // Node filter
    const filteredCreators = creators.filter((c) => {
      if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false;
      if (categoryFilter !== "all" && (c.category ?? "other") !== categoryFilter) return false;
      if (selectedBases.size > 0) {
        const basis = basisById.get(c.creator_id) ?? "placeholder";
        if (!selectedBases.has(basis)) return false;
      }
      return true;
    });
    const filteredIds = new Set(filteredCreators.map((c) => c.creator_id));

    const nodesArray = filteredCreators.map((c) => {
      const isHighlighted = highlightedIds.has(c.creator_id);
      const basis = (basisById.get(c.creator_id) ?? "placeholder") as SpilloverBasis;
      const cat = c.category ?? "other";
      return {
        id: c.creator_id,
        label: c.name.length > 18 ? c.name.slice(0, 17) + "…" : c.name,
        title: `${c.name} — ${cat} — basis: ${basis}${isHighlighted ? " ★ recommended" : ""}`,
        color: {
          background: isHighlighted ? BASIS_COLOR[basis] ?? CATEGORY_COLOR[cat] : CATEGORY_COLOR[cat] ?? "#71717a",
          border: isHighlighted ? "#0f172a" : CATEGORY_COLOR[cat] ?? "#71717a",
          highlight: { background: BASIS_COLOR[basis] ?? "#0f172a", border: "#0f172a" },
        },
        borderWidth: isHighlighted ? 4 : 2,
        size: isHighlighted ? 16 : 10,
        font: { color: isHighlighted ? "#0f172a" : "#27272a", size: isHighlighted ? 12 : 11 },
        group: cat,
      };
    });

    // Also add brand nodes if sponsorship edges exist and edge type enabled
    const brandNodes: any[] = [];
    if (edgeTypes.has("sponsorship") && sponsorEdges.length > 0) {
      const brandIdsInView = new Set<string>();
      sponsorEdges.forEach((e) => {
        if (e.weight >= weightThreshold) brandIdsInView.add(e.brand_id);
      });
      // only brands that connect to filtered creators will be shown anyway via edges filter
      brandIdsInView.forEach((bid) => {
        brandNodes.push({
          id: `brand:${bid}`,
          label: `brand ${bid.slice(0, 6)}`,
          title: `brand ${bid}`,
          shape: "square",
          color: { background: "#f4f4f5", border: "#a1a1aa", highlight: { background: "#e4e4e7", border: "#0f172a" } },
          borderWidth: 2,
          size: 14,
          font: { size: 10, color: "#52525b" },
        });
      });
    }

    // Edge filter
    const edgesArray: any[] = [];
    if (edgeTypes.has("collab")) {
      collabEdges.forEach((e: any) => {
        if (e.weight < weightThreshold) return;
        if (!filteredIds.has(e.source_creator_id) || !filteredIds.has(e.target_creator_id)) return;
        edgesArray.push({
          id: `collab:${e.source_creator_id}-${e.target_creator_id}`,
          from: e.source_creator_id,
          to: e.target_creator_id,
          label: e.weight > 1 ? String(e.weight) : undefined,
          width: Math.min(4, 1 + (e.weight - 1) * 1.2),
          color: { color: "#a78bfa", highlight: "#7c3aed" },
          dashes: false,
          title: `collaborates_with weight ${e.weight}`,
        });
      });
    }
    if (edgeTypes.has("coOccurrence")) {
      coEdges.forEach((e: any) => {
        if (e.weight < weightThreshold) return;
        if (!filteredIds.has(e.source_creator_id) || !filteredIds.has(e.target_creator_id)) return;
        edgesArray.push({
          id: `co:${e.source_creator_id}-${e.target_creator_id}`,
          from: e.source_creator_id,
          to: e.target_creator_id,
          width: 1,
          color: { color: "#94a3b8", highlight: "#475569", opacity: 0.7 },
          dashes: [4, 4],
          title: `co_occurs_with weight ${e.weight}`,
        });
      });
    }
    if (edgeTypes.has("sponsorship")) {
      sponsorEdges.forEach((e: any) => {
        if (e.weight !== undefined && e.weight < weightThreshold) return;
        if (!filteredIds.has(e.creator_id)) return;
        // e.brand_id -> creator_id
        const brandNodeId = `brand:${e.brand_id}`;
        // only add if brand node exists in brandNodes
        edgesArray.push({
          id: `spon:${e.brand_id}-${e.creator_id}-${e.content_id}`,
          from: brandNodeId,
          to: e.creator_id,
          width: 1.5,
          color: { color: "#facc15", highlight: "#eab308" },
          dashes: false,
          title: `sponsors ${e.platform} ${e.content_id}`,
        });
      });
    }

    // Update DataSets atomically
    nodesDataSetRef.current!.clear();
    edgesDataSetRef.current!.clear();
    nodesDataSetRef.current!.add([...nodesArray, ...brandNodes]);
    edgesDataSetRef.current!.add(edgesArray);
  }, [creators, collabEdges, coEdges, sponsorEdges, search, selectedBases, edgeTypes, categoryFilter, weightThreshold, highlightedIds, basisById]);

  const toggleBasis = (b: SpilloverBasis) => {
    setSelectedBases((prev) => {
      const n = new Set(prev);
      if (n.has(b)) n.delete(b);
      else n.add(b);
      return n;
    });
  };
  const toggleEdgeType = (t: string) => {
    setEdgeTypes((prev) => {
      const n = new Set(prev);
      if (n.has(t)) n.delete(t);
      else n.add(t);
      return n;
    });
  };

  if (loading) return <div className="rounded-md border border-zinc-200 bg-zinc-50 px-4 py-6 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900">Loading graph — 259 creators, 340 collaborations + 1,414 co-occurrences + 16 sponsorships…</div>;
  if (error) return <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>;

  return (
    <div className="flex flex-col gap-3">
      {/* Filters bar */}
      <div className="flex flex-col gap-3 rounded-md border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name — e.g. LeBron"
              className="w-56 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm placeholder:text-zinc-400 dark:border-zinc-700 dark:bg-zinc-800"
            />
            <span className="text-xs text-zinc-500">
              {creators.length} nodes, {collabEdges.length + coEdges.length} creator↔creator + {sponsorEdges.length} brand edges
            </span>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-zinc-500">Category</label>
            <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-800">
              <option value="all">all</option>
              <option value="athlete">athlete</option>
              <option value="team">team</option>
              <option value="league">league</option>
              <option value="fitness_influencer">fitness_influencer</option>
              <option value="lifestyle_influencer">lifestyle_influencer</option>
              <option value="other">other</option>
            </select>
            <label className="text-xs text-zinc-500">weight ≥</label>
            <input type="range" min={1} max={3} step={1} value={weightThreshold} onChange={(e) => setWeightThreshold(Number(e.target.value))} className="w-20" />
            <span className="text-xs tabular-nums">{weightThreshold}</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-zinc-600">Basis:</span>
          {(["trained", "inferred", "isolated", "placeholder"] as SpilloverBasis[]).map((b) => (
            <label key={b} className="inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs">
              <input type="checkbox" checked={selectedBases.has(b)} onChange={() => toggleBasis(b)} className="h-3 w-3" />
              <span style={{ color: BASIS_COLOR[b] }}>●</span> {b}
            </label>
          ))}
          {selectedBases.size > 0 && <button onClick={() => setSelectedBases(new Set())} className="text-xs underline">clear</button>}
          <span className="ml-4 text-xs font-medium text-zinc-600">Edges:</span>
          <label className="inline-flex items-center gap-1 text-xs"><input type="checkbox" checked={edgeTypes.has("collab")} onChange={() => toggleEdgeType("collab")} /> collaborates</label>
          <label className="inline-flex items-center gap-1 text-xs"><input type="checkbox" checked={edgeTypes.has("coOccurrence")} onChange={() => toggleEdgeType("coOccurrence")} /> co‑occurs</label>
          <label className="inline-flex items-center gap-1 text-xs"><input type="checkbox" checked={edgeTypes.has("sponsorship")} onChange={() => toggleEdgeType("sponsorship")} /> sponsorship</label>
          {highlightedIds.size > 0 && <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">{highlightedIds.size} recommended haloed ★ (max_results up to 50)</span>}
        </div>
        <p className="text-[11px] leading-relaxed text-zinc-500">
          All 259 creators are loaded. The active recommendation set (whatever `POST /recommendations` last returned — default 10, cap 50 — is the ~54‑pair GAIL supervision is distinct from this per‑query size) is haloed. Search focuses + filters narrow the view; weight ≥2 shows stronger collaborations only. Brand squares are `sponsors` edges (16 live via `GET /feature-store/edges/sponsorships`, populated by `POST /labeling/run` disclose extraction).
        </p>
      </div>

      <div ref={containerRef} className="h-[560px] w-full rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900" />

      <p className="text-[11px] text-zinc-500">
        Drag to pan, scroll to zoom, click a node to focus. Data: 340 collaborations + 1,414 co‑occurrences + 16 sponsorships via <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">GET /feature-store/edges/*</code>, GAIL checkpoint <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">c6488a6</code>. Physics: forceAtlas2Based.
      </p>
    </div>
  );
}
