"use client";

import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, type SimulationLinkDatum, type SimulationNodeDatum } from "d3-force";
import { useEffect, useMemo, useState } from "react";
import { getCoOccurrenceEdges, getCollaborationEdges, getCreatorSummaries, postRecommendations } from "@/lib/api";
import type { GraphEdge, InfluencerRecommendation } from "@/types";

// Campaign Simulator (22 Nov 2026, idea 2 of 3 Nov). Part 1 (real): a portfolio of creators under budget, skipping
// creators directly linked to one already chosen (overlapping audiences). Part 2 (real): their network neighbourhood from
// the live edges. Part 3 (SIMULATED, labelled): a what-if ripple of a controversy through that network with ASSUMED
// spread rates. The project's real test (NEGATIVE_SPILLOVER_PLAN_14NOV.md: 368 bad moments, 2,549 pairs) found no
// measurable harm to linked creators, and the page says so.

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
const rupees = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

type Node = SimulationNodeDatum & { id: string; name: string; chosen: boolean };
type Link = SimulationLinkDatum<Node> & { kind: "collab" | "cooc" };
type Pick = { r: InfluencerRecommendation; cost: number };

function pickPortfolio(results: InfluencerRecommendation[], budget: number, linked: (a: string, b: string) => boolean) {
  const chosen: Pick[] = [];
  const skipped: { name: string; reason: string }[] = [];
  let left = budget;
  for (const r of [...results].sort((a, b) => b.final_score - a.final_score)) {
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
function ripple(sourceId: string, links: Link[]) {
  const adj = new Map<string, { to: string; w: number }[]>();
  for (const l of links) {
    const a = (l.source as Node).id ?? (l.source as unknown as string);
    const b = (l.target as Node).id ?? (l.target as unknown as string);
    const w = PASS[l.kind];
    adj.set(a, [...(adj.get(a) ?? []), { to: b, w }]);
    adj.set(b, [...(adj.get(b) ?? []), { to: a, w }]);
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
  const [plan, setPlan] = useState<ReturnType<typeof pickPortfolio> | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [day, setDay] = useState(0);
  const [playing, setPlaying] = useState(false);

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

  async function buildPlan() {
    setBusy(true);
    setError(null);
    try {
      const res = await postRecommendations({ product_category: brief, budget, max_results: 50 });
      setPlan(pickPortfolio(res.results, budget, (a, b) => linkSet.has(`${a}|${b}`)));
      setSource(null);
      setDay(0);
    } catch {
      setError("Couldn't reach the backend at " + (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000") + ".");
    } finally {
      setBusy(false);
    }
  }

  // Network neighbourhood of the portfolio (chosen creators + direct neighbours), laid out once with d3-force.
  const graph = useMemo(() => {
    if (!plan || !edges) return null;
    const chosen = new Set(plan.chosen.map((c) => c.r.creator_id));
    const raw: { a: string; b: string; kind: "collab" | "cooc" }[] = [
      ...edges.collab.map((e) => ({ a: e.source_creator_id, b: e.target_creator_id, kind: "collab" as const })),
      ...edges.cooc.map((e) => ({ a: e.source_creator_id, b: e.target_creator_id, kind: "cooc" as const })),
    ].filter((e) => chosen.has(e.a) || chosen.has(e.b));
    const ids = new Set<string>(chosen);
    for (const e of raw) {
      if (ids.size >= 70) break;
      ids.add(e.a);
      ids.add(e.b);
    }
    const nodes: Node[] = [...ids].map((id) => ({
      id,
      name: plan.chosen.find((c) => c.r.creator_id === id)?.r.name ?? names.get(id) ?? "creator",
      chosen: chosen.has(id),
    }));
    const seen = new Set<string>();
    const links: Link[] = [];
    for (const e of raw) {
      const k = [e.a, e.b].sort().join("|");
      if (!ids.has(e.a) || !ids.has(e.b) || seen.has(k)) continue;
      seen.add(k);
      links.push({ source: e.a, target: e.b, kind: e.kind });
    }
    const sim = forceSimulation<Node>(nodes)
      .force("link", forceLink<Node, Link>(links).id((d) => d.id).distance(60))
      .force("charge", forceManyBody().strength(-90))
      .force("center", forceCenter(W / 2, H / 2))
      .force("collide", forceCollide(14))
      .stop();
    for (let i = 0; i < 300; i++) sim.tick();
    for (const n of nodes) {
      n.x = Math.max(20, Math.min(W - 20, n.x ?? W / 2));
      n.y = Math.max(20, Math.min(H - 20, n.y ?? H / 2));
    }
    return { nodes, links };
  }, [plan, edges, names]);

  const days = useMemo(() => (source && graph ? ripple(source, graph.links) : null), [source, graph]);
  const risk = days?.[day] ?? null;

  const animating = playing && day < DAYS;
  useEffect(() => {
    if (!animating) return;
    const t = setTimeout(() => setDay((d) => d + 1), 900);
    return () => clearTimeout(t);
  }, [animating, day]);

  function startRipple(id: string) {
    setSource(id);
    setDay(0);
    setPlaying(true);
  }

  const affected = plan && risk ? plan.chosen.filter((c) => c.r.creator_id !== source && (risk.get(c.r.creator_id) ?? 0) >= 0.1) : [];

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
        <label className="flex flex-col gap-1 text-xs text-zinc-400">
          Budget (₹)
          <input
            type="number"
            min={10000}
            step={10000}
            value={budget}
            onChange={(e) => setBudget(Math.max(10000, Number(e.target.value) || 0))}
            className="w-40 rounded-md border border-line bg-background px-3 py-2 text-sm text-zinc-100"
          />
        </label>
        <button onClick={buildPlan} disabled={busy || !edges} className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background disabled:opacity-50">
          {busy ? "Planning…" : "Build portfolio"}
        </button>
        {error && <p className="w-full text-sm text-red-400">{error}</p>}
      </section>

      {plan && (
        <section className="grid gap-4 lg:grid-cols-[1fr_1.6fr]">
          <div className="rounded-xl border border-line bg-panel p-4">
            <h2 className="text-sm font-semibold text-zinc-100">Your portfolio</h2>
            <p className="mt-1 text-xs text-zinc-500">
              Highest scores first, within budget, never two creators who are directly linked (their audiences overlap).
            </p>
            {plan.chosen.length === 0 ? (
              <p className="mt-3 text-sm text-zinc-400">No creator fits this budget. Try a larger budget.</p>
            ) : (
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-zinc-500">
                    <th className="py-1 font-normal">Creator</th>
                    <th className="py-1 text-right font-normal">Score</th>
                    <th className="py-1 text-right font-normal">Est. cost</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.chosen.map((c) => (
                    <tr key={c.r.creator_id} className="border-t border-line/60">
                      <td className="py-1.5 text-zinc-100">{c.r.name}</td>
                      <td className="py-1.5 text-right font-mono text-zinc-100">{c.r.final_score.toFixed(1)}</td>
                      <td className="py-1.5 text-right font-mono text-zinc-300">{rupees(c.cost)}</td>
                    </tr>
                  ))}
                  <tr className="border-t border-line text-xs">
                    <td className="py-1.5 text-zinc-400">{plan.chosen.length} creators</td>
                    <td />
                    <td className="py-1.5 text-right font-mono text-zinc-100">
                      {rupees(plan.spent)} of {rupees(budget)}
                    </td>
                  </tr>
                </tbody>
              </table>
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
            <p className="mt-3 text-[11px] text-zinc-500">Costs are estimates from published rate cards.</p>
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
            {graph && graph.nodes.length > 0 ? (
              <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 block h-auto w-full" role="img" aria-label="Creator network around the portfolio">
                {graph.links.map((l, i) => (
                  <line
                    key={i}
                    x1={(l.source as Node).x}
                    y1={(l.source as Node).y}
                    x2={(l.target as Node).x}
                    y2={(l.target as Node).y}
                    stroke={l.kind === "collab" ? "#8497aa" : "#2e3c4a"}
                    strokeWidth={l.kind === "collab" ? 1.5 : 1}
                  />
                ))}
                {graph.nodes.map((n) => {
                  const r = risk?.get(n.id) ?? 0;
                  return (
                    <g key={n.id} onClick={() => startRipple(n.id)} style={{ cursor: "pointer" }}>
                      <circle cx={n.x} cy={n.y} r={14} fill="transparent" />
                      <circle
                        cx={n.x}
                        cy={n.y}
                        r={n.chosen ? 9 : 6}
                        fill={r > 0 ? "#d95926" : n.chosen ? "var(--accent)" : "#4a5b6d"}
                        fillOpacity={r > 0 ? 0.25 + 0.75 * r : 1}
                        stroke={n.id === source ? "#f2f6fa" : "var(--panel)"}
                        strokeWidth={2}
                      />
                      <title>{`${n.name}${r > 0 ? ` · simulated risk ${Math.round(r * 100)}%` : ""}`}</title>
                      {n.chosen && (
                        <text x={(n.x ?? 0) + 12} y={(n.y ?? 0) + 4} fontSize="13" fill="var(--foreground)" style={{ pointerEvents: "none" }}>
                          {n.name}
                        </text>
                      )}
                    </g>
                  );
                })}
              </svg>
            ) : (
              <p className="mt-3 text-sm text-zinc-400">These creators have no recorded links: a controversy at one would not reach the others.</p>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-zinc-400">
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-accent" /> in your portfolio
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "#4a5b6d" }} /> linked creator
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "#d95926" }} /> simulated risk (darker = more)
              </span>
            </div>
            {source && (
              <div className="mt-3 flex flex-wrap items-center gap-3 rounded-md border border-line bg-background p-3 text-sm">
                <span className="text-zinc-300">
                  Day <span className="font-mono text-zinc-50">{day}</span> of {DAYS}
                </span>
                <input type="range" min={0} max={DAYS} value={day} onChange={(e) => { setPlaying(false); setDay(Number(e.target.value)); }} aria-label="Day" />
                <button onClick={() => { setDay(0); setPlaying(true); }} className="rounded-md border border-line px-3 py-1 text-xs text-zinc-200 hover:border-accent hover:text-accent">
                  ▶ Replay
                </button>
                <span className="w-full text-zinc-400">
                  {affected.length === 0
                    ? "None of your other portfolio creators is reached in this what-if."
                    : `Reached in this what-if: ${affected.map((c) => `${c.r.name} (${Math.round((risk?.get(c.r.creator_id) ?? 0) * 100)}%)`).join(", ")}.`}
                </span>
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
