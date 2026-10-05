"use client";

import Link from "next/link";
import CreatorGraph from "@/components/CreatorGraph";
import SpilloverBadge from "@/components/SpilloverBadge";
import { useStoredRecommendationResult } from "@/lib/useStoredRecommendationResult";
import type { SpilloverBasis } from "@/types";

// Two parts: the creator graph GAIL reads (live edges from /feature-store/edges/*,
// PendingWork S6) and, per creator, the weighted fusion formula with its inputs
// (same InfluencerRecommendation the dashboard renders).

export default function ExplainabilityPage() {
  const result = useStoredRecommendationResult();

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Explainability</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          The creator graph the model reads, and why each score came out the
          way it did.
        </p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium">Creator graph</h2>
        <CreatorGraph results={result?.results ?? null} />
      </section>

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

                <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
                  <Contribution
                    label="Spillover (GAIL)"
                    points={spilloverContribution}
                    hint={
                      basis === "trained"
                        ? "percentile of GAIL lift (N=10)"
                        : basis === "inferred"
                          ? "percentile of GAIL lift, wide"
                          : "neutral 0.5"
                    }
                  />
                  <Contribution
                    label="Sentiment / Risk (Temporal)"
                    points={sentimentContribution}
                    hint="comment sentiment, 0.5 if none scored"
                  />
                  <Contribution label="Creator Features" points={featureContribution} hint="brief relevance + reach, 0.5 if unknown" />
                </div>

                <p className="mt-3 text-xs text-zinc-500">
                  Confidence bounds {influencer.confidence_low.toFixed(0)}–
                  {influencer.confidence_high.toFixed(0)} (spillover basis: {basis}). The interval combines the
                  uncertainty of all three branches in quadrature: spillover (small-N), sentiment (fewer comments →
                  wider) and feature (no evidence → widest), clamped [0,100].{" "}
                  {result.is_mock_data ? "Demo creators: the creator table was empty." : ""}
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
        Not shown: which relationship type drove a creator&apos;s spillover (the
        learned per-relation weights are not served by the API yet), and
        posting-time lag insights. The 12-24h cross-platform lag was tested and
        is not supported by the available data.
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
