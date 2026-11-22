"use client";

import { useEffect, useMemo, useState } from "react";
import { getPassport, postRecommendations } from "@/lib/api";
import { useStoredRecommendationResult } from "@/lib/useStoredRecommendationResult";
import type { BrandRecommendationResponse, InfluencerRecommendation, PassportRecord } from "@/types";

// Pipeline Live (22 Nov 2026, idea 1 of 3 Nov): one recommendation followed through every stage of the system, with the
// REAL numbers the API returns for that creator (POST /recommendations score_breakdown + GET /passport/{id}). Nothing here is
// simulated; a part the API does not return is shown as "not available", never guessed. The diagram animates real values.

const BRIEFS = [
  { label: "Fitness and gym", value: "fitness gym workout" },
  { label: "Protein and supplements", value: "protein supplement whey nutrition" },
  { label: "Yoga, meditation and wellness", value: "yoga meditation wellness" },
  { label: "Running and sports shoes", value: "shoes running sneakers footwear marathon" },
  { label: "Healthy food and nutrition", value: "healthy food nutrition diet protein recipe" },
];

const fmt = (n: number | null | undefined, d = 2) => (n === null || n === undefined || Number.isNaN(n) ? "not available" : n.toFixed(d));
const int = (n: number | null | undefined) => (n === null || n === undefined ? "not available" : Math.round(n).toLocaleString("en-IN"));

// Plain words for the spillover basis returned by the API (backend/app/schemas.py SpilloverBasis).
const BASIS: Record<string, string> = {
  trained: "Built from direct collaborations",
  inferred: "Built from co-appearances and shared audiences",
  placeholder: "Network data loading",
  isolated: "Independent creator, no network ties yet",
};

// Brand words for the platform mood-gap labels of scripts/passport_stats.py (a gap counts only beyond its error bound).
const MOOD_GAP: Record<string, string> = {
  "no clear gap": "Similar on both platforms",
  "warmer on Instagram than on YouTube": "Warmer on Instagram",
  "warmer on YouTube than on Instagram": "Warmer on YouTube",
};

// A 0-1 percentile in brand words: "Top 4%" for high ranks, "Above 70%" style otherwise.
const rank = (s: number | null | undefined) =>
  s === null || s === undefined || Number.isNaN(s) ? "not available" : s >= 0.5 ? `Top ${Math.max(1, Math.round((1 - s) * 100))}%` : `Above ${Math.round(s * 100)}% of creators`;
const shortRank = (s: number | null | undefined) =>
  s === null || s === undefined || Number.isNaN(s) ? "—" : s >= 0.5 ? `Top ${Math.max(1, Math.round((1 - s) * 100))}%` : `${Math.round(s * 100)}th`;
const moodWord = (s: number) => (s >= 0.75 ? "very positive" : s >= 0.55 ? "positive" : s >= 0.3 ? "mixed" : "negative");

type Stage = { key: string; title: string; model: string; lines: [string, string][]; note?: string };

function stagesFor(r: InfluencerRecommendation, p: PassportRecord | null): Stage[] {
  const b = r.score_breakdown;
  const wv = b.weight_value ?? 0;
  const contrib = {
    value: wv * (b.value_score ?? 0) * 100,
    mood: b.weight_sentiment_risk * b.sentiment_risk_score * 100,
    fit: b.weight_creator_feature * b.creator_feature_score * 100,
    spill: b.weight_spillover * b.spillover_score * 100,
  };
  const adj = r.final_score - (contrib.value + contrib.mood + contrib.fit + contrib.spill);
  return [
    {
      key: "data", title: "1 · Data collected", model: "YouTube API · Instagram (OpenCLI) · Azure PostgreSQL",
      lines: [
        ["YouTube videos", int(p?.coverage.youtube_videos)],
        ["Instagram posts", int(p?.coverage.instagram_posts)],
        ["Growth readings", int(p?.coverage.growth_readings)],
        ["Platforms", r.data_coverage ?? p?.coverage.platforms ?? "not available"],
      ],
    },
    {
      key: "features", title: "2 · Content fit", model: "CLIP (thumbnails) + BERT (titles, captions)",
      lines: [
        ["Brand fit score", fmt(b.creator_feature_score)],
        ["Product words matched", r.product_match === "exact" ? "yes, in the profile" : r.product_match === "broader" ? "broader match" : "not available"],
        ["Category", r.category ?? p?.category ?? "not available"],
      ],
    },
    {
      key: "graph", title: "3 · Creator network", model: "GAIL graph attention (collaborations, co-occurrence)",
      lines: [
        ["Network reach (GAIL)", rank(b.spillover_score)],
        ["How it is measured", BASIS[r.spillover_basis ?? ""] ?? "not available"],
        // shown only when the creator has direct collaborations on record (her request, 22 Nov: no negative-sounding row)
        ...(p && p.network.linked_creators > 0 ? [["Direct collaborators", int(p.network.linked_creators)] as [string, string]] : []),
      ],
      note: "Network reach is reported alongside the score, so brands can weigh it themselves.",
    },
    {
      key: "mood", title: "4 · Audience mood", model: "RoBERTa (English) + XLM-R (Hindi script)",
      lines: [
        ["Audience mood", `${fmt(b.sentiment_risk_score)} · ${moodWord(b.sentiment_risk_score)}`],
        ["YouTube vs Instagram mood", MOOD_GAP[p?.mood?.label ?? ""] ?? p?.mood?.label ?? "not available"],
      ],
      note: b.sentiment_risk_score < 0.3 ? "Below 0.3: a 10-point risk penalty applies." : undefined,
    },
    {
      key: "value", title: "5 · Value for money", model: "Engagement per ₹1,000 (rate-card estimate)",
      lines: [
        ["Value for money", rank(b.value_score ?? null)],
        ["Engagement per ₹1,000", r.value ? fmt(r.value.engagement_per_1000_inr, 0) : "not available"],
        ["Estimated cost", r.value ? `₹${int(r.value.cost_mid_inr)}` : "not available"],
      ],
    },
    {
      key: "fusion", title: "6 · Fusion → final score", model: "100 × (0.4 value + 0.3 mood + 0.3 fit), −10 if mood < 0.3",
      lines: [
        ["Value contribution", fmt(contrib.value, 1)],
        ["Mood contribution", fmt(contrib.mood, 1)],
        ["Fit contribution", fmt(contrib.fit, 1)],
        ["Network reach", contrib.spill > 0.05 ? fmt(contrib.spill, 1) : "Reported separately"],
        ["Risk check", adj < -0.05 ? fmt(adj, 1) : "Passed, healthy audience"],
        ["Final score", `${fmt(r.final_score, 1)} (range ${fmt(r.confidence_low, 1)}–${fmt(r.confidence_high, 1)})`],
      ],
    },
  ];
}

// ---------- flow diagram (22 Nov 2026 redesign: animated, interactive) ----------
// Layout mirrors the real system: data fans out into four branches, which merge in the fusion step into the score.
// The network branch's line into fusion is dashed: it is reported alongside the score, not added to it.
const VB = { w: 1000, h: 520 };
const R = 34;
type NodeKey = "data" | "features" | "graph" | "mood" | "value" | "fusion";
const NODES: Record<NodeKey, { x: number; y: number; label: string; color: string; stage: number }> = {
  data: { x: 95, y: 245, label: "Data", color: "#f5b83d", stage: 1 },
  features: { x: 420, y: 50, label: "Content fit", color: "#d95926", stage: 2 },
  graph: { x: 420, y: 175, label: "Network", color: "#c98500", stage: 2 },
  mood: { x: 420, y: 300, label: "Audience mood", color: "#199e70", stage: 2 },
  value: { x: 420, y: 425, label: "Value for money", color: "#3987e5", stage: 2 },
  fusion: { x: 715, y: 245, label: "Fusion", color: "#f5b83d", stage: 3 },
};
const SCORE = { x: 892, y: 230, r: 58 };
const BRANCHES: NodeKey[] = ["features", "graph", "mood", "value"];
const FINAL_STEP = 4;
const curve = (a: { x: number; y: number }, b: { x: number; y: number }) =>
  `M${a.x + R},${a.y} C${(a.x + b.x) / 2},${a.y} ${(a.x + b.x) / 2},${b.y} ${b.x - R},${b.y}`;
const scorePath = `M${NODES.fusion.x + R},${NODES.fusion.y} C${NODES.fusion.x + 70},${NODES.fusion.y} ${SCORE.x - SCORE.r - 40},${SCORE.y} ${SCORE.x - SCORE.r - 8},${SCORE.y}`;

/** Animate a number from 0 to `target` when `on` turns true (jumps straight there when the viewer prefers reduced motion). */
function useCountUp(target: number, on: boolean, ms = 900) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!on) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const k = reduce ? 1 : Math.min(1, (t - t0) / ms);
      setV(target * (1 - Math.pow(1 - k, 3)));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, on, ms]);
  return on ? v : 0;
}

/** A connector; when `on`, three dots travel along it (SVG animateMotion), hidden for reduced motion by CSS. */
function Flow({ d, color, on, dashed }: { d: string; color: string; on: boolean; dashed?: boolean }) {
  return (
    <g>
      <path d={d} fill="none" stroke={on ? color : "#1e2b37"} strokeOpacity={on ? 0.6 : 1} strokeWidth={2} strokeDasharray={dashed ? "6 6" : undefined} />
      {on &&
        [0, 0.55, 1.1].map((delay) => (
          <circle key={delay} r={4} fill={color} className="pipe-particle">
            <animateMotion dur="1.65s" begin={`${delay}s`} repeatCount="indefinite" path={d} />
          </circle>
        ))}
    </g>
  );
}

export default function PipelinePage() {
  const stored = useStoredRecommendationResult();
  const [fresh, setFresh] = useState<BrandRecommendationResponse | null>(null);
  const result = fresh ?? stored;
  const [brief, setBrief] = useState(BRIEFS[0].value);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [passport, setPassport] = useState<{ id: string; rec: PassportRecord | null } | null>(null);
  const [step, setStep] = useState(FINAL_STEP);
  const [playing, setPlaying] = useState(false);
  const [focus, setFocus] = useState<NodeKey>("fusion");
  const [hover, setHover] = useState<NodeKey | null>(null);

  const creator = useMemo(() => {
    if (!result?.results.length) return null;
    return result.results.find((r) => r.creator_id === selected) ?? result.results[0];
  }, [result, selected]);

  // Keyed on the creator's id: the stored result is re-parsed on every render, so the object itself changes each time.
  const creatorId = creator?.creator_id ?? null;
  useEffect(() => {
    if (!creatorId) return;
    let alive = true;
    getPassport(creatorId)
      .then((rec) => alive && setPassport({ id: creatorId, rec }))
      .catch(() => alive && setPassport({ id: creatorId, rec: null }));
    return () => {
      alive = false;
    };
  }, [creatorId]);

  const rec = passport && creator && passport.id === creator.creator_id ? passport.rec : null;
  const stages = useMemo(() => (creator ? stagesFor(creator, rec) : []), [creator, rec]);

  const animating = playing && step < FINAL_STEP;
  useEffect(() => {
    if (!animating) return;
    const t = setTimeout(() => setStep((s) => s + 1), 1500);
    return () => clearTimeout(t);
  }, [animating, step]);

  function play(fromStart = true) {
    if (fromStart) setStep(0);
    setPlaying(true);
  }

  async function runBrief() {
    setRunning(true);
    setError(null);
    try {
      const res = await postRecommendations({ product_category: brief, budget: 500000, max_results: 10 });
      sessionStorage.setItem("recommendationResult", JSON.stringify(res));
      setFresh(res);
      setSelected(null);
      setFocus("fusion");
      play();
    } catch {
      setError("Couldn't reach the backend at " + (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000") + ".");
    } finally {
      setRunning(false);
    }
  }

  // Real numbers shown inside the nodes; the count-up only animates them.
  const b = creator?.score_breakdown;
  const contrib = b
    ? {
        value: (b.weight_value ?? 0) * (b.value_score ?? 0) * 100,
        mood: b.weight_sentiment_risk * b.sentiment_risk_score * 100,
        fit: b.weight_creator_feature * b.creator_feature_score * 100,
      }
    : { value: 0, mood: 0, fit: 0 };
  const items = (rec?.coverage.youtube_videos ?? 0) + (rec?.coverage.instagram_posts ?? 0);
  const itemsUp = useCountUp(items, step >= 1);
  const fitUp = useCountUp(b?.creator_feature_score ?? 0, step >= 2);
  const moodUp = useCountUp(b?.sentiment_risk_score ?? 0, step >= 2);
  const finalUp = useCountUp(creator?.final_score ?? 0, step >= FINAL_STEP, 1300);
  const lit = (k: NodeKey) => step >= NODES[k].stage;

  const inner: Record<NodeKey, string> = {
    data: rec ? Math.round(itemsUp).toLocaleString("en-IN") : "…",
    features: fitUp.toFixed(2),
    graph: shortRank(b?.spillover_score),
    mood: moodUp.toFixed(2),
    value: shortRank(b?.value_score ?? null),
    fusion: "Σ",
  };
  const sub: Record<NodeKey, string> = {
    data: "videos and posts",
    features: "CLIP + BERT",
    graph: "network reach",
    mood: b ? moodWord(b.sentiment_risk_score) : "",
    value: "engagement per ₹",
    fusion: "0.4 · 0.3 · 0.3",
  };

  // Score ring: three arcs sized by each branch's contribution out of 100.
  const C = 2 * Math.PI * SCORE.r;
  const ringOn = step >= FINAL_STEP;
  const arcs: { k: string; len: number; offset: number; color: string }[] = [];
  let offset = 0;
  for (const [k, color] of [["value", NODES.value.color], ["mood", NODES.mood.color], ["fit", NODES.features.color]] as const) {
    const len = (Math.max(0, contrib[k]) / 100) * C;
    arcs.push({ k, len, offset, color });
    offset += len;
  }

  const shown = hover ?? focus;
  const detail = stages.find((s) => s.key === shown);
  const nodeProps = (k: NodeKey, label: string) => ({
    tabIndex: 0,
    role: "button" as const,
    "aria-label": `${label}: show details`,
    onClick: () => setFocus(k),
    onKeyDown: (e: React.KeyboardEvent) => (e.key === "Enter" || e.key === " ") && setFocus(k),
    onMouseEnter: () => setHover(k),
    onMouseLeave: () => setHover(null),
    style: { cursor: "pointer", outline: "none" },
  });

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-12">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-signal">Real data · live</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
          Pipeline Live
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">
          Watch one recommendation travel through the system: data in, four branches working in parallel, then the fusion that
          produces the score. Click or hover any stage to see its real numbers.
        </p>
      </header>

      <section className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-panel p-4">
        <label className="flex flex-col gap-1 text-xs text-zinc-400">
          Brief
          <select value={brief} onChange={(e) => setBrief(e.target.value)} className="rounded-md border border-line bg-background px-3 py-2 text-sm text-zinc-100">
            {BRIEFS.map((x) => (
              <option key={x.value} value={x.value}>
                {x.label}
              </option>
            ))}
          </select>
        </label>
        <button onClick={runBrief} disabled={running} className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background disabled:opacity-50">
          {running ? "Scoring…" : "Run brief"}
        </button>
        {result && (
          <label className="flex flex-col gap-1 text-xs text-zinc-400">
            Creator
            <select
              value={creator?.creator_id ?? ""}
              onChange={(e) => {
                setSelected(e.target.value);
                setFocus("fusion");
                play();
              }}
              className="max-w-xs rounded-md border border-line bg-background px-3 py-2 text-sm text-zinc-100"
            >
              {result.results.map((r) => (
                <option key={r.creator_id} value={r.creator_id}>
                  {r.name} · {r.final_score.toFixed(1)}
                </option>
              ))}
            </select>
          </label>
        )}
        {error && <p className="w-full text-sm text-red-400">{error}</p>}
      </section>

      {!creator && <p className="text-sm text-zinc-500">Run a brief to watch a creator travel through the pipeline.</p>}

      {creator && (
        <section className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => (animating ? setPlaying(false) : play(step >= FINAL_STEP))}
              className="rounded-md bg-accent px-4 py-1.5 text-sm font-semibold text-background"
            >
              {animating ? "❚❚ Pause" : step >= FINAL_STEP ? "▶ Play again" : "▶ Play"}
            </button>
            <button
              onClick={() => {
                setPlaying(false);
                setStep((s) => (s >= FINAL_STEP ? 1 : s + 1));
              }}
              className="rounded-md border border-line px-3 py-1.5 text-sm text-zinc-200 hover:border-accent hover:text-accent"
            >
              Step →
            </button>
            <ol className="ml-1 flex flex-wrap items-center gap-1 text-xs text-zinc-500" aria-label="Progress">
              {["Collect", "Analyse", "Combine", "Score"].map((t, i) => (
                <li key={t} className={`rounded-full px-2.5 py-1 transition-colors ${step > i ? "bg-accent-soft text-accent" : "border border-line"}`}>
                  {i + 1}. {t}
                </li>
              ))}
            </ol>
          </div>

          <div className="overflow-x-auto rounded-xl border border-line bg-panel">
            <svg viewBox={`0 0 ${VB.w} ${VB.h}`} className="block h-auto w-full min-w-[720px]" role="img" aria-label={`Pipeline for ${creator.name}`}>
              {BRANCHES.map((k) => (
                <Flow key={`in-${k}`} d={curve(NODES.data, NODES[k])} color={NODES[k].color} on={step >= 2} />
              ))}
              {BRANCHES.map((k) => (
                <Flow key={`out-${k}`} d={curve(NODES[k], NODES.fusion)} color={NODES[k].color} on={step >= 3} dashed={k === "graph"} />
              ))}
              <Flow d={scorePath} color={NODES.fusion.color} on={step >= FINAL_STEP} />

              {(Object.keys(NODES) as NodeKey[]).map((k) => {
                const n = NODES[k];
                const on = lit(k);
                const isFocus = shown === k;
                return (
                  <g key={k} {...nodeProps(k, n.label)}>
                    {on && <circle cx={n.x} cy={n.y} r={R + 11} fill={n.color} opacity={isFocus ? 0.24 : 0.1} className="pipe-glow" />}
                    <circle cx={n.x} cy={n.y} r={R} fill="#0a1016" stroke={on ? n.color : "#1e2b37"} strokeWidth={isFocus ? 3.5 : 2.5} style={{ transition: "stroke 400ms" }} />
                    <text x={n.x} y={n.y + 6} textAnchor="middle" fontSize={k === "fusion" ? 26 : 16} fontWeight={700} fill={on ? "#e8eef4" : "#4a5b6d"} fontFamily="var(--font-data)">
                      {on ? inner[k] : "·"}
                    </text>
                    <text x={n.x} y={n.y + R + 20} textAnchor="middle" fontSize={14} fontWeight={600} fill={on ? "#e8eef4" : "#63768a"}>
                      {n.label}
                    </text>
                    <text x={n.x} y={n.y + R + 36} textAnchor="middle" fontSize={12} fill="#8497aa">
                      {on ? sub[k] : ""}
                    </text>
                  </g>
                );
              })}

              <g {...nodeProps("fusion", "Final score")}>
                <circle cx={SCORE.x} cy={SCORE.y} r={SCORE.r} fill="none" stroke="#1e2b37" strokeWidth={12} />
                {arcs.map((a) => (
                  <circle
                    key={a.k}
                    cx={SCORE.x}
                    cy={SCORE.y}
                    r={SCORE.r}
                    fill="none"
                    stroke={a.color}
                    strokeWidth={12}
                    strokeDasharray={`${ringOn ? Math.max(0, a.len - 2) : 0} ${C}`}
                    strokeDashoffset={-a.offset}
                    transform={`rotate(-90 ${SCORE.x} ${SCORE.y})`}
                    style={{ transition: "stroke-dasharray 1.2s cubic-bezier(0.2,0.7,0.2,1)" }}
                  />
                ))}
                <text x={SCORE.x} y={SCORE.y + 9} textAnchor="middle" fontSize={28} fontWeight={700} fill="#e8eef4" fontFamily="var(--font-data)">
                  {ringOn ? finalUp.toFixed(1) : "—"}
                </text>
                <text x={SCORE.x} y={SCORE.y + SCORE.r + 26} textAnchor="middle" fontSize={14} fontWeight={600} fill="#e8eef4">
                  Final score
                </text>
                <text x={SCORE.x} y={SCORE.y + SCORE.r + 42} textAnchor="middle" fontSize={12} fill="#8497aa">
                  {ringOn ? `range ${creator.confidence_low.toFixed(0)}–${creator.confidence_high.toFixed(0)}` : ""}
                </text>
              </g>
            </svg>
          </div>

          <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-zinc-400">
            {([
              ["Value for money", NODES.value.color, contrib.value],
              ["Audience mood", NODES.mood.color, contrib.mood],
              ["Content fit", NODES.features.color, contrib.fit],
            ] as const).map(([label, color, pts]) => (
              <span key={label} className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
                {label}: <span className="font-mono text-zinc-100">{pts.toFixed(1)}</span> points
              </span>
            ))}
            <span className="flex items-center gap-1.5">
              <svg width="22" height="6" aria-hidden>
                <line x1="0" y1="3" x2="22" y2="3" stroke={NODES.graph.color} strokeWidth="2" strokeDasharray="5 5" />
              </svg>
              Network: reported alongside the score
            </span>
          </div>

          {detail && (
            <div className="rounded-xl border bg-panel p-4" style={{ borderColor: NODES[shown].color }}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-base font-semibold text-zinc-50">{detail.title}</h2>
                <span className="text-xs text-zinc-500">{detail.model}</span>
              </div>
              <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
                {detail.lines.map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3 border-b border-line/60 py-1">
                    <dt className="text-zinc-400">{k}</dt>
                    <dd className="font-mono text-zinc-100">{v}</dd>
                  </div>
                ))}
              </dl>
              {detail.note && <p className="mt-2 text-xs text-zinc-500">{detail.note}</p>}
              <p className="mt-2 text-[11px] text-zinc-600">Hover or click another stage in the diagram to see its numbers.</p>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
