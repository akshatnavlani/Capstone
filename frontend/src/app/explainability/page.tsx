"use client";

import Link from "next/link";
import { useStoredRecommendationResult } from "@/lib/useStoredRecommendationResult";

// Full network-graph visualization needs Track B's graph data (GAIL branch
// isn't built yet — PROJECT_PLAN.md Section 3a / timeline weeks 11-13), so
// it's still a placeholder. But the weighted fusion formula and its inputs
// ARE real data already flowing through the app (same InfluencerRecommendation
// the dashboard renders), so that part is worth showing now rather than
// waiting for the network graph.

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
            const spilloverContribution = b.weight_spillover * b.spillover_score * 100;
            const sentimentContribution = b.weight_sentiment_risk * b.sentiment_risk_score * 100;
            const featureContribution = b.weight_creator_feature * b.creator_feature_score * 100;
            const weightedSum = spilloverContribution + sentimentContribution + featureContribution;
            // Derived, not authoritative: final_score = clamp(weightedSum + risk_adjustment, 0, 100)
            // per backend/app/fusion.py. If the server clamped the result, this back-calculated
            // figure won't match the real risk_adjustment. The true value isn't in
            // InfluencerRecommendation — only GET /scores/{creator_id} returns it directly.
            const derivedRiskAdjustment = influencer.final_score - weightedSum;

            return (
              <li
                key={influencer.creator_id}
                className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-800"
              >
                <h2 className="text-lg font-medium">{influencer.name}</h2>
                <p className="mt-1 font-mono text-xs text-zinc-500">
                  {influencer.final_score.toFixed(1)} = ({b.weight_spillover}×{b.spillover_score.toFixed(2)}
                  {" + "}
                  {b.weight_sentiment_risk}×{b.sentiment_risk_score.toFixed(2)}
                  {" + "}
                  {b.weight_creator_feature}×{b.creator_feature_score.toFixed(2)}) × 100
                  {derivedRiskAdjustment !== 0 && ` + ~${derivedRiskAdjustment.toFixed(1)} risk adjustment (derived, approximate)`}
                </p>

                <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
                  <Contribution label="Spillover (GAIL)" points={spilloverContribution} />
                  <Contribution label="Sentiment / Risk (Temporal)" points={sentimentContribution} />
                  <Contribution label="Creator Features" points={featureContribution} />
                </div>

                <p className="mt-3 text-xs text-zinc-500">
                  Confidence bounds {influencer.confidence_low.toFixed(0)}–
                  {influencer.confidence_high.toFixed(0)}.{" "}
                  {result.is_mock_data
                    ? "These are placeholder scores (is_mock_data) — the GAIL/Temporal branches aren't wired in yet."
                    : ""}
                </p>
              </li>
            );
          })}
        </ul>
      )}

      <p className="rounded-md border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
        Network-graph visualization of influencer/brand connections and
        posting-time/lag causal insights (Granger causality) aren&apos;t
        available yet — they depend on Track B&apos;s GAIL branch and graph
        data, which per the project timeline are built later (weeks 11-13
        onward), after the recommendation engine and fusion layer are stable.
      </p>
    </main>
  );
}

function Contribution({ label, points }: { label: string; points: number }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2 dark:bg-zinc-900">
      <div className="text-zinc-500">{label}</div>
      <div className="mt-1 font-medium">{points.toFixed(1)} pts</div>
    </div>
  );
}
