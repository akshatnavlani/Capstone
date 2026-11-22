"use client";

import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";
import { useEffect, useMemo, useRef, useState } from "react";
import { getCoOccurrenceEdges, getCollaborationEdges, getCreatorSummaries, postRecommendations } from "@/lib/api";
import type { GraphEdge, InfluencerRecommendation } from "@/types";

// Campaign Simulator (22 Nov 2026, idea 2 of 3 Nov). Part 1 (real): a portfolio of creators under budget, skipping
// creators directly linked to one already chosen (overlapping audiences). Part 2 (real): their network neighbourhood from
// the live edges. Part 3 (SIMULATED, labelled): a what-if ripple of a controversy through that network with ASSUMED
// spread rates. The project's real test (NEGATIVE_SPILLOVER_PLAN_14NOV.md: 368 bad moments, 2,549 pairs) found no
// measurable harm to linked creators, and the page says so.
//
// 22 Nov (interactive version): one backend call per brief at the slider's top budget (a call takes 15-25 s), then the
// budget slider and the remove buttons re-pick the portfolio instantly in the browser. Checked on "Fitness and gym": the
// picks at Rs 1L and Rs 3L from that one call equal the picks from a call at that budget, with identical scores.

const BRIEFS = [
  { label: "Fitness and gym", value: "fitness gym workout" },
  { label: "Protein and supplements", value: "protein supplement whey nutrition" },
  { label: "Yoga, meditation and wellness", value: "yoga meditation wellness" },
  { label: "Running and sports shoes", value: "shoes running sneakers footwear marathon" },
  { label: "Healthy food and nutrition", value: "healthy food nutrition diet protein recipe" },
];
const PASS = { collab: 0.4, cooc: 0.2 }; // ASSUMED share of risk passed along a link per day (what-if only)
const DAYS = 5;
const W = 900, H = 520;
const MIN_BUDGET = 100000, MAX_BUDGET = 1000000, STEP = 25000;
const rupees = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
const PLATFORM: Record<string, string> = { youtube: "YouTube", instagram: "Instagram" };

type GNode = { id: string; name: string; chosen: boolean };
type GLink = { a: string; b: string; kind: "collab" | "cooc" };
type SimNode = SimulationNodeDatum & { id: string };
type Pick = { r: InfluencerRecommendation; cost: number };

function pickPortfolio(results: InfluencerRecommendation[], budget: number, removed: Set<string>, linked: (a: string, b: string) => boolean) {
  const chosen: Pick[] = [];
  const skipped: { name: string; reason: string }[] = [];
  let left = budget;
  for (const r of [...results].sort((a, b) => b.final_score - a.final_score)) {
    if (removed.has(r.creator_id)) continue;
    const cost = r.value?.cost_mid_inr ?? r.estimated_cost ?? 0;
    if (cost <= 0) continue;
    const clash = chosen.find((c) => linked(c.r.creator_id, r.creator_id));
    if (clash) {
      skipped.push({ name: r.name, reason: `shares an audience link with ${clash.r.name}` });
      continue;
    }
    if (cost > left) continue;
    chosen.push({ r, cost });
    left -= cost;
    if (chosen.length >= 8) break;
  }
  return { chosen, skipped: skipped.slice(0, 5), spent: budget - left };
}

/** Day-by-day risk: the source starts at 1; each day a node takes the largest (neighbour risk × assumed pass rate). */
function ripple(sourceId: string, links: GLink[]) {
  const adj = new Map<string, { to: string; w: number }[]>();
  for (const l of links) {
    const w = PASS[l.kind];
    adj.set(l.a, [...(adj.get(l.a) ?? []), { to: l.b, w }]);
    adj.set(l.b, [...(adj.get(l.b) ?? []), { to: l.a, w }]);
  }
  const days: Map<string, number>[] = [new Map([[sourceId, 1]])];
  for (let d = 1; d <= DAYS; d++) {
    const prev = days[d - 1];
    const next = new Map(prev);
    for (const [id, risk] of prev) {
      for (const { to, w } of adj.get(id) ?? []) next.set(to, Math.max(next.get(to) ?? 0, risk * w));
    }
    days.push(next);
  }
  return days;
}

export default function SimulatorPage() {
  const [brief, setBrief] = useState(BRIEFS[0].value);
  const [budget, setBudget] = useState(300000);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [edges, setEdges] = useState<{ collab: GraphEdge[]; cooc: GraphEdge[] } | null>(null);
  const [names, setNames] = useState<Map<string, string>>(new Map());
  const [results, setResults] = useState<{ brief: string; list: InfluencerRecommendation[] } | null>(null);
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [day, setDay] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [pos, setPos] = useState<Map<string, { x: number; y: number }>>(new Map());
  const posRef = useRef(pos);

  useEffect(() => {
    Promise.all([getCollaborationEdges(), getCoOccurrenceEdges()])
      .then(([collab, cooc]) => setEdges({ collab, cooc }))
      .catch(() => setError("Couldn't load the creator network from the backend."));
    // Names for linked creators outside the portfolio; the light summary endpoint (under 1 s), not required to plan.
    getCreatorSummaries()
      .then((creators) => setNames(new Map(creators.map((c) => [c.creator_id, c.name]))))
      .catch(() => {});
  }, []);

  const linkSet = useMemo(() => {
    const s = new Set<string>();
    for (const e of [...(edges?.collab ?? []), ...(edges?.cooc ?? [])]) {
      s.add(`${e.source_creator_id}|${e.target_creator_id}`);
      s.add(`${e.target_creator_id}|${e.source_creator_id}`);
    }
    return s;
  }, [edges]);

  async function scoreBrief() {
    setBusy(true);
    setError(null);
    try {
      const res = await postRecommendations({ product_category: brief, budget: MAX_BUDGET, max_results: 50 });
      setResults({ brief, list: res.results });
      setRemoved(new Set());
      setSource(null);
      setDay(0);
    } catch {
      setError("Couldn't reach the backend at " + (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000") + ".");
    } finally {
      setBusy(false);
    }
  }

  const plan = useMemo(
    () => (results ? pickPortfolio(results.list, budget, removed, (a, b) => linkSet.has(`${a}|${b}`)) : null),
    [results, budget, removed, linkSet],
  );

  // Network neighbourhood of the portfolio: chosen creators + direct neighbours (max 70 nodes).
  const graph = useMemo(() => {
    if (!plan || !edges) return null;
    const chosen = new Set(plan.chosen.map((c) => c.r.creator_id));
    const raw: GLink[] = [
      ...edges.collab.map((e) => ({ a: e.source_creator_id, b: e.target_creator_id, kind: "collab" as const })),
      ...edges.cooc.map((e) => ({ a: e.source_creator_id, b: e.target_creator_id, kind: "cooc" as const })),
    ].filter((e) => chosen.has(e.a) || chosen.has(e.b));
    const ids = new Set<string>(chosen);
    for (const e of raw) {
      if (ids.size >= 70) break;
      ids.add(e.a);
      ids.add(e.b);
    }
    const nodes: GNode[] = [...ids].map((id) => ({
      id,
      name: plan.chosen.find((c) => c.r.creator_id === id)?.r.name ?? names.get(id) ?? "creator",
      chosen: chosen.has(id),
    }));
    const seen = new Set<string>();
    const links: GLink[] = [];
    for (const e of raw) {
      const k = [e.a, e.b].sort().join("|");
      if (!ids.has(e.a) || !ids.has(e.b) || seen.has(k)) continue;
      seen.add(k);
      links.push(e);
    }
    return { nodes, links };
  }, [plan, edges, names]);

  // Live force layout: creators drift into place; creators already on the map keep their spot when the portfolio changes.
  useEffect(() => {
    if (!graph) return;
    const prev = posRef.current;
    const nodes: SimNode[] = graph.nodes.map((n) => ({
      id: n.id,
      x: prev.get(n.id)?.x ?? W / 2 + (Math.random() - 0.5) * 120,
      y: prev.get(n.id)?.y ?? H / 2 + (Math.random() - 0.5) * 120,
    }));
    const links = graph.links.map((l) => ({ source: l.a, target: l.b }));
    const sim = forceSimulation<SimNode>(nodes)
      .force("link", forceLink<SimNode, { source: string; target: string }>(links).id((d) => d.id).distance(60))
      .force("charge", forceManyBody().strength(-260).distanceMax(400))
      .force("x", forceX(W / 2).strength(0.03))
      .force("y", forceY(H / 2).strength(0.05))
      .force("collide", forceCollide(16))
      .alpha(prev.size ? 0.6 : 1);
    const publish = () => {
      for (const n of nodes) {
        n.x = Math.max(24, Math.min(W - 24, n.x ?? W / 2));
        n.y = Math.max(24, Math.min(H - 24, n.y ?? H / 2));
      }
      const m = new Map(nodes.map((n) => [n.id, { x: n.x as number, y: n.y as number }]));
      posRef.current = m;
      setPos(m);
    };
    let frame = 0;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      sim.stop();
      for (let i = 0; i < 300; i++) sim.tick();
      frame = requestAnimationFrame(publish);
    } else {
      sim.on("tick", publish);
    }
    return () => {
      sim.stop();
      cancelAnimationFrame(frame);
    };
  }, [graph]);

  const days = useMemo(() => (source && graph ? ripple(source, graph.links) : null), [source, graph]);
  const risk = days?.[day] ?? null;
  const prevRisk = days && day > 0 ? days[day - 1] : null;

  const animating = playing && day < DAYS;
  useEffect(() => {
    if (!animating) return;
    const t = setTimeout(() => setDay((d) => d + 1), 1100);
    return () => clearTimeout(t);
  }, [animating, day]);

  function startRipple(id: string) {
    setSource(id);
    setDay(0);
    setPlaying(true);
  }

  function removeCreator(id: string) {
    setRemoved((s) => new Set(s).add(id));
    if (source === id) setSource(null);
  }

  const affected = plan && risk ? plan.chosen.filter((c) => c.r.creator_id !== source && (risk.get(c.r.creator_id) ?? 0) >= 0.1) : [];
  const others = plan ? plan.chosen.length - (source && plan.chosen.some((c) => c.r.creator_id === source) ? 1 : 0) : 0;
  const standalone = plan && graph ? plan.chosen.filter((c) => !graph.links.some((l) => l.a === c.r.creator_id || l.b === c.r.creator_id)).length : 0;

  // Hover: the hovered creator, its links and its neighbours stay bright; the rest dims.
  const near = useMemo(() => {
    if (!hover || !graph) return null;
    const s = new Set([hover]);
    for (const l of graph.links) {
      if (l.a === hover) s.add(l.b);
      if (l.b === hover) s.add(l.a);
    }
    return s;
  }, [hover, graph]);
  const hoverNode = hover && graph ? graph.nodes.find((n) => n.id === hover) : undefined;
  const hoverPos = hover ? pos.get(hover) : undefined;
  const hoverPick = hover && plan ? plan.chosen.find((c) => c.r.creator_id === hover) : undefined;
  const hoverLinkedTo =
    hover && graph && plan
      ? graph.links
          .filter((l) => l.a === hover || l.b === hover)
          .map((l) => ({ other: l.a === hover ? l.b : l.a, kind: l.kind }))
          .filter((x) => plan.chosen.some((c) => c.r.creator_id === x.other))
          .map((x) => `${plan.chosen.find((c) => c.r.creator_id === x.other)?.r.name} (${x.kind === "collab" ? "collaboration" : "appeared together"})`)
      : [];

  // Particles for the current day: risk hopping from a creator reached yesterday to a neighbour whose risk rises today.
  const hops =
    graph && risk && prevRisk
      ? graph.links.flatMap((l) => {
          const out: { from: string; to: string }[] = [];
          for (const [f, t] of [[l.a, l.b], [l.b, l.a]] as const) {
            if ((prevRisk.get(f) ?? 0) > 0 && (risk.get(t) ?? 0) > (prevRisk.get(t) ?? 0)) out.push({ from: f, to: t });
          }
          return out;
        })
      : [];

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-12">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-signal">Plan a campaign · what-if risk</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
          Campaign Simulator
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-zinc-400">
          Build a creator portfolio within your budget, see how the creators are connected, and play out what could happen if one
          of them hits a controversy.
        </p>
      </header>

      <section className="flex flex-wrap items-end gap-4 rounded-xl border border-line bg-panel p-4">
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
        <label className="flex min-w-[260px] flex-1 flex-col gap-1 text-xs text-zinc-400">
          <span className="flex justify-between">
            <span>Budget</span>
            <span className="font-mono text-sm text-zinc-50">{rupees(budget)}</span>
          </span>
          <input
            type="range"
            min={MIN_BUDGET}
            max={MAX_BUDGET}
            step={STEP}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            className="accent-[var(--accent)]"
            aria-label="Budget"
          />
          <span className="flex justify-between text-[10px] text-zinc-500">
            <span>{rupees(MIN_BUDGET)}</span>
            <span>{results ? "drag: the portfolio updates instantly" : ""}</span>
            <span>{rupees(MAX_BUDGET)}</span>
          </span>
        </label>
        <button onClick={scoreBrief} disabled={busy || !edges} className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background disabled:opacity-50">
          {busy ? "Scoring creators…" : results && results.brief === brief ? "Rebuild portfolio" : "Build portfolio"}
        </button>
        {error && <p className="w-full text-sm text-red-400">{error}</p>}
        {busy && (
          <div className="w-full">
            <div className="h-1 overflow-hidden rounded-full bg-line">
              <div className="sim-loading h-full w-1/3 rounded-full bg-accent" />
            </div>
            <p className="mt-1 text-xs text-zinc-500">Scoring every creator for this brief (takes about 20 seconds).</p>
          </div>
        )}
      </section>

      {plan && (
        <section className="grid gap-4 lg:grid-cols-[1fr_1.6fr]">
          <div className="rounded-xl border border-line bg-panel p-4">
            <h2 className="text-sm font-semibold text-zinc-100">Your portfolio</h2>
            <p className="mt-1 text-xs text-zinc-500">
              Highest scores first, within budget, never two creators who are directly linked (their audiences overlap).
            </p>
            <div className="mt-3">
              <div className="flex justify-between text-xs text-zinc-400">
                <span>Budget used</span>
                <span className="font-mono text-zinc-100">
                  {rupees(plan.spent)} <span className="text-zinc-500">of {rupees(budget)}</span>
                </span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-line">
                <div className="h-full rounded-full bg-accent transition-[width] duration-700 ease-out" style={{ width: `${Math.min(100, (plan.spent / budget) * 100)}%` }} />
              </div>
            </div>
            {plan.chosen.length === 0 ? (
              <p className="mt-3 text-sm text-zinc-400">No creator fits this budget. Try a larger budget.</p>
            ) : (
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-zinc-500">
                    <th className="py-1 font-normal">Creator</th>
                    <th className="py-1 text-right font-normal">Score</th>
                    <th className="py-1 text-right font-normal">Est. cost per post</th>
                    <th className="w-6" />
                  </tr>
                </thead>
                <tbody>
                  {plan.chosen.map((c, i) => (
                    <tr
                      key={c.r.creator_id}
                      onMouseEnter={() => setHover(c.r.creator_id)}
                      onMouseLeave={() => setHover(null)}
                      className={`sim-row border-t border-line/60 transition-colors ${hover === c.r.creator_id ? "bg-accent/10" : ""}`}
                      style={{ animationDelay: `${i * 110}ms` }}
                    >
                      <td className="py-1.5 text-zinc-100">
                        <button onClick={() => startRipple(c.r.creator_id)} className="text-left hover:text-accent" title="Play out a controversy for this creator">
                          {c.r.name}
                        </button>
                      </td>
                      <td className="py-1.5 text-right font-mono text-zinc-100">{c.r.final_score.toFixed(1)}</td>
                      <td className="py-1.5 text-right">
                        <div className="font-mono text-zinc-300">{rupees(c.cost)}</div>
                        {c.r.value && (
                          <div className="text-[10px] text-zinc-500">
                            {PLATFORM[c.r.value.platform] ?? c.r.value.platform}
                            {c.r.value.cost_tier ? ` · ${c.r.value.cost_tier}` : ""}
                          </div>
                        )}
                      </td>
                      <td className="py-1.5 pl-2 text-right">
                        <button
                          onClick={() => removeCreator(c.r.creator_id)}
                          className="rounded px-1 text-zinc-500 hover:bg-line hover:text-zinc-100"
                          aria-label={`Remove ${c.r.name}`}
                          title="Remove: the next best creator takes the place"
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  ))}
                  <tr className="border-t border-line text-xs">
                    <td className="py-1.5 text-zinc-400" colSpan={4}>
                      {plan.chosen.length} creators
                    </td>
                  </tr>
                </tbody>
              </table>
            )}
            {removed.size > 0 && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                Removed by you:
                {[...removed].map((id) => (
                  <button
                    key={id}
                    onClick={() => setRemoved((s) => { const n = new Set(s); n.delete(id); return n; })}
                    className="rounded-full border border-line px-2 py-0.5 text-zinc-300 hover:border-accent hover:text-accent"
                    title="Put back"
                  >
                    {results?.list.find((r) => r.creator_id === id)?.name ?? "creator"} ↺
                  </button>
                ))}
              </div>
            )}
            {plan.skipped.length > 0 && (
              <div className="mt-3 text-xs text-zinc-500">
                <div className="font-medium text-zinc-400">Skipped to avoid audience overlap</div>
                <ul className="mt-1 list-disc pl-4">
                  {plan.skipped.map((s) => (
                    <li key={s.name}>
                      {s.name}: {s.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="mt-3 text-[11px] text-zinc-500">
              Estimated price of one post on the platform shown, from published rate cards by audience size (nano under 10k, micro
              10k–100k, mid 100k–500k, macro 500k–2M). Creators of the same size share an estimate.
            </p>
          </div>

          <div className="rounded-xl border border-line bg-panel p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-zinc-100">Network around your portfolio</h2>
              <span className="rounded-full border border-accent/50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-accent">
                What-if · simulated
              </span>
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              Click a creator to play out a controversy: risk spreads along links day by day (assumed rates: {PASS.collab * 100}% per day
              along a collaboration, {PASS.cooc * 100}% along a co-appearance).
            </p>
            {!source && plan.chosen.length > 0 && (
              <p className="mt-2 inline-flex items-center gap-2 rounded-full border border-line px-3 py-1 text-xs text-zinc-300">
                <span className="sim-hint-dot inline-block h-2 w-2 rounded-full bg-accent" /> Click a yellow creator to start the what-if
              </p>
            )}
            {graph && (
              <div className="relative mt-2">
                <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" aria-label="Creator network around the portfolio" onMouseLeave={() => setHover(null)}>
                  {graph.links.map((l) => {
                    const p = pos.get(l.a), q = pos.get(l.b);
                    if (!p || !q) return null;
                    const lit = hover && (l.a === hover || l.b === hover);
                    const hot = risk && (risk.get(l.a) ?? 0) > 0 && (risk.get(l.b) ?? 0) > 0;
                    return (
                      <line
                        key={`${l.a}|${l.b}`}
                        x1={p.x}
                        y1={p.y}
                        x2={q.x}
                        y2={q.y}
                        stroke={hot ? "#d95926" : lit ? "var(--accent)" : l.kind === "collab" ? "#8497aa" : "#2e3c4a"}
                        strokeWidth={lit || hot ? 2 : l.kind === "collab" ? 1.5 : 1}
                        strokeOpacity={hover && !lit ? 0.15 : hot ? 0.8 : 1}
                        className="transition-[stroke,stroke-opacity] duration-300"
                      />
                    );
                  })}
                  {hops.map((h) => {
                    const p = pos.get(h.from), q = pos.get(h.to);
                    if (!p || !q) return null;
                    return (
                      <circle
                        key={`${day}-${h.from}-${h.to}`}
                        r={4}
                        fill="#f5b83d"
                        className="sim-hop"
                        style={{ "--x0": `${p.x}px`, "--y0": `${p.y}px`, "--x1": `${q.x}px`, "--y1": `${q.y}px` } as React.CSSProperties}
                      />
                    );
                  })}
                  {graph.nodes.map((n) => {
                    const p = pos.get(n.id);
                    if (!p) return null;
                    const r = risk?.get(n.id) ?? 0;
                    const dim = near && !near.has(n.id);
                    return (
                      <g
                        key={n.id}
                        onClick={() => startRipple(n.id)}
                        onMouseEnter={() => setHover(n.id)}
                        style={{ cursor: "pointer", opacity: dim ? 0.25 : 1, transition: "opacity 250ms" }}
                      >
                        {n.id === source && playing && <circle cx={p.x} cy={p.y} r={10} fill="none" stroke="#d95926" strokeWidth={2} className="sim-ping" />}
                        <circle cx={p.x} cy={p.y} r={16} fill="transparent" />
                        <circle
                          cx={p.x}
                          cy={p.y}
                          r={(n.chosen ? 9 : 6) + (hover === n.id ? 3 : 0)}
                          fill={r > 0 ? "#d95926" : n.chosen ? "var(--accent)" : "#4a5b6d"}
                          fillOpacity={r > 0 ? 0.3 + 0.7 * r : 1}
                          stroke={n.id === source ? "#f2f6fa" : "var(--panel)"}
                          strokeWidth={2}
                          className="transition-[r,fill,fill-opacity] duration-500"
                        />
                        {n.chosen && (
                          <text
                            x={p.x + 13}
                            y={p.y + 4}
                            fontSize="13"
                            fill="var(--foreground)"
                            stroke="var(--panel)"
                            strokeWidth={4}
                            paintOrder="stroke"
                            style={{ pointerEvents: "none" }}
                          >
                            {n.name}
                          </text>
                        )}
                        {r > 0 && n.id !== source && (
                          <text
                            x={p.x}
                            y={p.y - (n.chosen ? 15 : 11)}
                            textAnchor="middle"
                            fontSize="11"
                            fontWeight={600}
                            fill="#f2a27f"
                            stroke="var(--panel)"
                            strokeWidth={3}
                            paintOrder="stroke"
                            className="sim-pop"
                            style={{ pointerEvents: "none" }}
                          >
                            {Math.round(r * 100)}%
                          </text>
                        )}
                      </g>
                    );
                  })}
                </svg>
                {hoverNode && hoverPos && (
                  <div
                    className="pointer-events-none absolute z-10 w-60 -translate-x-1/2 rounded-lg border border-line bg-background/95 p-3 text-xs shadow-xl"
                    style={{ left: `${Math.min(85, Math.max(15, (hoverPos.x / W) * 100))}%`, top: `${(hoverPos.y / H) * 100}%`, transform: "translate(-50%, 18px)" }}
                  >
                    <div className="font-semibold text-zinc-50">{hoverNode.name}</div>
                    {hoverPick ? (
                      <div className="mt-1 text-zinc-400">
                        In your portfolio · score <span className="font-mono text-zinc-200">{hoverPick.r.final_score.toFixed(1)}</span> ·{" "}
                        <span className="font-mono text-zinc-200">{rupees(hoverPick.cost)}</span>
                      </div>
                    ) : (
                      <div className="mt-1 text-zinc-400">Connected creator, not in your portfolio</div>
                    )}
                    {hoverLinkedTo.length > 0 && <div className="mt-1 text-zinc-400">Linked to: {hoverLinkedTo.join(", ")}</div>}
                    {risk && (risk.get(hoverNode.id) ?? 0) > 0 && (
                      <div className="mt-1 text-[#f2a27f]">Simulated risk on day {day}: {Math.round((risk.get(hoverNode.id) ?? 0) * 100)}%</div>
                    )}
                    <div className="mt-1 text-zinc-500">Click to play out a controversy here</div>
                  </div>
                )}
              </div>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-zinc-400">
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-accent" /> in your portfolio
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "#4a5b6d" }} /> connected creator
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "#d95926" }} /> simulated risk (darker = more)
              </span>
              {plan.chosen.length > 0 && (
                <span className="text-zinc-500">
                  {standalone} of {plan.chosen.length} portfolio creators stand alone: a problem at one stays with that creator.
                </span>
              )}
            </div>
            {source && (
              <div className="mt-3 rounded-md border border-line bg-background p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="mr-1 text-xs text-zinc-400">Day</span>
                  {Array.from({ length: DAYS + 1 }, (_, d) => (
                    <button
                      key={d}
                      onClick={() => {
                        setPlaying(false);
                        setDay(d);
                      }}
                      className={`h-7 w-7 rounded-full border font-mono text-xs transition-colors ${
                        d === day ? "border-accent bg-accent text-background" : d < day ? "border-accent/50 text-accent" : "border-line text-zinc-400 hover:border-zinc-500"
                      }`}
                    >
                      {d}
                    </button>
                  ))}
                  <button
                    onClick={() => (animating ? setPlaying(false) : (setDay(day >= DAYS ? 0 : day), setPlaying(true)))}
                    className="ml-2 rounded-md border border-line px-3 py-1 text-xs text-zinc-200 hover:border-accent hover:text-accent"
                  >
                    {animating ? "❚❚ Pause" : day >= DAYS ? "▶ Replay" : "▶ Play"}
                  </button>
                  <button onClick={() => setSource(null)} className="rounded-md px-2 py-1 text-xs text-zinc-500 hover:text-zinc-200">
                    Clear
                  </button>
                </div>
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-zinc-400">
                    <span>Your other portfolio creators reached</span>
                    <span className="font-mono text-zinc-100">
                      {affected.length} of {others}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-line">
                    <div className="h-full rounded-full bg-[#d95926] transition-[width] duration-500" style={{ width: `${others ? (affected.length / others) * 100 : 0}%` }} />
                  </div>
                </div>
                <p className="mt-2 text-zinc-400">
                  {affected.length === 0
                    ? "None of your other portfolio creators is reached in this what-if."
                    : `Reached in this what-if: ${affected.map((c) => `${c.r.name} (${Math.round((risk?.get(c.r.creator_id) ?? 0) * 100)}%)`).join(", ")}.`}
                </p>
              </div>
            )}
          </div>
        </section>
      )}

      <p className="text-xs text-zinc-500">
        The portfolio and the network are real data. The spread is a what-if with assumed rates, not a prediction: our real-data
        test of 368 bad audience moments across 2,549 creator pairs found no measurable harm to linked creators.
      </p>
    </main>
  );
}
