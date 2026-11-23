"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import Avatar from "@/components/Avatar";
import Icon from "@/components/Icon";
import { getCoOccurrenceEdges, getCollaborationEdges, getPlatformProfile, getTimeline, postRecommendations, type CreatorTimeline } from "@/lib/api";
import type { BrandRecommendationRequest, BrandRecommendationResponse, InfluencerRecommendation, PlatformProfile } from "@/types";

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
    { title: "GAIL reads the creator network", sub: `${mapEdges.length.toLocaleString()} real collaborations and co-appearances; GAIL scores how far each creator's sponsorship can spread` },
    { title: "Scoring every creator", sub: result ? "Done" : `Content match (CLIP + BERT), audience mood, value for money, GAIL network reach · ${elapsed}s` },
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
                const fill = COLOR[p.niche] ?? "#63768a";
                let size = 3.2;
                let opacity = 0.85;
                if (stage >= 4) {
                  if (r) {
                    // The matched creator's photo is drawn over this spot (see the photo layer below the map).
                    size = 4 + 7 * r.score_breakdown.creator_feature_score;
                    opacity = 0;
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
                  </g>
                );
              })}

            {(stage === 1 || (stage === 3 && !result)) && (
              <rect x={-160} y={0} width={160} height={H} fill="url(#lm-sweep-g)" className={stage === 1 ? "lm-sweep-once" : "lm-sweep"} />
            )}
          </svg>

          {/* Photo layer: each matched creator's picture at their spot on the map (same box as the map, so positions line up).
              Size = content match, ring colour = audience mood (from stage 5), top 3 bigger with their names. */}
          {stage >= 4 && (
            <div className="pointer-events-none absolute inset-x-0 top-0" style={{ aspectRatio: `${W} / ${H}` }}>
              {[...results]
                .sort((a, b) => Number(topIds.has(a.creator_id)) - Number(topIds.has(b.creator_id)))
                .map((r, i) => {
                  const p = byId.get(r.creator_id);
                  if (!p) return null;
                  const isTop = stage >= 6 && topIds.has(r.creator_id);
                  const t = (r.score_breakdown.sentiment_risk_score - moodRange[0]) / Math.max(1e-6, moodRange[1] - moodRange[0]);
                  const ring = stage >= 5 ? mix(COOL, WARM, t) : "#f5b83d";
                  const size = Math.round(24 + 18 * r.score_breakdown.creator_feature_score) + (isTop ? 12 : 0);
                  return (
                    <div
                      key={r.creator_id}
                      className="pointer-events-auto absolute"
                      style={{ left: `${(sx(p.x) / W) * 100}%`, top: `${(sy(p.y) / H) * 100}%`, transform: "translate(-50%, -50%)", zIndex: isTop ? 2 : 1 }}
                      title={r.name}
                    >
                      <span
                        className="lm-photo block rounded-full"
                        style={{
                          animationDelay: `${i * 90}ms`,
                          boxShadow: `0 0 0 3px ${ring}${isTop ? `, 0 0 22px 4px ${ring}` : ""}`,
                          transition: "box-shadow 700ms",
                        }}
                      >
                        <Avatar creatorId={r.creator_id} name={r.name} size={size} />
                      </span>
                      {isTop && (
                        <span className="lm-fade absolute left-1/2 top-full mt-1.5 -translate-x-1/2 whitespace-nowrap rounded-md bg-background/80 px-1.5 py-0.5 text-xs font-semibold text-zinc-50">
                          {r.name}
                        </span>
                      )}
                    </div>
                  );
                })}
            </div>
          )}

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
                <span className="text-zinc-600">· bigger photo = closer content match</span>
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
          <Glance results={results} budget={Number(req.budget)} top={top} />
          <RankedList results={results} />
          <Charts results={results} />
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
                  <GailLine r={r} />
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

// ---- Brand report (23 Nov 2026): at-a-glance tiles, YouTube vs Instagram, value for money. Real data only. ----

const YT = "#d95926", IG = "#3987e5";
const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
const shortInr = (n: number) => (n >= 1e5 ? `₹${Number((n / 1e5).toFixed(1))}L` : `₹${Math.round(n / 1e3)}K`);
const people = (n: number | null) => (n == null ? "" : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}K` : `${n}`);

function useCountUp(target: number, ms = 900) {
  const [v, setV] = useState(0);
  useEffect(() => {
    let id = 0;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      id = requestAnimationFrame(() => setV(target));
      return () => cancelAnimationFrame(id);
    }
    const t0 = performance.now();
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      setV(target * (1 - Math.pow(1 - k, 3)));
      if (k < 1) id = requestAnimationFrame(step);
    };
    id = requestAnimationFrame(step);
    return () => cancelAnimationFrame(id);
  }, [target, ms]);
  return v;
}

function Tile({ icon, big, small, delay, children }: { icon: string; big: string; small: string; delay: number; children?: React.ReactNode }) {
  return (
    <div className="lm-rise flex flex-col gap-1 rounded-xl border border-line bg-panel p-4" style={{ animationDelay: `${delay}ms` }}>
      <span className="text-accent" aria-hidden>
        <Icon name={icon} size={20} />
      </span>
      <span className="font-mono text-2xl font-semibold text-zinc-50">{big}</span>
      <span className="text-xs text-zinc-400">{small}</span>
      {children}
    </div>
  );
}

function Glance({ results, budget, top }: { results: InfluencerRecommendation[]; budget: number; top: InfluencerRecommendation[] }) {
  const topCost = top.every((r) => r.estimated_cost != null) ? top.reduce((a, r) => a + (r.estimated_cost ?? 0), 0) : null;
  const yt = results.filter((r) => r.value?.platform === "youtube").length;
  const ig = results.filter((r) => r.value?.platform === "instagram").length;
  const moods = results.map((r) => r.score_breakdown.sentiment_risk_score).filter((m) => m !== 0.5);
  const avgMood = moods.length ? (100 * moods.reduce((a, b) => a + b, 0)) / moods.length : null;
  const n = useCountUp(results.length);
  const cost = useCountUp(topCost ?? 0);
  const mood = useCountUp(avgMood ?? 0);
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Tile icon="target" big={`${Math.round(n)}`} small="creators fit your product and budget" delay={0} />
      {topCost != null && (
        <Tile icon="wallet" big={inr(cost)} small={`your top 3, one post each (${Math.round((100 * topCost) / budget)}% of your budget)`} delay={80}>
          <span className="mt-1 h-1.5 overflow-hidden rounded-full bg-line">
            <span className="lm-grow block h-full rounded-full bg-accent" style={{ width: `${Math.min(100, (100 * topCost) / budget)}%` }} />
          </span>
        </Tile>
      )}
      <Tile icon="screen" big={`${yt} · ${ig}`} small="best value on YouTube · on Instagram" delay={160}>
        <span className="mt-1 flex h-1.5 overflow-hidden rounded-full bg-line">
          <span className="lm-grow h-full" style={{ width: `${(100 * yt) / Math.max(1, yt + ig)}%`, background: YT }} />
          <span className="lm-grow h-full" style={{ width: `${(100 * ig) / Math.max(1, yt + ig)}%`, background: IG }} />
        </span>
      </Tile>
      {avgMood != null && <Tile icon="smile" big={`${Math.round(mood)}/100`} small="average audience mood of your matches" delay={240} />}
    </div>
  );
}

/** The charts block: both charts plus the X vs Y explorer share one fetch of the per-platform profiles. */
function Charts({ results }: { results: InfluencerRecommendation[] }) {
  const [profiles, setProfiles] = useState<Record<string, PlatformProfile> | null>(null);
  const ids = results.map((r) => r.creator_id).join(",");
  useEffect(() => {
    let cancelled = false;
    // 3 at a time: the backend has 15 database connections, and 10 parallel profile calls per open report exhausted them
    // (QueuePool timeout seen 23 Nov 2026 with two reports open).
    (async () => {
      const list = ids.split(",").filter(Boolean);
      const m: Record<string, PlatformProfile> = {};
      for (let i = 0; i < list.length && !cancelled; i += 3) {
        const rs = await Promise.allSettled(list.slice(i, i + 3).map((id) => getPlatformProfile(id)));
        for (const x of rs) if (x.status === "fulfilled") m[x.value.creator_id] = x.value;
      }
      if (!cancelled) setProfiles(m);
    })();
    return () => {
      cancelled = true;
    };
  }, [ids]);
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-2">
        <PlatformChart results={results} profiles={profiles} />
        <ValueChart results={results} />
      </div>
      <NetworkReach results={results} />
      <PerformanceChart top={[...results].sort((a, b) => b.final_score - a.final_score).slice(0, 3)} />
      <Explorer results={results} profiles={profiles} />
    </>
  );
}

function PlatformChart({ results, profiles }: { results: InfluencerRecommendation[]; profiles: Record<string, PlatformProfile> | null }) {
  const [hover, setHover] = useState<string | null>(null);

  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <h3 className="text-base font-semibold text-zinc-100">YouTube vs Instagram</h3>
      <p className="mt-0.5 text-xs text-zinc-500">How engaged each creator&apos;s audience is, compared with other creators on the same platform</p>
      <div className="mt-2 flex gap-4 text-[11px] text-zinc-400">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: YT }} /> YouTube
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: IG }} /> Instagram
        </span>
      </div>
      <div className="mt-3 flex flex-col">
        <div className="grid grid-cols-[minmax(0,120px)_1fr_minmax(0,110px)] gap-3 text-[10px] text-zinc-600">
          <span />
          <span className="flex justify-between">
            <span>less engaged</span>
            <span>more engaged</span>
          </span>
          <span />
        </div>
        {results.map((r, i) => {
          const p = profiles?.[r.creator_id];
          const y = p?.youtube.available ? p.youtube.percentile : null;
          const g = p?.instagram.available ? p.instagram.percentile : null;
          const verdict =
            y != null && g != null
              ? Math.abs(y - g) < 10
                ? { text: "Similar on both", color: "#aab9c8" }
                : y > g
                  ? { text: "More engaged on YouTube", color: YT }
                  : { text: "More engaged on Instagram", color: IG }
              : y != null
                ? { text: "YouTube creator", color: YT }
                : g != null
                  ? { text: "Instagram creator", color: IG }
                  : null;
          const lo = y != null && g != null ? Math.min(y, g) : null;
          const hi = y != null && g != null ? Math.max(y, g) : null;
          const isHover = hover === r.creator_id;
          return (
            <div
              key={r.creator_id}
              onMouseEnter={() => setHover(r.creator_id)}
              onMouseLeave={() => setHover(null)}
              className={`lm-row rounded-md px-1 py-1.5 transition-colors ${isHover ? "bg-line/50" : ""}`}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <div className="grid grid-cols-[minmax(0,120px)_1fr_minmax(0,110px)] items-center gap-3">
                <span className="truncate text-xs text-zinc-200">{r.name}</span>
                <span className="relative h-5">
                  <span className="absolute inset-x-0 top-1/2 h-px bg-line" />
                  <span className="absolute top-1/2 h-2 w-px -translate-y-1/2 bg-zinc-700" style={{ left: "50%" }} />
                  {!profiles && <span className="lm-shimmer absolute top-1/2 h-1 w-1/4 -translate-y-1/2 rounded-full bg-zinc-700" />}
                  {lo != null && hi != null && (
                    <span className="lm-grow absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-zinc-500/60" style={{ left: `${lo}%`, width: `${hi - lo}%` }} />
                  )}
                  {y != null && <Dot left={y} color={YT} label="YT" big={g == null || y >= g} dy={g != null && Math.abs(y - g) < 4 ? -7 : 0} />}
                  {g != null && <Dot left={g} color={IG} label="IG" big={y == null || g > y} dy={y != null && Math.abs(y - g) < 4 ? 7 : 0} />}
                </span>
                <span className="text-right text-[11px]" style={{ color: verdict?.color ?? "#63768a" }}>
                  {verdict?.text ?? (profiles ? "Not measured yet" : "")}
                </span>
              </div>
              {isHover && p && (
                <div className="lm-fade mt-1 pl-[132px] text-[11px] text-zinc-400">
                  {p.youtube.available && (
                    <span className="mr-4">
                      <span style={{ color: YT }}>YouTube</span> {people(p.youtube.audience)} subscribers · typical {people(p.youtube.typical_views)} views
                    </span>
                  )}
                  {p.instagram.available && (
                    <span>
                      <span style={{ color: IG }}>Instagram</span> {people(p.instagram.audience)} followers · typical {people(p.instagram.typical_likes)} likes
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Smallest sideways moves (in chart units) so no two dots cover each other; dots that do not touch stay exactly in place. */
function spreadX(ps: { id: string; x: number; y: number; r: number }[]) {
  const out = new Map<string, number>();
  const placed: { x: number; y: number; r: number }[] = [];
  for (const p of [...ps].sort((a, b) => a.y - b.y)) {
    const hits = (dx: number) => placed.some((q) => Math.hypot(p.x + dx - q.x, p.y - q.y) < p.r + q.r - 1);
    let dx = 0;
    for (let k = 1; hits(dx) && k <= 40; k++) dx = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 3;
    out.set(p.id, dx);
    placed.push({ x: p.x + dx, y: p.y, r: p.r });
  }
  return out;
}

function Dot({ left, color, label, big, dy = 0 }: { left: number; color: string; label: string; big: boolean; dy?: number }) {
  return (
    <span
      className="lm-fade absolute top-1/2 grid -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full font-mono text-[8px] font-bold text-background"
      style={{ left: `${left}%`, marginTop: dy, background: color, width: big ? 20 : 15, height: big ? 20 : 15, boxShadow: big ? `0 0 12px ${color}` : "none" }}
      title={`${label === "YT" ? "YouTube" : "Instagram"}: more engaged than ${Math.round(left)}% of creators there`}
    >
      {label}
    </span>
  );
}

function ValueChart({ results }: { results: InfluencerRecommendation[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const pts = results.filter((r) => r.estimated_cost != null && r.score_breakdown.value_score != null);
  if (pts.length < 2) return null;
  const VW = 520, VH = 300, L = 48, R = 16, T = 16, B = 40;
  const costs = pts.map((r) => r.estimated_cost as number);
  const lx0 = Math.log10(Math.min(...costs) / 1.6), lx1 = Math.log10(Math.max(...costs) * 1.6);
  const vals = pts.map((r) => r.score_breakdown.value_score as number);
  const y0 = Math.max(0, Math.floor((Math.min(...vals) - 0.08) * 10) / 10), y1 = 1;
  const X = (c: number) => L + ((Math.log10(c) - lx0) / (lx1 - lx0)) * (VW - L - R);
  const Y = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (VH - T - B);
  // Sweet spot: the cheaper half of the price range (log middle; rate-card prices repeat, so a median can equal the top price).
  const midCost = Math.sqrt(Math.min(...costs) * Math.max(...costs));
  const radius = (r: InfluencerRecommendation) => Math.max(6, Math.min(14, 6 + (r.final_score - 60) / 2.5));
  // Only bubbles that would cover each other are moved, and only as far as needed.
  const offsets = spreadX(pts.map((r) => ({ id: r.creator_id, x: X(r.estimated_cost as number), y: Y(r.score_breakdown.value_score as number), r: radius(r) })));
  const nudge = (r: InfluencerRecommendation) => offsets.get(r.creator_id) ?? 0;
  const ticks = [4000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000, 2500000].filter((t) => Math.log10(t) > lx0 && Math.log10(t) < lx1);
  const yTicks = [0, 0.25, 0.5, 0.75, 0.9, 1].filter((t) => t >= y0);
  const top3 = new Set([...results].sort((a, b) => b.final_score - a.final_score).slice(0, 3).map((r) => r.creator_id));
  const h = pts.find((r) => r.creator_id === hover);
  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <h3 className="text-base font-semibold text-zinc-100">Price vs value</h3>
      <p className="mt-0.5 text-xs text-zinc-500">Top left is the sweet spot: lower price, more engagement per rupee. Bigger bubble = higher overall score.</p>
      <div className="relative mt-2">
        <svg viewBox={`0 0 ${VW} ${VH}`} className="block h-auto w-full" role="img" aria-label="Price per post against value for money">
          <rect x={L} y={Y(1)} width={Math.max(0, X(midCost) - L)} height={Y(Math.max(y0, 0.9)) - Y(1)} fill="#35d6c0" fillOpacity={0.08} rx={6} />
          <text x={L + 8} y={Y(1) + 16} fontSize="11" fill="#35d6c0">
            Sweet spot
          </text>
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={L} x2={VW - R} y1={Y(t)} y2={Y(t)} stroke="#1e2b37" />
              <text x={L - 6} y={Y(t) + 3} fontSize="10" textAnchor="end" fill="#63768a">
                {Math.round(t * 100)}%
              </text>
            </g>
          ))}
          {ticks.map((t) => (
            <text key={t} x={X(t)} y={VH - B + 16} fontSize="10" textAnchor="middle" fill="#63768a">
              {shortInr(t)}
            </text>
          ))}
          <text x={(L + VW - R) / 2} y={VH - 6} fontSize="10" textAnchor="middle" fill="#8497aa">
            price per post →
          </text>
          <text x={12} y={(T + VH - B) / 2} fontSize="10" textAnchor="middle" fill="#8497aa" transform={`rotate(-90 12 ${(T + VH - B) / 2})`}>
            value for money →
          </text>
          {pts.map((r, i) => {
            const cx = X(r.estimated_cost as number) + nudge(r);
            const cy = Y(r.score_breakdown.value_score as number);
            const rad = radius(r);
            const color = r.value?.platform === "instagram" ? IG : YT;
            return (
              <g key={r.creator_id} onMouseEnter={() => setHover(r.creator_id)} onMouseLeave={() => setHover(null)} style={{ cursor: "pointer" }}>
                <circle cx={cx} cy={cy} r={rad + 8} fill="transparent" />
                <circle
                  cx={cx}
                  cy={cy}
                  r={rad}
                  fill={color}
                  fillOpacity={hover && hover !== r.creator_id ? 0.25 : 0.85}
                  stroke={top3.has(r.creator_id) ? "#f5b83d" : "var(--panel)"}
                  strokeWidth={top3.has(r.creator_id) ? 2.5 : 2}
                  className="lm-dot"
                  style={{ animationDelay: `${i * 80}ms`, transition: "fill-opacity 200ms" }}
                />
              </g>
            );
          })}
        </svg>
        {h && (
          <div
            className="pointer-events-none absolute z-10 w-52 -translate-x-1/2 rounded-lg border border-line bg-background/95 p-2.5 text-xs shadow-xl"
            style={{ left: `${((X(h.estimated_cost as number) + nudge(h)) / VW) * 100}%`, top: `${(Y(h.score_breakdown.value_score as number) / VH) * 100}%`, transform: "translate(-50%, 16px)" }}
          >
            <div className="font-semibold text-zinc-50">{h.name}</div>
            <div className="mt-0.5 text-zinc-400">
              {inr(h.estimated_cost as number)} per post on {h.value?.platform === "instagram" ? "Instagram" : "YouTube"}
            </div>
            <div className="text-zinc-400">Better value than {Math.round(100 * (h.score_breakdown.value_score as number))}% of creators there</div>
            <div className="text-zinc-400">Overall score {h.final_score.toFixed(1)}</div>
          </div>
        )}
      </div>
      <div className="mt-1 flex flex-wrap gap-4 text-[11px] text-zinc-400">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: YT }} /> best on YouTube
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: IG }} /> best on Instagram
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full border-2 border-accent" /> your top 3
        </span>
      </div>
    </div>
  );
}

// ---- X vs Y explorer (23 Nov 2026): the brand picks what goes on each axis; each dot is one matched creator. ----
// Every number is real: the recommendation answer and /platform-profiles. A part at the neutral 0.5 (too little data) and
// a platform the creator is not measured on are left out, and the chart says how many creators that leaves.

type Prof = PlatformProfile | undefined;
type Metric = {
  key: string;
  label: string;
  get: (r: InfluencerRecommendation, p: Prof) => number | null;
  fmt: (v: number) => string;
  log?: boolean;
  domain?: [number, number];
};

const pct100 = (v: number) => `${Math.round(v)}`;
const METRICS: Metric[] = [
  { key: "price", label: "Price per post", get: (r) => r.estimated_cost, fmt: (v) => shortInr(v), log: true },
  {
    key: "audience",
    label: "Audience size",
    get: (r, p) => {
      if (!p) return null;
      const side = r.value?.platform === "instagram" ? p.instagram : p.youtube;
      return side.available && side.audience ? side.audience : null;
    },
    fmt: (v) => people(v),
    log: true,
  },
  { key: "score", label: "Overall score", get: (r) => r.final_score, fmt: (v) => v.toFixed(0) },
  {
    key: "value",
    label: "Value for money",
    get: (r) => (r.score_breakdown.value_score == null ? null : 100 * r.score_breakdown.value_score),
    fmt: pct100,
    domain: [0, 100],
  },
  {
    key: "mood",
    label: "Audience mood",
    get: (r) => (r.score_breakdown.sentiment_risk_score === 0.5 ? null : 100 * r.score_breakdown.sentiment_risk_score),
    fmt: pct100,
    domain: [0, 100],
  },
  {
    key: "fit",
    label: "Content match",
    get: (r) => (r.score_breakdown.creator_feature_score === 0.5 ? null : 100 * r.score_breakdown.creator_feature_score),
    fmt: pct100,
    domain: [0, 100],
  },
  {
    key: "yt",
    label: "YouTube engagement",
    get: (_r, p) => (p?.youtube.available && p.youtube.percentile != null ? p.youtube.percentile : null),
    fmt: pct100,
    domain: [0, 100],
  },
  {
    key: "network",
    label: "Network reach (GAIL)",
    get: (r) => (r.spillover_basis === "trained" || r.spillover_basis === "inferred" ? 100 * r.score_breakdown.spillover_score : null),
    fmt: pct100,
    domain: [0, 100],
  },
  {
    key: "ig",
    label: "Instagram engagement",
    get: (_r, p) => (p?.instagram.available && p.instagram.percentile != null ? p.instagram.percentile : null),
    fmt: pct100,
    domain: [0, 100],
  },
];
const QUESTIONS = [
  { q: "Is a higher price worth it?", x: "price", y: "value" },
  { q: "Do bigger creators score better?", x: "audience", y: "score" },
  { q: "Bigger audience, happier audience?", x: "audience", y: "mood" },
  { q: "Better content match, better score?", x: "fit", y: "score" },
  { q: "YouTube vs Instagram engagement", x: "yt", y: "ig" },
  { q: "Network reach (GAIL) vs overall score", x: "network", y: "score" },
];

function ticksFor(lo: number, hi: number, log?: boolean) {
  if (log) {
    const out: number[] = [];
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++)
      for (const m of [1, 2.5, 5]) {
        const t = m * 10 ** e;
        if (t >= lo && t <= hi) out.push(t);
      }
    return out;
  }
  const raw = (hi - lo) / 5;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(Number(t.toFixed(6)));
  return out;
}

function domainFor(m: Metric, vals: number[]): [number, number] {
  if (m.domain) return m.domain;
  const lo = Math.min(...vals), hi = Math.max(...vals);
  if (m.log) return [lo / 1.6, hi * 1.6];
  const span = hi - lo || 10;
  return [lo - 0.15 * span, hi + 0.15 * span];
}

function Explorer({ results, profiles }: { results: InfluencerRecommendation[]; profiles: Record<string, PlatformProfile> | null }) {
  const [xk, setXk] = useState("price");
  const [yk, setYk] = useState("value");
  const [hover, setHover] = useState<string | null>(null);
  const mx = METRICS.find((m) => m.key === xk)!, my = METRICS.find((m) => m.key === yk)!;
  const pts = results
    .map((r) => ({ r, x: mx.get(r, profiles?.[r.creator_id]), y: my.get(r, profiles?.[r.creator_id]) }))
    .filter((p): p is { r: InfluencerRecommendation; x: number; y: number } => p.x != null && p.y != null);
  const needsProfiles = [mx, my].some((m) => ["audience", "yt", "ig"].includes(m.key));
  const VW = 900, VH = 380, L = 64, R = 24, T = 20, B = 52;
  const [x0, x1] = pts.length ? domainFor(mx, pts.map((p) => p.x)) : [0, 1];
  const [y0, y1] = pts.length ? domainFor(my, pts.map((p) => p.y)) : [0, 1];
  const fx = (v: number) => (mx.log ? (Math.log10(v) - Math.log10(x0)) / (Math.log10(x1) - Math.log10(x0)) : (v - x0) / (x1 - x0));
  const fy = (v: number) => (my.log ? (Math.log10(v) - Math.log10(y0)) / (Math.log10(y1) - Math.log10(y0)) : (v - y0) / (y1 - y0));
  const X = (v: number) => L + fx(v) * (VW - L - R);
  const Y = (v: number) => VH - B - fy(v) * (VH - T - B);
  const top3 = new Set([...results].sort((a, b) => b.final_score - a.final_score).slice(0, 3).map((r) => r.creator_id));
  const rad = (id: string) => (top3.has(id) ? 11 : 8);
  const offsets = spreadX(pts.map((p) => ({ id: p.r.creator_id, x: X(p.x), y: Y(p.y), r: rad(p.r.creator_id) })));
  const h = pts.find((p) => p.r.creator_id === hover);

  // Trend line: least squares on the plotted positions (so on a price or audience axis it follows the log scale drawn).
  const PW = VW - L - R, PH = VH - T - B;
  const trend = (() => {
    if (pts.length < 3) return null;
    const u = pts.map((p) => fx(p.x)), v = pts.map((p) => fy(p.y));
    const n = u.length, mu = u.reduce((a, b) => a + b, 0) / n, mv = v.reduce((a, b) => a + b, 0) / n;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < n; i++) {
      sxy += (u[i] - mu) * (v[i] - mv);
      sxx += (u[i] - mu) ** 2;
      syy += (v[i] - mv) ** 2;
    }
    if (sxx < 1e-9 || syy < 1e-9) return null;
    const b = sxy / sxx, a = mv - b * mu, r = sxy / Math.sqrt(sxx * syy);
    const ua = Math.min(...u), ub = Math.max(...u);
    const at = (uu: number) => [L + uu * PW, VH - B - Math.max(-0.02, Math.min(1.02, a + b * uu)) * PH];
    return { r, b, p1: at(ua), p2: at(ub) };
  })();
  const lc = (s: string) => (/^(YouTube|Instagram)/.test(s) ? s : s[0].toLowerCase() + s.slice(1));
  const reading = !trend
    ? null
    : Math.abs(trend.r) < 0.3
      ? `No clear pattern between ${lc(mx.label)} and ${lc(my.label)} in these ${pts.length} creators.`
      : `${Math.abs(trend.r) >= 0.6 ? "Clear" : "Slight"} pattern: as ${lc(mx.label)} goes up, ${lc(my.label)} tends to go ${trend.b > 0 ? "up" : "down"} (in these ${pts.length} creators).`;

  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <h3 className="text-base font-semibold text-zinc-100">Compare your matches</h3>
      <p className="mt-0.5 text-xs text-zinc-500">Pick a question. Each dot is one creator; the line shows the overall pattern.</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {QUESTIONS.map((q) => {
          const on = q.x === xk && q.y === yk;
          return (
            <button
              key={q.q}
              onClick={() => {
                setXk(q.x);
                setYk(q.y);
              }}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${on ? "border-accent bg-accent text-background" : "border-line text-zinc-300 hover:border-accent hover:text-accent"}`}
            >
              {q.q}
            </button>
          );
        })}
      </div>

      <div className="relative mt-3">
        {pts.length === 0 ? (
          <p className="py-16 text-center text-sm text-zinc-500">{needsProfiles && !profiles ? "Loading platform numbers…" : "None of these creators has both of these numbers yet. Try another pair."}</p>
        ) : (
          <svg viewBox={`0 0 ${VW} ${VH}`} className="block h-auto w-full" role="img" aria-label={`${mx.label} against ${my.label}`} onMouseLeave={() => setHover(null)}>
            {ticksFor(y0, y1, my.log).map((t) => (
              <g key={`y${t}`}>
                <line x1={L} x2={VW - R} y1={Y(t)} y2={Y(t)} stroke="#1e2b37" />
                <text x={L - 8} y={Y(t) + 4} fontSize="11" textAnchor="end" fill="#63768a">
                  {my.fmt(t)}
                </text>
              </g>
            ))}
            {ticksFor(x0, x1, mx.log).map((t) => (
              <g key={`x${t}`}>
                <line x1={X(t)} x2={X(t)} y1={T} y2={VH - B} stroke="#1e2b37" strokeDasharray="2 4" />
                <text x={X(t)} y={VH - B + 18} fontSize="11" textAnchor="middle" fill="#63768a">
                  {mx.fmt(t)}
                </text>
              </g>
            ))}
            <line x1={L} x2={VW - R} y1={VH - B} y2={VH - B} stroke="#8497aa" strokeWidth={1.5} />
            <line x1={L} x2={L} y1={T} y2={VH - B} stroke="#8497aa" strokeWidth={1.5} />
            <path d={`M ${VW - R} ${VH - B} l -7 -4 l 0 8 z`} fill="#8497aa" />
            <path d={`M ${L} ${T} l -4 7 l 8 0 z`} fill="#8497aa" />
            <text x={(L + VW - R) / 2} y={VH - 10} fontSize="13" fontWeight={600} textAnchor="middle" fill="#cbd6e1">
              X axis: {mx.label}
            </text>
            <text x={16} y={(T + VH - B) / 2} fontSize="13" fontWeight={600} textAnchor="middle" fill="#cbd6e1" transform={`rotate(-90 16 ${(T + VH - B) / 2})`}>
              Y axis: {my.label}
            </text>
            {trend && (
              <line
                key={`${xk}-${yk}`}
                x1={trend.p1[0]}
                y1={trend.p1[1]}
                x2={trend.p2[0]}
                y2={trend.p2[1]}
                pathLength={1}
                stroke="#f5b83d"
                strokeWidth={2.5}
                strokeOpacity={0.85}
                strokeLinecap="round"
                className="lm-draw"
              />
            )}
            {pts.map((p, i) => {
              const id = p.r.creator_id;
              const cx = X(p.x) + (offsets.get(id) ?? 0), cy = Y(p.y);
              const color = p.r.value?.platform === "instagram" ? IG : YT;
              const dim = hover && hover !== id;
              return (
                <g key={id} onMouseEnter={() => setHover(id)} style={{ cursor: "pointer" }}>
                  <circle cx={cx} cy={cy} r={rad(id) + 8} fill="transparent" style={{ transition: "cx 700ms ease, cy 700ms ease" }} />
                  <circle
                    cx={cx}
                    cy={cy}
                    r={rad(id)}
                    fill={color}
                    fillOpacity={dim ? 0.25 : 0.9}
                    stroke={top3.has(id) ? "#f5b83d" : "var(--panel)"}
                    strokeWidth={top3.has(id) ? 3 : 2}
                    className="lm-dot"
                    style={{ animationDelay: `${i * 50}ms`, transition: "cx 700ms cubic-bezier(0.2,0.7,0.2,1), cy 700ms cubic-bezier(0.2,0.7,0.2,1), fill-opacity 200ms" }}
                  />
                  {(top3.has(id) || hover === id) && (
                    <text
                      x={cx + rad(id) + 5}
                      y={cy + 4}
                      fontSize="12"
                      fill="#f2f6fa"
                      stroke="var(--panel)"
                      strokeWidth={4}
                      paintOrder="stroke"
                      style={{ pointerEvents: "none", transition: "x 700ms, y 700ms" }}
                    >
                      {p.r.name}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        )}
        {h && (
          <div
            className="pointer-events-none absolute z-10 w-56 rounded-lg border border-line bg-background/95 p-2.5 text-xs shadow-xl"
            style={{ left: `${Math.min(80, (X(h.x) / VW) * 100)}%`, top: `${(Y(h.y) / VH) * 100}%`, transform: "translate(-50%, 18px)" }}
          >
            <div className="font-semibold text-zinc-50">{h.r.name}</div>
            <div className="mt-1 flex justify-between text-zinc-400">
              <span>{mx.label}</span>
              <span className="font-mono text-zinc-100">{mx.key === "price" ? inr(h.x) : mx.fmt(h.x)}</span>
            </div>
            <div className="flex justify-between text-zinc-400">
              <span>{my.label}</span>
              <span className="font-mono text-zinc-100">{my.key === "price" ? inr(h.y) : my.fmt(h.y)}</span>
            </div>
          </div>
        )}
      </div>
      {reading && (
        <p key={`${xk}-${yk}`} className="lm-fade mt-2 rounded-md border border-accent/30 bg-accent/5 px-3 py-2 text-sm text-zinc-200">
          {reading}
        </p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-4 text-[11px] text-zinc-400">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: YT }} /> best on YouTube
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: IG }} /> best on Instagram
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full border-2 border-accent" /> your top 3
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 rounded bg-accent" /> pattern line
        </span>
        {pts.length < results.length && pts.length > 0 && (
          <span className="ml-auto text-zinc-500">
            {pts.length} of {results.length} creators shown: the others don&apos;t have both numbers yet
          </span>
        )}
      </div>
    </div>
  );
}

// ---- GAIL in the report (23 Nov 2026) ----
// score_breakdown.spillover_score is GAIL's output (backend/app/spillover.py: the creator's percentile among
// graph-connected creators). With a price estimate the final score gives it weight 0 (agreed 7 Nov 2026), so it is shown
// alongside the ranking, never folded into it here. Measured spillover (SPILLOVER_RESULTS_OVERALL_22NOV.md): a tagged
// creator's engagement +0.095 log (about +10%, 7 days, 291 events); small featured creators in joint videos +0.277 log
// (about +32%, 14 days).
const gailScored = (r: InfluencerRecommendation) => r.spillover_basis === "trained" || r.spillover_basis === "inferred";
const topPct = (s: number) => Math.max(1, Math.round(100 - 100 * s));

function GailLine({ r }: { r: InfluencerRecommendation }) {
  return (
    <div className="flex items-center gap-2 text-[11px] text-zinc-400 sm:col-span-3">
      <Icon name="network" size={14} className="text-[#d55181]" />
      {gailScored(r) ? (
        <span>
          Network reach (GAIL): <span className="font-semibold text-zinc-100">top {topPct(r.score_breakdown.spillover_score)}%</span> of connected creators ·{" "}
          {r.score_breakdown.weight_spillover > 0 ? `counts for ${Math.round(100 * r.score_breakdown.weight_spillover)}% of the score` : "shown alongside, not part of the score"}
        </span>
      ) : r.spillover_basis === "isolated" ? (
        <span>Network reach (GAIL): independent creator, no collaborations on record</span>
      ) : (
        <span>Network reach (GAIL): not scored yet</span>
      )}
    </div>
  );
}

function NetworkReach({ results }: { results: InfluencerRecommendation[] }) {
  const scored = [...results].filter(gailScored).sort((a, b) => b.score_breakdown.spillover_score - a.score_breakdown.spillover_score);
  const solo = results.filter((r) => r.spillover_basis === "isolated");
  const pending = results.filter((r) => !gailScored(r) && r.spillover_basis !== "isolated");
  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-base font-semibold text-zinc-100">
            <Icon name="network" size={18} className="text-[#d55181]" /> Network reach (GAIL)
          </h3>
          <p className="mt-0.5 max-w-2xl text-xs text-zinc-500">
            Our GAIL model reads who works with whom and scores how well placed each creator is for a sponsorship to spread to the creators they collaborate with.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="rounded-lg border border-[#d55181]/40 bg-[#d55181]/10 px-3 py-1.5 text-xs text-zinc-200">
            Measured: tagged collaborators <span className="font-semibold text-zinc-50">+10%</span> engagement
          </span>
          <span className="rounded-lg border border-[#d55181]/40 bg-[#d55181]/10 px-3 py-1.5 text-xs text-zinc-200">
            Small creators in joint videos <span className="font-semibold text-zinc-50">+32%</span>
          </span>
        </div>
      </div>
      {scored.length > 0 ? (
        <div className="mt-4 flex flex-col gap-2">
          {scored.map((r, i) => (
            <div key={r.creator_id} className="lm-row grid grid-cols-[28px_minmax(0,180px)_1fr_64px] items-center gap-3" style={{ animationDelay: `${i * 60}ms` }}>
              <Avatar creatorId={r.creator_id} name={r.name} size={28} />
              <span className="truncate text-sm text-zinc-200">{r.name}</span>
              <span className="h-3 overflow-hidden rounded-full bg-line">
                <span
                  className="lm-grow block h-full rounded-full"
                  style={{ width: `${100 * r.score_breakdown.spillover_score}%`, background: "linear-gradient(90deg, #8e3a63, #d55181)", animationDelay: `${150 + i * 60}ms` }}
                />
              </span>
              <span className="text-right font-mono text-xs text-zinc-100">top {topPct(r.score_breakdown.spillover_score)}%</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-zinc-500">None of these creators has collaborations on record yet.</p>
      )}
      {(solo.length > 0 || pending.length > 0) && (
        <p className="mt-3 text-[11px] text-zinc-500">
          {solo.length > 0 && `${solo.length} independent creator${solo.length > 1 ? "s" : ""} with no collaborations on record. `}
          {pending.length > 0 && `${pending.length} not scored yet.`}
        </p>
      )}
      <p className="mt-2 text-[11px] text-zinc-500">
        {results.some((r) => r.score_breakdown.weight_spillover > 0)
          ? `GAIL's reach counts for ${Math.round(100 * Math.max(...results.map((r) => r.score_breakdown.weight_spillover)))}% of the score for the creators it scored. `
          : "Shown alongside the ranking: GAIL's reach does not change the score yet. "}
        The two measured numbers come from our real-data spillover tests (7-day and 14-day windows).
      </p>
    </div>
  );
}

// ---- Recent performance: a zig-zag line per creator (23 Nov 2026) ----
// Real counts from /platform-profiles/{id}/timeline, each post divided by that creator's own median, so creators of very
// different sizes share one axis (100% = their usual). Log scale, because single posts can run several times the usual.
const LINE = ["#f5b83d", "#35d6c0", "#d55181"];

function PerformanceChart({ top }: { top: InfluencerRecommendation[] }) {
  const [tl, setTl] = useState<Record<string, CreatorTimeline> | null>(null);
  const [platform, setPlatform] = useState<"youtube" | "instagram">("youtube");
  const [off, setOff] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<{ id: string; i: number } | null>(null);
  const ids = top.map((r) => r.creator_id).join(",");
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const m: Record<string, CreatorTimeline> = {};
      for (const id of ids.split(",").filter(Boolean)) {
        try {
          m[id] = await getTimeline(id);
        } catch {
          // a creator without a timeline simply has no line
        }
        if (cancelled) return;
      }
      setTl(m);
    })();
    return () => {
      cancelled = true;
    };
  }, [ids]);

  const series = top.map((r, ci) => {
    const t = tl?.[r.creator_id];
    const raw = (platform === "youtube" ? t?.youtube.map((v) => ({ at: v.at, n: v.views, sp: v.sponsored })) : t?.instagram.map((v) => ({ at: v.at, n: v.likes, sp: v.sponsored }))) ?? [];
    const pos = raw.filter((p) => p.n > 0);
    const sorted = [...pos].map((p) => p.n).sort((a, b) => a - b);
    const med = sorted.length ? sorted[Math.floor(sorted.length / 2)] : 1;
    return { r, color: LINE[ci % LINE.length], pts: pos.map((p) => ({ ...p, rel: (100 * p.n) / med })) };
  });
  const shown = series.filter((s) => s.pts.length >= 3 && !off.has(s.r.creator_id));
  const VW = 900, VH = 330, L = 64, R = 24, T = 20, B = 52;
  const all = shown.flatMap((s) => s.pts.map((p) => p.rel));
  const y0 = Math.max(5, Math.min(25, ...all) / 1.3), y1 = Math.max(400, ...all) * 1.15;
  const X = (i: number, n: number) => L + (n <= 1 ? 0.5 : i / (n - 1)) * (VW - L - R);
  const Y = (v: number) => VH - B - ((Math.log10(v) - Math.log10(y0)) / (Math.log10(y1) - Math.log10(y0))) * (VH - T - B);
  const ticks = [10, 25, 50, 100, 200, 400, 800, 1600, 3200].filter((t) => t >= y0 && t <= y1);
  const best = shown.flatMap((s) => s.pts.map((p) => ({ s, p }))).sort((a, b) => b.p.rel - a.p.rel)[0];
  const h = hover ? series.find((s) => s.r.creator_id === hover.id) : undefined;
  const hp = h && hover ? h.pts[hover.i] : undefined;
  const date = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  const unit = platform === "youtube" ? "views" : "likes";

  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-zinc-100">Recent performance of your top 3</h3>
          <p className="mt-0.5 text-xs text-zinc-500">Each point is one post, compared with that creator&apos;s own usual (100%). Ringed points are sponsored posts.</p>
        </div>
        <div className="flex gap-1.5">
          {(["youtube", "instagram"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPlatform(p)}
              className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors ${platform === p ? "border-accent bg-accent text-background" : "border-line text-zinc-300 hover:border-accent"}`}
            >
              <Icon name={p} size={14} />
              {p === "youtube" ? "YouTube views" : "Instagram likes"}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {series.map((s) => {
          const enough = s.pts.length >= 3;
          const on = enough && !off.has(s.r.creator_id);
          return (
            <button
              key={s.r.creator_id}
              disabled={!enough}
              onClick={() =>
                setOff((o) => {
                  const n = new Set(o);
                  if (n.has(s.r.creator_id)) n.delete(s.r.creator_id);
                  else n.add(s.r.creator_id);
                  return n;
                })
              }
              className={`flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs transition-colors ${on ? "border-line text-zinc-100" : "border-line text-zinc-600"}`}
              title={enough ? "Show or hide this line" : `Too few ${platform === "youtube" ? "videos" : "posts"} on this platform`}
            >
              <span className="inline-block h-0.5 w-4 rounded" style={{ background: on ? s.color : "#2e3c4a" }} />
              {s.r.name}
            </button>
          );
        })}
      </div>

      <div className="relative mt-2">
        {!tl ? (
          <p className="py-16 text-center text-sm text-zinc-500">Loading their latest posts…</p>
        ) : shown.length === 0 ? (
          <p className="py-16 text-center text-sm text-zinc-500">Not enough recent {platform === "youtube" ? "YouTube videos" : "Instagram posts"} for these creators.</p>
        ) : (
          <svg viewBox={`0 0 ${VW} ${VH}`} className="block h-auto w-full" role="img" aria-label="Recent posts of the top creators compared with their usual" onMouseLeave={() => setHover(null)}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={L} x2={VW - R} y1={Y(t)} y2={Y(t)} stroke={t === 100 ? "#4a5b6d" : "#1e2b37"} strokeDasharray={t === 100 ? "6 4" : undefined} />
                <text x={L - 8} y={Y(t) + 4} fontSize="11" textAnchor="end" fill="#63768a">
                  {t}%
                </text>
              </g>
            ))}
            <text x={VW - R - 4} y={Y(100) - 6} fontSize="11" textAnchor="end" fill="#8497aa">
              their usual
            </text>
            <line x1={L} x2={VW - R} y1={VH - B} y2={VH - B} stroke="#8497aa" strokeWidth={1.5} />
            <line x1={L} x2={L} y1={T} y2={VH - B} stroke="#8497aa" strokeWidth={1.5} />
            <text x={L} y={VH - B + 18} fontSize="11" fill="#63768a">
              older
            </text>
            <text x={VW - R} y={VH - B + 18} fontSize="11" textAnchor="end" fill="#63768a">
              newest
            </text>
            <text x={(L + VW - R) / 2} y={VH - 10} fontSize="13" fontWeight={600} textAnchor="middle" fill="#cbd6e1">
              X axis: their latest posts, in order
            </text>
            <text x={16} y={(T + VH - B) / 2} fontSize="13" fontWeight={600} textAnchor="middle" fill="#cbd6e1" transform={`rotate(-90 16 ${(T + VH - B) / 2})`}>
              Y axis: {unit} vs their usual
            </text>
            {shown.map((s) => {
              const n = s.pts.length;
              const d = s.pts.map((p, i) => `${i ? "L" : "M"} ${X(i, n)} ${Y(Math.max(y0, p.rel))}`).join(" ");
              return (
                <g key={`${platform}-${s.r.creator_id}`}>
                  <path d={d} fill="none" stroke={s.color} strokeWidth={2.2} strokeLinejoin="round" pathLength={1} className="lm-draw" style={{ animationDuration: "1.4s" }} />
                  {s.pts.map((p, i) => (
                    <g key={i} onMouseEnter={() => setHover({ id: s.r.creator_id, i })}>
                      <circle cx={X(i, n)} cy={Y(Math.max(y0, p.rel))} r={10} fill="transparent" />
                      <circle
                        cx={X(i, n)}
                        cy={Y(Math.max(y0, p.rel))}
                        r={p.sp ? 5 : 3}
                        fill={p.sp ? "var(--panel)" : s.color}
                        stroke={s.color}
                        strokeWidth={p.sp ? 2.5 : 0}
                        className="lm-fade"
                        style={{ animationDelay: `${600 + i * 25}ms` }}
                      />
                    </g>
                  ))}
                </g>
              );
            })}
          </svg>
        )}
        {h && hp && hover && (
          <div
            className="pointer-events-none absolute z-10 w-56 rounded-lg border border-line bg-background/95 p-2.5 text-xs shadow-xl"
            style={{ left: `${Math.min(82, (X(hover.i, h.pts.length) / VW) * 100)}%`, top: `${(Y(Math.max(y0, hp.rel)) / VH) * 100}%`, transform: "translate(-50%, 16px)" }}
          >
            <div className="font-semibold text-zinc-50">{h.r.name}</div>
            <div className="text-zinc-400">
              {date(hp.at)} · {hp.n.toLocaleString("en-IN")} {unit}
            </div>
            <div className="text-zinc-400">
              {Math.round(hp.rel)}% of their usual{hp.sp ? " · sponsored" : ""}
            </div>
          </div>
        )}
      </div>
      {best && (
        <p className="mt-2 rounded-md border border-accent/30 bg-accent/5 px-3 py-2 text-sm text-zinc-200">
          Biggest jump: {best.s.r.name}&apos;s {platform === "youtube" ? "video" : "post"} on {date(best.p.at)} reached {Math.round(best.p.rel)}% of their usual
          {best.p.sp ? " (a sponsored post)" : ""}.
        </p>
      )}
    </div>
  );
}
