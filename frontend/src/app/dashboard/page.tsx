"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import SpilloverBadge from "@/components/SpilloverBadge";
import { getAlerts } from "@/lib/api";
import { useStoredRecommendationResult } from "@/lib/useStoredRecommendationResult";
import type { AlertResponse, SpilloverBasis } from "@/types";

// Reads the /recommendations response left in sessionStorage by the
// brand-input form. Risk-flag badges are NOT part of InfluencerRecommendation
// (see WIREFRAMES.md mismatch notes) — they come from a separate GET /alerts
// call, matched client-side by creator_id.

export default function DashboardPage() {
  const result = useStoredRecommendationResult();
  const [alertsByCreator, setAlertsByCreator] = useState<Map<string, AlertResponse[]>>(new Map());

  useEffect(() => {
    getAlerts()
      .then((alerts) => {
        const map = new Map<string, AlertResponse[]>();
        for (const alert of alerts) {
          const existing = map.get(alert.creator_id) ?? [];
          existing.push(alert);
          map.set(alert.creator_id, existing);
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

  if (result.results.length === 0) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-start gap-4 px-6 py-16">
        <h1 className="text-2xl font-semibold tracking-tight">Recommendation Dashboard</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          No creators matched "{result.query.product_category}", budget ₹{result.query.budget.toLocaleString()}.
        </p>
        {result.explanation && (
          <p className="mt-2 rounded-md border border-zinc-300 p-3 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
            {result.explanation}
          </p>
        )}
        {result.counts && Object.values(result.counts).some(v => v > 0) && (
          <div className="mt-4 text-xs text-zinc-500 dark:text-zinc-400">
            <div>Considered: {result.counts.considered}</div>
            <div>Dropped by budget: {result.counts.dropped_by_budget}</div>
            <div>Dropped by platform: {result.counts.dropped_by_platform}</div>
            <div>Dropped by region: {result.counts.dropped_by_region}</div>
            <div>Dropped by demographic: {result.counts.dropped_by_demographic}</div>
            <div>Dropped by product category: {result.counts.dropped_by_product}</div>
          </div>
        )}
        <Link href="/brand-input" className="text-sm font-medium underline mt-4">
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
          Showing mock/placeholder data — some creators lack stored FusionScore or the creator table was empty when queried.
        </p>
      )}

      <ul className="flex flex-col gap-4">
        {result.results.map((influencer, index) => {
          const alerts = alertsByCreator.get(influencer.creator_id) ?? [];
          const basis = (influencer.spillover_basis ?? "placeholder") as SpilloverBasis;
          const spilloverRaw = influencer.score_breakdown.spillover_score;
          // Primary profile URL — priority instagram -> youtube -> reddit
          const profileUrl = (() => {
            const ig = influencer.instagram_handle?.replace(/^@/, "");
            if (ig) return `https://www.instagram.com/${ig}`;
            const yt = influencer.youtube_handle?.replace(/^@/, "");
            if (yt) return `https://www.youtube.com/@${yt}`;
            const rd = influencer.reddit_handles?.[0];
            if (rd) {
              const handle = rd.replace(/^u\//, "").replace(/^r\//, "");
              return rd.startsWith("r/") ? `https://www.reddit.com/r/${handle}` : `https://www.reddit.com/user/${handle}`;
            }
            return null;
          })();
          return (
            <li
              key={influencer.creator_id}
              className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-800"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span className="text-xs font-medium text-zinc-500">#{index + 1}</span>
                  {profileUrl ? (
                    <h2 className="text-lg font-medium">
                      <a href={profileUrl} target="_blank" rel="noopener noreferrer" className="underline decoration-zinc-300 underline-offset-4 hover:decoration-zinc-600">
                        {influencer.name}
                      </a>
                    </h2>
                  ) : (
                    <h2 className="text-lg font-medium">{influencer.name}</h2>
                  )}
                  <p className="text-xs text-zinc-500">
                    {(() => {
                      const links: React.ReactNode[] = [];
                      if (influencer.instagram_handle) {
                        const h = influencer.instagram_handle.replace(/^@/, "");
                        links.push(<a key="ig" href={`https://www.instagram.com/${h}`} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-zinc-700">{influencer.instagram_handle}</a>);
                      }
                      if (influencer.youtube_handle) {
                        const h = influencer.youtube_handle.replace(/^@/, "");
                        links.push(<a key="yt" href={`https://www.youtube.com/@${h}`} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-zinc-700">{influencer.youtube_handle}</a>);
                      }
                      influencer.reddit_handles.forEach((rh) => {
                        const clean = rh.replace(/^u\//, "").replace(/^r\//, "");
                        const url = rh.startsWith("r/") ? `https://www.reddit.com/r/${clean}` : `https://www.reddit.com/user/${clean}`;
                        links.push(<a key={rh} href={url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-zinc-700">{rh}</a>);
                      });
                      if (links.length === 0) return "no linked handles";
                      return links.reduce<React.ReactNode[]>((acc, cur, i) => (i === 0 ? [cur] : [...acc, " · ", cur]), []);
                    })()}
                  </p>
                  {influencer.estimated_cost != null && (
                    <p className="mt-1 text-xs text-zinc-500">
                      est. cost ₹{influencer.estimated_cost.toLocaleString()} (placeholder rate)
                    </p>
                  )}
                  <div className="mt-2">
                    <SpilloverBadge basis={basis} influencerName={influencer.name} />
                  </div>
                  {basis === "isolated" && (
                    <p className="mt-1 text-xs text-zinc-500">
                      no graph signal — degree 0 on collaborates_with + co_occurs_with; placeholder 0.5, never inferred.
                    </p>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-2xl font-semibold">{influencer.final_score.toFixed(0)}</div>
                  <p className="mt-1 text-[11px] text-zinc-400">basis: {basis}</p>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
                <ScorePart
                  label="Spillover"
                  value={spilloverRaw.toFixed(2)}
                />
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

function ScorePart({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: string;
  sublabel?: string;
}) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2 dark:bg-zinc-900">
      <div className="text-zinc-500">{label}</div>
      <div className="mt-1 font-medium">{value}</div>
      {sublabel && <div className="mt-0.5 text-[11px] text-zinc-500">{sublabel}</div>}
    </div>
  );
}
