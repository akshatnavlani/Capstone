"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { getAlerts } from "@/lib/api";
import type { AlertResponse, BrandRecommendationResponse } from "@/types";

// Reads the /recommendations response left in sessionStorage by the
// brand-input form. Risk-flag badges are NOT part of InfluencerRecommendation
// (see WIREFRAMES.md mismatch notes) — they come from a separate GET /alerts
// call, matched client-side by creator_unique_id.

// sessionStorage is browser-only and can't be read during server prerender;
// useSyncExternalStore is the hydration-safe way to read it (getServerSnapshot
// returns null on the server, then React reconciles with the real client
// value after hydration) without a synchronous setState-in-effect.
function useStoredRecommendationResult(): BrandRecommendationResponse | null {
  const raw = useSyncExternalStore(
    () => () => {},
    () => sessionStorage.getItem("recommendationResult"),
    () => null
  );
  return raw ? (JSON.parse(raw) as BrandRecommendationResponse) : null;
}

export default function DashboardPage() {
  const result = useStoredRecommendationResult();
  const [alertsByCreator, setAlertsByCreator] = useState<Map<string, AlertResponse[]>>(new Map());

  useEffect(() => {
    getAlerts()
      .then((alerts) => {
        const map = new Map<string, AlertResponse[]>();
        for (const alert of alerts) {
          const existing = map.get(alert.creator_unique_id) ?? [];
          existing.push(alert);
          map.set(alert.creator_unique_id, existing);
        }
        setAlertsByCreator(map);
      })
      .catch(() => {
        // Alerts are supplementary here; a failed fetch just leaves badges empty.
      });
  }, []);

  if (!result) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-start gap-4 px-6 py-16">
        <h1 className="text-2xl font-semibold tracking-tight">Recommendation Dashboard</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          No recommendation query yet.
        </p>
        <Link href="/brand-input" className="text-sm font-medium underline">
          Start a brand request
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Recommendation Dashboard</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Results for &quot;{result.query.product_category}&quot;, budget ₹{result.query.budget.toLocaleString()}.
        </p>
      </div>

      {result.is_mock_data && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
          Showing mock/placeholder data — the real Fusion Layer model isn&apos;t wired in yet.
        </p>
      )}

      <ul className="flex flex-col gap-4">
        {result.results.map((influencer, index) => {
          const alerts = alertsByCreator.get(influencer.creator_unique_id) ?? [];
          return (
            <li
              key={influencer.creator_unique_id}
              className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-800"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span className="text-xs font-medium text-zinc-500">#{index + 1}</span>
                  <h2 className="text-lg font-medium">{influencer.name}</h2>
                  <p className="text-xs text-zinc-500">
                    {[influencer.youtube_handle, influencer.instagram_handle, influencer.reddit_handle]
                      .filter(Boolean)
                      .join(" · ") || "no linked handles"}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-semibold">{influencer.final_score.toFixed(0)}</div>
                  <div className="text-xs text-zinc-500">
                    confidence {influencer.confidence_low.toFixed(0)}–{influencer.confidence_high.toFixed(0)}
                  </div>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
                <ScorePart label="Spillover" value={influencer.score_breakdown.spillover_score.toFixed(2)} />
                <ScorePart
                  label="Sentiment / Risk"
                  value={influencer.score_breakdown.sentiment_risk_score.toFixed(2)}
                />
                <ScorePart
                  label="Feature Score"
                  value={influencer.score_breakdown.creator_feature_score.toFixed(2)}
                />
              </div>

              <div className="mt-4 flex gap-2">
                {alerts.length === 0 ? (
                  <span className="rounded-full border border-zinc-300 px-2 py-1 text-xs text-zinc-500 dark:border-zinc-700">
                    no active alerts
                  </span>
                ) : (
                  <span className="rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-800 dark:bg-red-900/40 dark:text-red-300">
                    {alerts.length} alert{alerts.length > 1 ? "s" : ""}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </main>
  );
}

function ScorePart({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2 dark:bg-zinc-900">
      <div className="text-zinc-500">{label}</div>
      <div className="mt-1 font-medium">{value}</div>
    </div>
  );
}
