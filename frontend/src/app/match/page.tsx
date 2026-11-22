"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import Avatar from "@/components/Avatar";
import { getCoOccurrenceEdges, getCollaborationEdges, postRecommendations } from "@/lib/api";
import type { BrandRecommendationRequest, BrandRecommendationResponse, InfluencerRecommendation } from "@/types";

// Live Match (23 Nov 2026): what a brand sees between pressing "Get Recommendations" and the ranking. The backend takes
// about 15-25 s, so the wait plays the real steps on real data instead of a spinner:
//   before the answer: the brief, the creator map (/niche_map.json, CLIP+BERT -> PCA), the real collaboration and
//   co-appearance links (/feature-store/edges/*), then "scoring" until the answer arrives;
//   after the answer: the returned creators light up by their content-match score, take colours by their real audience
//   mood (score_breakdown.sentiment_risk_score), and the top 3 by final score land on a podium.
// Nothing here is simulated or changes a score. The answer is also saved for /dashboard, as the brief page did.

type Point = { creator_id: string; name: string; niche: string; x: number; y: number };
type Edge = { a: string; b: string };

const NICHES = [
  { name: "Gym and bodybuilding", color: "#3987e5" },
  { name: "Nutrition and health", color: "#d95926" },
  { name: "Yoga and wellness", color: "#199e70" },
  { name: "Sports and athletes", color: "#c98500" },
  { name: "Running and endurance", color: "#d55181" },
  { name: "Lifestyle and other", color: "#0ca30c" },
];
const COLOR = Object.fromEntries(NICHES.map((n) => [n.name, n.color]));
const W = 1000, H = 560, PAD = 30;
const sx = (x: number) => PAD + x * (W - 2 * PAD);
const sy = (y: number) => H - PAD - y * (H - 2 * PAD);
const DUR = [2800, 3200, 3400, 1500, 2800, 2800]; // ms per stage; stage 3 also waits for the answer
const COOL = "#3987e5", WARM = "#f5b83d";

function mix(a: string, b: string, t: number) {
  const p = (h: string, i: number) => parseInt(h.slice(1 + 2 * i, 3 + 2 * i), 16);
  const c = [0, 1, 2].map((i) => Math.round(p(a, i) + (p(b, i) - p(a, i)) * t).toString(16).padStart(2, "0"));
  return `#${c.join("")}`;
}

// The parts of the final score with their real weights (backend/app/fusion.py). With a price estimate the final score is
// 100 x (0.4 value + 0.3 mood + 0.3 content match) minus 10 when mood is below 0.3; the network part then has weight 0.
// A part at exactly 0.5 is the neutral value used when the creator has too little data for it.
const PARTS = [
  { key: "value", label: "Value for money", reason: "Great value for money", color: "#f5b83d" },
  { key: "mood", label: "Audience mood", reason: "Audience comments are very positive", color: "#35d6c0" },
  { key: "fit", label: "Content match", reason: "Strong content match for your product", color: "#3987e5" },
  { key: "network", label: "Network", reason: "Well connected in the creator network", color: "#d55181" },
] as const;
type PartKey = (typeof PARTS)[number]["key"];

function parts(r: InfluencerRecommendation) {
  const b = r.score_breakdown;
  const raw: Record<PartKey, [number, number | null | undefined]> = {
    value: [b.weight_value ?? 0, b.value_score],
    mood: [b.weight_sentiment_risk, b.sentiment_risk_score],
    fit: [b.weight_creator_feature, b.creator_feature_score],
    network: [b.weight_spillover, b.spillover_score],
  };
  return PARTS.filter((p) => raw[p.key][0] > 0 && raw[p.key][1] != null).map((p) => {
    const [w, s] = raw[p.key] as [number, number];
    return { ...p, weight: w, score: s, points: 100 * w * s, neutral: s === 0.5 && p.key !== "value" };
  });
}

function strongest(r: InfluencerRecommendation) {
  const ps = parts(r).filter((p) => !p.neutral);
  return ps.length ? [...ps].sort((x, y) => y.score - x.score)[0].reason : "Good overall fit";
}

export default function LiveMatchPage() {
  const raw = useSyncExternalStore(
    () => () => {},
    () => sessionStorage.getItem("liveMatchRequest"),
    () => null,
  );
  const req = useMemo(() => {
    try {
      return raw ? (JSON.parse(raw) as BrandRecommendationRequest) : null;
    } catch {
      return null;
    }
  }, [raw]);

  const [points, setPoints] = useState<Point[] | null>(null);
  const [edges, setEdges] = useState<Edge[] | null>(null);
  const [result, setResult] = useState<BrandRecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const started = useRef(false);
  const t0 = useRef(0);

  useEffect(() => {
    fetch("/niche_map.json")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setPoints(d.points))
      .catch(() => setPoints([]));
    Promise.all([getCollaborationEdges(), getCoOccurrenceEdges()])
      .then(([c, o]) => setEdges([...c, ...o].map((e) => ({ a: e.source_creator_id, b: e.target_creator_id }))))
      .catch(() => setEdges([]));
  }, []);

  // One request per visit (the ref survives React's development double-mount, so the 20 s call is not sent twice).
  useEffect(() => {
    if (!req || started.current) return;
    started.current = true;
    t0.current = performance.now();
    postRecommendations(req)
      .then((r) => {
        sessionStorage.setItem("recommendationResult", JSON.stringify(r));
        setResult(r);
      })
      .catch(() => setError("Couldn't reach the recommendation service. Is the backend running?"));
  }, [req]);

  useEffect(() => {
    if (result || error || !req) return;
    const id = setInterval(() => setElapsed(Math.round((performance.now() - t0.current) / 1000)), 500);
    return () => clearInterval(id);
  }, [result, error, req]);

  useEffect(() => {
    if (stage >= 6 || error || !req) return;
    if (stage === 3 && !result) return; // keep "scoring" on screen until the answer is here
    const t = setTimeout(() => setStage((s) => s + 1), DUR[stage]);
    return () => clearTimeout(t);
  }, [stage, result, error, req]);

  const byId = useMemo(() => new Map((points ?? []).map((p) => [p.creator_id, p])), [points]);
  const mapEdges = useMemo(() => (edges ?? []).filter((e) => byId.has(e.a) && byId.has(e.b)), [edges, byId]);
  const pulses = useMemo(() => {
    const step = Math.max(1, Math.floor(mapEdges.length / 36));
    return mapEdges.filter((_, i) => i % step === 0).slice(0, 36);
  }, [mapEdges]);

  const results = useMemo(() => result?.results ?? [], [result]);
  const matched = useMemo(() => new Map(results.map((r) => [r.creator_id, r])), [results]);
  const onMap = results.filter((r) => byId.has(r.creator_id)).length;
  const moodRange = useMemo(() => {
    const m = results.map((r) => r.score_breakdown.sentiment_risk_score);
    return m.length ? [Math.min(...m), Math.max(...m)] : [0, 1];
  }, [results]);
  const top = useMemo(() => [...results].sort((a, b) => b.final_score - a.final_score).slice(0, 3), [results]);
  const topIds = new Set(top.map((t) => t.creator_id));

  const words = (req?.product_category ?? "").split(/\s+/).filter(Boolean);
  const STAGES = [
    { title: "Reading your brief", sub: "AI turns your product words into numbers" },
    { title: "Scanning the creator market", sub: `${points?.length ?? "…"} creators, placed by what their content looks and sounds like` },
    { title: "Mapping who works with whom", sub: `${mapEdges.length.toLocaleString()} real collaborations and co-appearances` },
    { title: "Scoring every creator", sub: result ? "Done" : `Content match, audience mood, value for money · ${elapsed}s` },
    { title: "Finding your matches", sub: result ? `${results.length} creators fit your product and budget` : "" },
    { title: "Listening to their audiences", sub: "Warmer colour = more positive comments" },
    { title: "Your top creators", sub: top.length ? `${top.length} best picks` : "" },
  ];

  if (!req) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-start gap-4 px-6 py-16">
        <h1 className="text-2xl font-semibold tracking-tight">Live Match</h1>
        <p className="text-sm text-zinc-400">Start with your product and budget, and watch the match happen live.</p>
        <Link href="/brand-input" className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-background">
          Start a brief
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-5 px-6 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-signal">Live match · real data</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
            Finding your creators
          </h1>
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            {words.map((w) => (
              <span key={w} className="rounded-full border border-line px-2.5 py-0.5 text-zinc-300">
                {w}
              </span>
            ))}
            <span className="rounded-full border border-accent/50 px-2.5 py-0.5 text-accent">₹{Number(req.budget).toLocaleString("en-IN")}</span>
          </div>
        </div>
        {stage < 6 && !error && (
          <button
            onClick={() => setStage(result ? 6 : 3)}
            className="rounded-md border border-line px-3 py-1.5 text-xs text-zinc-400 hover:border-accent hover:text-accent"
          >
            Skip animation
          </button>
        )}
      </header>

      {error && (
        <p className="rounded-md border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}{" "}
          <Link href="/brand-input" className="underline">
            Back to the brief
          </Link>
        </p>
      )}

      <section className="grid gap-4 lg:grid-cols-[250px_1fr]">
        <ol className="flex flex-col gap-1 rounded-xl border border-line bg-panel p-3">
          {STAGES.map((s, i) => {
            const done = i < stage || (stage === STAGES.length - 1 && i === stage), now = i === stage && !done;
            return (
              <li key={s.title} className={`flex gap-3 rounded-lg px-2 py-2 transition-colors ${now ? "bg-accent/10" : ""}`}>
                <span
                  className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full border text-[11px] font-semibold transition-colors ${
                    done ? "border-signal bg-signal text-background" : now ? "border-accent text-accent" : "border-line text-zinc-600"
                  }`}
                >
                  {done ? "✓" : now ? <span className="lm-spin inline-block h-3 w-3 rounded-full border-2 border-accent border-t-transparent" /> : i + 1}
                </span>
                <span className="min-w-0">
                  <span className={`block text-sm ${now ? "font-semibold text-zinc-50" : done ? "text-zinc-300" : "text-zinc-600"}`}>{s.title}</span>
                  {(now || done) && s.sub && <span className="block text-[11px] text-zinc-500">{s.sub}</span>}
                </span>
              </li>
            );
          })}
        </ol>

        <div className="relative overflow-hidden rounded-xl border border-line bg-panel">
          <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" aria-label="Live match on the creator map">
            <defs>
              <linearGradient id="lm-sweep-g" x1="0" x2="1">
                <stop offset="0" stopColor="#35d6c0" stopOpacity="0" />
                <stop offset="1" stopColor="#35d6c0" stopOpacity="0.35" />
              </linearGradient>
              <radialGradient id="lm-glow">
                <stop offset="0" stopColor="#f5b83d" stopOpacity="0.55" />
                <stop offset="1" stopColor="#f5b83d" stopOpacity="0" />
              </radialGradient>
            </defs>

            {stage >= 2 &&
              mapEdges.map((e, i) => {
                const p = byId.get(e.a)!, q = byId.get(e.b)!;
                const lit = stage >= 4 && matched.has(e.a) && matched.has(e.b);
                return (
                  <line
                    key={`${e.a}|${e.b}|${i}`}
                    x1={sx(p.x)}
                    y1={sy(p.y)}
                    x2={sx(q.x)}
                    y2={sy(q.y)}
                    pathLength={1}
                    stroke={lit ? "#f5b83d" : "#8497aa"}
                    strokeOpacity={stage >= 4 ? (lit ? 0.7 : 0.04) : 0.16}
                    strokeWidth={lit ? 1.5 : 0.7}
                    className={stage === 2 ? "lm-draw" : undefined}
                    style={{ animationDelay: `${(i % 60) * 35}ms`, transition: "stroke-opacity 600ms" }}
                  />
                );
              })}

            {(stage === 2 || stage === 3) &&
              pulses.map((e, i) => {
                const p = byId.get(e.a)!, q = byId.get(e.b)!;
                return (
                  <circle
                    key={`p${i}`}
                    r={2.6}
                    fill="#35d6c0"
                    className="lm-pulse"
                    style={
                      {
                        "--x0": `${sx(p.x)}px`,
                        "--y0": `${sy(p.y)}px`,
                        "--x1": `${sx(q.x)}px`,
                        "--y1": `${sy(q.y)}px`,
                        animationDelay: `${(i % 12) * 170}ms`,
                      } as React.CSSProperties
                    }
                  />
                );
              })}

            {stage >= 1 &&
              (points ?? []).map((p) => {
                const r = matched.get(p.creator_id);
                const isTop = stage >= 6 && topIds.has(p.creator_id);
                let fill = COLOR[p.niche] ?? "#63768a";
                let size = 3.2;
                let opacity = 0.85;
                if (stage >= 4) {
                  if (r) {
                    const t = (r.score_breakdown.sentiment_risk_score - moodRange[0]) / Math.max(1e-6, moodRange[1] - moodRange[0]);
                    fill = stage >= 5 ? mix(COOL, WARM, t) : "#f5b83d";
                    size = 4 + 7 * r.score_breakdown.creator_feature_score;
                    opacity = 1;
                  } else {
                    opacity = 0.12;
                  }
                }
                return (
                  <g key={p.creator_id}>
                    {isTop && <circle cx={sx(p.x)} cy={sy(p.y)} r={30} fill="url(#lm-glow)" className="lm-breathe" />}
                    <circle
                      cx={sx(p.x)}
                      cy={sy(p.y)}
                      r={size}
                      fill={fill}
                      fillOpacity={opacity}
                      stroke={isTop ? "#f2f6fa" : "none"}
                      strokeWidth={2}
                      className="lm-dot"
                      style={{ animationDelay: `${Math.round(p.x * 1500)}ms`, transition: "r 600ms, fill 700ms, fill-opacity 600ms" }}
                    >
                      <title>{p.name}</title>
                    </circle>
                    {isTop && (
                      <text
                        x={sx(p.x) + 12}
                        y={sy(p.y) - 10}
                        fontSize="15"
                        fontWeight={600}
                        fill="#f2f6fa"
                        stroke="var(--panel)"
                        strokeWidth={4}
                        paintOrder="stroke"
                        className="lm-fade"
                      >
                        {p.name}
                      </text>
                    )}
                  </g>
                );
              })}

            {(stage === 1 || (stage === 3 && !result)) && (
              <rect x={-160} y={0} width={160} height={H} fill="url(#lm-sweep-g)" className={stage === 1 ? "lm-sweep-once" : "lm-sweep"} />
            )}
          </svg>

          {stage === 0 && (
            <div className="absolute inset-0 grid place-items-center">
              <div className="flex flex-col items-center gap-4">
                <div className="flex flex-wrap justify-center gap-2">
                  {words.map((w, i) => (
                    <span
                      key={w}
                      className="lm-word rounded-full border border-accent/60 bg-accent-soft px-4 py-1.5 text-lg font-semibold text-accent"
                      style={{ animationDelay: `${i * 260}ms` }}
                    >
                      {w}
                    </span>
                  ))}
                </div>
                <div className="lm-fade flex items-center gap-3 text-xs text-zinc-400" style={{ animationDelay: `${words.length * 260 + 300}ms` }}>
                  <span>CLIP + BERT</span>
                  <span className="relative h-1.5 w-40 overflow-hidden rounded-full bg-line">
                    <span className="lm-shimmer absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-signal to-transparent" />
                  </span>
                  <span>1,280 numbers</span>
                </div>
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-4 py-2 text-[11px] text-zinc-500">
            {stage < 5 ? (
              NICHES.map((n) => (
                <span key={n.name} className="flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: n.color }} />
                  {n.name}
                </span>
              ))
            ) : (
              <span className="flex items-center gap-2">
                Audience mood of your matches
                <span className="inline-block h-2 w-24 rounded-full" style={{ background: `linear-gradient(to right, ${COOL}, ${WARM})` }} />
                <span>more positive →</span>
                <span className="text-zinc-600">· bigger dot = closer content match</span>
              </span>
            )}
            {result && <span className="ml-auto">{onMap} of {results.length} matches shown on the map</span>}
          </div>
        </div>
      </section>

      {stage >= 6 && top.length > 0 && (
        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold text-zinc-100">Your top creators</h2>
          <div className="grid items-end gap-3 sm:grid-cols-3">
            {[top[1], top[0], top[2]].map((r, slot) =>
              r ? <Podium key={r.creator_id} r={r} place={slot === 1 ? 1 : slot === 0 ? 2 : 3} /> : <div key={`empty${slot}`} />,
            )}
          </div>
          <RankedList results={results} />
          <div className="flex flex-wrap gap-3">
            <Link href="/dashboard" className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-background hover:opacity-90">
              Detailed view →
            </Link>
            <Link href="/simulator" className="rounded-full border border-line px-5 py-2.5 text-sm text-zinc-200 hover:border-accent hover:text-accent">
              Plan a campaign
            </Link>
            <button onClick={() => setStage(0)} className="rounded-full px-4 py-2.5 text-sm text-zinc-500 hover:text-zinc-200">
              ↺ Replay
            </button>
          </div>
        </section>
      )}
    </main>
  );
}

function Podium({ r, place }: { r: InfluencerRecommendation; place: 1 | 2 | 3 }) {
  const R = 30, C = 2 * Math.PI * R;
  const medal = place === 1 ? "#f5b83d" : place === 2 ? "#cbd6e1" : "#d9894a";
  const platform = r.value?.platform === "youtube" ? "Best on YouTube" : r.value?.platform === "instagram" ? "Best on Instagram" : null;
  return (
    <div
      className={`lm-rise relative flex flex-col items-center gap-2 rounded-xl border bg-panel p-4 text-center ${place === 1 ? "border-accent/70 pb-8 pt-6" : "border-line"}`}
      style={{ animationDelay: `${place === 1 ? 0 : place === 2 ? 250 : 450}ms` }}
    >
      <span className="absolute -top-3 rounded-full px-2.5 py-0.5 text-xs font-bold text-background" style={{ background: medal }}>
        #{place}
      </span>
      <div className="relative">
        <svg viewBox="0 0 76 76" className="h-20 w-20">
          <g transform="rotate(-90 38 38)">
            <circle cx="38" cy="38" r={R} fill="none" stroke="var(--line)" strokeWidth="5" />
            <circle cx="38" cy="38" r={R} fill="none" stroke={medal} strokeWidth="5" strokeLinecap="round" strokeDasharray={`${(r.final_score / 100) * C} ${C}`} className="lm-ring" />
          </g>
        </svg>
        <span className="absolute inset-0 grid place-items-center">
          <Avatar creatorId={r.creator_id} name={r.name} size={48} />
        </span>
      </div>
      <div className="text-sm font-semibold text-zinc-50">{r.name}</div>
      <div className="font-mono text-2xl font-semibold" style={{ color: medal }}>
        {r.final_score.toFixed(1)}
      </div>
      <div className="text-xs text-zinc-400">{strongest(r)}</div>
      {platform && <span className="rounded-full border border-line px-2 py-0.5 text-[11px] text-zinc-400">{platform}</span>}
    </div>
  );
}

const SORTS: { key: "overall" | PartKey; label: string }[] = [
  { key: "overall", label: "Best overall" },
  { key: "value", label: "Best value" },
  { key: "mood", label: "Happiest audience" },
  { key: "fit", label: "Closest content" },
];

function partWords(key: PartKey, score: number, platform?: string) {
  const n = Math.round(score * 100);
  if (key === "value") return `Better value than ${n}% of ${platform === "instagram" ? "Instagram" : platform === "youtube" ? "YouTube" : ""} creators`;
  if (key === "mood") return `Audience mood ${n} out of 100`;
  if (key === "fit") return `Content match ${n} out of 100`;
  return `Network position ${n} out of 100`;
}

function RankedList({ results }: { results: InfluencerRecommendation[] }) {
  const [sort, setSort] = useState<"overall" | PartKey>("overall");
  const [open, setOpen] = useState<string | null>(null);
  const rows = useMemo(() => {
    const key = (r: InfluencerRecommendation) => (sort === "overall" ? r.final_score : parts(r).find((p) => p.key === sort && !p.neutral)?.score ?? -1);
    return [...results].sort((a, b) => key(b) - key(a));
  }, [results, sort]);
  const used = PARTS.filter((p) => results.some((r) => parts(r).some((q) => q.key === p.key)));
  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-zinc-100">All {results.length} matches</h3>
        <div className="flex flex-wrap gap-1.5">
          {SORTS.filter((s) => s.key === "overall" || used.some((u) => u.key === s.key)).map((s) => (
            <button
              key={s.key}
              onClick={() => setSort(s.key)}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${sort === s.key ? "border-accent bg-accent text-background" : "border-line text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"}`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-zinc-500">
        <span>What makes up each score:</span>
        {used.map((p) => (
          <span key={p.key} className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-3 rounded-sm" style={{ background: p.color }} />
            {p.label} ({Math.round(100 * (parts(results.find((r) => parts(r).some((q) => q.key === p.key))!).find((q) => q.key === p.key)?.weight ?? 0))}%)
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="lm-stripes inline-block h-2 w-3 rounded-sm bg-zinc-600" />
          little data yet, counted as average
        </span>
      </div>

      <ul key={sort} className="mt-3 flex flex-col gap-1.5">
        {rows.map((r, i) => {
          const ps = parts(r);
          const sum = ps.reduce((a, p) => a + p.points, 0);
          const penalty = sum - r.final_score > 0.5;
          const isOpen = open === r.creator_id;
          return (
            <li key={r.creator_id} className="lm-row" style={{ animationDelay: `${i * 70}ms` }}>
              <button
                onClick={() => setOpen(isOpen ? null : r.creator_id)}
                aria-expanded={isOpen}
                className={`grid w-full grid-cols-[28px_36px_minmax(0,1fr)_auto] items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors sm:grid-cols-[28px_36px_minmax(140px,220px)_minmax(0,1fr)_52px] ${isOpen ? "bg-line/60" : "hover:bg-line/40"}`}
              >
                <span className={`grid h-7 w-7 place-items-center rounded-full font-mono text-xs font-semibold ${i < 3 ? "bg-accent text-background" : "bg-line text-zinc-300"}`}>{i + 1}</span>
                <Avatar creatorId={r.creator_id} name={r.name} size={36} />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-zinc-100">{r.name}</span>
                  <span className="block text-[11px] text-zinc-500">
                    {r.value?.platform === "instagram" ? "Instagram" : r.value?.platform === "youtube" ? "YouTube" : "Creator"}
                    {r.estimated_cost != null && ` · ₹${Math.round(r.estimated_cost).toLocaleString("en-IN")} per post`}
                  </span>
                </span>
                <span className="col-span-4 flex h-3.5 overflow-hidden rounded-full bg-line sm:col-span-1" title={ps.map((p) => `${p.label}: ${p.neutral ? "little data yet" : partWords(p.key, p.score, r.value?.platform)}`).join(" · ")}>
                  <span className="lm-grow flex h-full" style={{ width: `${Math.min(100, sum)}%`, animationDelay: `${i * 70 + 150}ms` }}>
                    {ps.map((p) => (
                      <span
                        key={p.key}
                        className={`h-full border-r-2 border-[var(--panel)] last:border-r-0 ${p.neutral ? "lm-stripes opacity-40" : ""}`}
                        style={{ width: `${(100 * p.points) / Math.max(1e-6, sum)}%`, background: p.color }}
                      />
                    ))}
                  </span>
                </span>
                <span className="row-start-1 text-right font-mono text-lg font-semibold text-zinc-50 sm:row-auto col-start-4 sm:col-start-auto">
                  {r.final_score.toFixed(1)}
                </span>
              </button>
              {isOpen && (
                <div className="lm-fade mx-2 mb-2 grid gap-3 rounded-lg border border-line bg-background p-3 sm:grid-cols-3">
                  {ps.map((p) => (
                    <div key={p.key}>
                      <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-200">
                        <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
                        {p.label}
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-line">
                        <div className={`h-full rounded-full ${p.neutral ? "lm-stripes opacity-40" : ""}`} style={{ width: `${p.score * 100}%`, background: p.color }} />
                      </div>
                      <div className="mt-1 text-[11px] text-zinc-400">{p.neutral ? "Little data yet, so counted as average" : partWords(p.key, p.score, r.value?.platform)}</div>
                    </div>
                  ))}
                  {penalty && <div className="text-[11px] text-red-300 sm:col-span-3">10 points taken off: some audience comments are negative.</div>}
                  <div className="flex items-center gap-3 sm:col-span-3">
                    <span className="text-xs text-zinc-400">{strongest(r)}</span>
                    <Link href={`/passport?creator=${r.creator_id}`} className="ml-auto text-xs font-medium text-accent hover:underline">
                      Open passport →
                    </Link>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
