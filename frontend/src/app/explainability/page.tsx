"use client";

import Link from "next/link";
import SpilloverBadge from "@/components/SpilloverBadge";
import { useStoredRecommendationResult } from "@/lib/useStoredRecommendationResult";
import type { SpilloverBasis } from "@/types";

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
            const basis = (influencer.spillover_basis ?? "placeholder") as SpilloverBasis;
            const spilloverContribution = b.weight_spillover * b.spillover_score * 100;
            const sentimentContribution = b.weight_sentiment_risk * b.sentiment_risk_score * 100;
            const featureContribution = b.weight_creator_feature * b.creator_feature_score * 100;
            const weightedSum = spilloverContribution + sentimentContribution + featureContribution;
            const derivedRiskAdjustment = influencer.final_score - weightedSum;
            const isOutOfRange = b.spillover_score < 0 || b.spillover_score > 1;

            return (
              <li
                key={influencer.creator_id}
                className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-800"
              >
                <div className="flex items-start justify-between gap-4">
                  <h2 className="text-lg font-medium">{influencer.name}</h2>
                  <SpilloverBadge basis={basis} />
                </div>
                {basis === "isolated" && (
                  <p className="mt-1 text-xs text-zinc-500">
                    no graph signal — degree 0 on collaborates_with + co_occurs_with; placeholder 0.5, never inferred.
                  </p>
                )}
                <p className="mt-2 font-mono text-xs text-zinc-500">
                  {influencer.final_score.toFixed(1)} = ({b.weight_spillover}×{b.spillover_score.toFixed(2)}
                  {" + "}
                  {b.weight_sentiment_risk}×{b.sentiment_risk_score.toFixed(2)}
                  {" + "}
                  {b.weight_creator_feature}×{b.creator_feature_score.toFixed(2)}) × 100
                  {derivedRiskAdjustment !== 0 && ` + ~${derivedRiskAdjustment.toFixed(1)} risk adjustment (derived, approximate)`}
                </p>
                {isOutOfRange && (
                  <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                    raw GAIL spillover {b.spillover_score.toFixed(2)} outside nominal 0-1; final_score clamped [0,100]
                  </p>
                )}

                <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
                  <Contribution
                    label="Spillover (GAIL)"
                    points={spilloverContribution}
                    hint={
                      basis === "trained"
                        ? "±13pts (N=10)"
                        : basis === "inferred"
                          ? "±21pts wide"
                          : "±10pts"
                    }
                  />
                  <Contribution
                    label="Sentiment / Risk (Temporal)"
                    points={sentimentContribution}
                    hint="placeholder 0.5 (Temporal 0%)"
                  />
                  <Contribution label="Creator Features" points={featureContribution} hint="placeholder 0.5" />
                </div>

                <p className="mt-3 text-xs text-zinc-500">
                  Confidence bounds {influencer.confidence_low.toFixed(0)}–
                  {influencer.confidence_high.toFixed(0)} (basis: {basis}
                  {basis === "trained"
                    ? ", hw≈3.28 → ±13pts"
                    : basis === "inferred"
                      ? ", hw≈5.25 → ±21pts wide"
                      : ", hw 0.25 → ±10pts"}
                  ; sentiment is still placeholder per CAPSTONE_NEXT_STEPS:822).{" "}
                  {result.is_mock_data ? "is_mock_data true — at least one creator lacked a stored FusionScore or creator table was empty." : ""}
                </p>
                <p className="mt-1 text-xs text-zinc-400">
                  {basis === "trained" && "Trained on N=10 labeled nodes — still wide CI due small-N + propensity 1.000. See API_CONTRACTS.md P1.6."}
                  {basis === "inferred" && "Inferred — graph-connected but unlabeled; GAT inductive, not validated. Wide CI by design."}
                  {basis === "placeholder" && "Placeholder — checkpoint/fallback 0.5, no GAIL signal."}
                  {basis === "isolated" && "Isolated — no graph signal, never inferred; placeholder 0.5."}
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

function Contribution({ label, points, hint }: { label: string; points: number; hint?: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2 dark:bg-zinc-900">
      <div className="text-zinc-500">{label}</div>
      <div className="mt-1 font-medium">{points.toFixed(1)} pts</div>
      {hint && <div className="mt-0.5 text-[11px] text-zinc-500">{hint}</div>}
    </div>
  );
}
