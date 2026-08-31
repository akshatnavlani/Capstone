"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import SpilloverBadge from "@/components/SpilloverBadge";
import { useStoredRecommendationResult } from "@/lib/useStoredRecommendationResult";
import type { SpilloverBasis } from "@/types";

const CollabGraph = dynamic(() => import("@/components/CollabGraph"), { ssr: false });

// Weighted fusion inputs are real (same InfluencerRecommendation the dashboard
// renders). Graph is now interactive: vis-network/standalone over all 259
// creators, 340 collaborates_with + 1,414 co_occurs_with + 16 sponsorships
// (via GET /feature-store/edges/*, sponsorship populated by POST /labeling/run).
// The last brand query's active set (default 10, cap 50 — distinct from the
// ~54-pair GAIL supervision) is haloed inside the full 259. See
// backend/app/feature_store.py and CollabGraph.tsx.

export default function ExplainabilityPage() {
  const result = useStoredRecommendationResult();

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Explainability</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Why each score came out the way it did, plus network-graph causal
          insights once those are available.
        </p>
      </div>

      {!result && (
        <>
          <p className="text-sm text-zinc-500">
            No recommendation query yet — score breakdowns show up here once
            you have results.
          </p>
          <Link href="/brand-input" className="text-sm font-medium underline">
            Start a brand request
          </Link>
        </>
      )}

      {result && (
        <ul className="flex flex-col gap-4">
          {result.results.map((influencer) => {
            const b = influencer.score_breakdown;
            const basis = (influencer.spillover_basis ?? "placeholder") as SpilloverBasis;
            const spilloverContribution = b.weight_spillover * b.spillover_score * 100;
            const sentimentContribution = b.weight_sentiment_risk * b.sentiment_risk_score * 100;
            const featureContribution = b.weight_creator_feature * b.creator_feature_score * 100;

            return (
              <li
                key={influencer.creator_id}
                className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-800"
              >
                <div className="flex items-start justify-between gap-4">
                  <h2 className="text-lg font-medium">{influencer.name}</h2>
                  <SpilloverBadge basis={basis} influencerName={influencer.name} />
                </div>
                <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
                  <span className="font-medium">Final score {influencer.final_score.toFixed(1)}</span>
                  <span className="text-zinc-500"> — Spillover {spilloverContribution.toFixed(1)} pts (40%) + Sentiment {sentimentContribution.toFixed(1)} pts (30%) + Features {featureContribution.toFixed(1)} pts (30%)</span>
                </p>

                <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
                  <Contribution label="Spillover" points={spilloverContribution} />
                  <Contribution label="Sentiment / Risk" points={sentimentContribution} />
                  <Contribution label="Creator Features" points={featureContribution} />
                </div>

                <p className="mt-3 text-xs text-zinc-500">
                  Estimated range {influencer.confidence_low.toFixed(0)}–{influencer.confidence_high.toFixed(0)} for {influencer.name}.
                </p>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-2">
        <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Network graph — all 259 creators</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Full graph is always loaded (259 nodes, 340 collaborations + 1,414 co‑occurrences + 16 sponsorships — sponsorship non‑empty via{" "}
          <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">POST /labeling/run</code> disclose extraction). The active recommendation
          set (whatever <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">POST /recommendations</code> last returned — default 10, cap 50; the ~54‑pair
          GAIL supervision is distinct from this per‑query size) is haloed ★. Posting‑time / Granger‑causal insights remain future work.
        </p>
        <div className="mt-3">
          <CollabGraph />
        </div>
      </div>
    </main>
  );
}

function Contribution({ label, points, hint }: { label: string; points: number; hint?: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2 dark:bg-zinc-900">
      <div className="text-zinc-500">{label}</div>
      <div className="mt-1 font-medium">{points.toFixed(1)} pts</div>
      {hint && <div className="mt-0.5 text-[11px] text-zinc-500">{hint}</div>}
    </div>
  );
}
