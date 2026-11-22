"use client";

import { useEffect, useMemo, useState } from "react";
import { getPassport, postRecommendations } from "@/lib/api";
import { useStoredRecommendationResult } from "@/lib/useStoredRecommendationResult";
import type { BrandRecommendationResponse, InfluencerRecommendation, PassportRecord } from "@/types";

// Pipeline Live (22 Nov 2026, idea 1 of 3 Nov): one recommendation followed through every stage of the system, with the
// REAL numbers the API returns for that creator (POST /recommendations score_breakdown + GET /passport/{id}). Nothing here is
// simulated; a part the API does not return is shown as "not available", never guessed.

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

// A 0-1 percentile in brand words: "Top 4%" for high ranks, "Above 70%" style otherwise.
const rank = (s: number | null | undefined) =>
  s === null || s === undefined || Number.isNaN(s) ? "not available" : s >= 0.5 ? `Top ${Math.max(1, Math.round((1 - s) * 100))}%` : `Above ${Math.round(s * 100)}% of creators`;
const moodWord = (s: number) => (s >= 0.75 ? "very positive" : s >= 0.55 ? "positive" : s >= 0.3 ? "mixed" : "negative");

type Stage ={ key: string; title: string; model: string; lines: [string, string][]; note?: string };

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
      key: "features", title: "2 · Content understood", model: "CLIP (thumbnails) + BERT (titles, captions)",
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
        ["Direct collaborators", p ? (p.network.linked_creators > 0 ? int(p.network.linked_creators) : "None on record") : "not available"],
      ],
      note: "Network reach is reported alongside the score, so brands can weigh it themselves.",
    },
    {
      key: "mood", title: "4 · Audience mood", model: "RoBERTa (English) + XLM-R (Hindi script)",
      lines: [
        ["Audience mood", `${fmt(b.sentiment_risk_score)} · ${moodWord(b.sentiment_risk_score)}`],
        ["YouTube vs Instagram mood", p?.mood?.label ?? "not available"],
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

export default function PipelinePage() {
  const stored = useStoredRecommendationResult();
  const [fresh, setFresh] = useState<BrandRecommendationResponse | null>(null);
  const result = fresh ?? stored;
  const [brief, setBrief] = useState(BRIEFS[0].value);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [passport, setPassport] = useState<{ id: string; rec: PassportRecord | null } | null>(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);

  const creator = useMemo(() => {
    if (!result?.results.length) return null;
    return result.results.find((r) => r.creator_id === selected) ?? result.results[0];
  }, [result, selected]);

  useEffect(() => {
    if (!creator) return;
    let alive = true;
    getPassport(creator.creator_id)
      .then((rec) => alive && setPassport({ id: creator.creator_id, rec }))
      .catch(() => alive && setPassport({ id: creator.creator_id, rec: null }));
    return () => {
      alive = false;
    };
  }, [creator]);

  const stages = useMemo(
    () => (creator ? stagesFor(creator, passport?.id === creator.creator_id ? passport.rec : null) : []),
    [creator, passport]
  );

  // Animating only while stages remain; once every stage is lit the page shows them all.
  const animating = playing && step < stages.length;
  useEffect(() => {
    if (!animating) return;
    const t = setTimeout(() => setStep((s) => s + 1), 1100);
    return () => clearTimeout(t);
  }, [animating, step]);

  function play() {
    setStep(0);
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
      setStep(0);
      setPlaying(true);
    } catch {
      setError("Couldn't reach the backend at " + (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000") + ".");
    } finally {
      setRunning(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-12">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-signal">Real data · live</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
          Pipeline Live
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">
          Follow one recommendation through every stage of the system. Each box shows the real numbers the models produced for
          this creator; anything the API does not return says so.
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
                setStep(0);
                setPlaying(true);
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
        {creator && (
          <button onClick={play} className="rounded-md border border-line px-4 py-2 text-sm text-zinc-200 hover:border-accent hover:text-accent">
            ▶ Replay
          </button>
        )}
        {error && <p className="w-full text-sm text-red-400">{error}</p>}
      </section>

      {!creator && <p className="text-sm text-zinc-500">Run a brief to watch a creator flow through the pipeline.</p>}

      {creator && (
        <section aria-label="Pipeline stages" className="flex flex-col gap-0">
          {stages.map((s, i) => {
            const on = !animating || i < step;
            const active = animating && i === step - 1;
            return (
              <div key={s.key} className="flex flex-col items-stretch">
                {i > 0 && (
                  <div className="flex justify-center py-1" aria-hidden>
                    <svg width="16" height="36" viewBox="0 0 16 36">
                      <line x1="8" y1="0" x2="8" y2="36" stroke={on ? "var(--accent)" : "var(--line)"} strokeWidth="2" className={on ? "pipe-flow" : ""} />
                    </svg>
                  </div>
                )}
                <div
                  className={`rounded-xl border p-4 transition-all duration-500 ${
                    on ? "border-accent/60 bg-panel opacity-100" : "border-line bg-background opacity-40"
                  } ${active ? "shadow-[0_0_24px_rgba(245,184,61,0.25)]" : ""}`}
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h2 className="text-base font-semibold text-zinc-50">{s.title}</h2>
                    <span className="text-xs text-zinc-500">{s.model}</span>
                  </div>
                  <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
                    {s.lines.map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-3 border-b border-line/60 py-1">
                        <dt className="text-zinc-400">{k}</dt>
                        <dd className="font-mono text-zinc-100">{on ? v : "…"}</dd>
                      </div>
                    ))}
                  </dl>
                  {s.note && on && <p className="mt-2 text-xs text-zinc-500">{s.note}</p>}
                </div>
              </div>
            );
          })}
        </section>
      )}
    </main>
  );
}
