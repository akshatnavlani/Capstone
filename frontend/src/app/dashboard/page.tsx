"use client";

import Avatar from "@/components/Avatar";
import { useEffect, useState } from "react";
import Link from "next/link";
import SpilloverBadge from "@/components/SpilloverBadge";
import EvidenceBadge from "@/components/EvidenceBadge";
import { getAlerts, getClash, getPassportStrip, getSpilloverScenario } from "@/lib/api";
import { useStoredRecommendationResult } from "@/lib/useStoredRecommendationResult";
import type { AlertResponse, ClashResult, PassportStrip, SpilloverBasis, SpilloverScenario } from "@/types";
import NoveltyStrip from "@/components/NoveltyStrip";
import PlatformProfileCard from "@/components/PlatformProfileCard";

// Reads the /recommendations response left in sessionStorage by the
// brand-input form. Risk-flag badges are NOT part of InfluencerRecommendation
// (see WIREFRAMES.md mismatch notes) — they come from a separate GET /alerts
// call, matched client-side by creator_id.

export default function DashboardPage() {
  const result = useStoredRecommendationResult();
  const [alertsByCreator, setAlertsByCreator] = useState<Map<string, AlertResponse[]>>(new Map());
  // What-if spillover (31 Oct 2026): the real graph and real current sponsorships with an assumed strength the user picks. Never changes a score.
  const [assumed, setAssumed] = useState(0);
  const [loaded, setLoaded] = useState<SpilloverScenario | null>(null);
  const [scenarioError, setScenarioError] = useState(false);
  // Competitor clash (1 Nov 2026): creators who recently promoted a rival brand in the brief's category. A warning only; never changes a score.
  const [clash, setClash] = useState<ClashResult | null>(null);
  const product = result?.query.product_category;
  // Creator Passport facts for the cards (1 Nov 2026): mood gap, day-1 views, ad load, sponsored response, links. Facts only; no score changes.
  const [strips, setStrips] = useState<Record<string, PassportStrip>>({});
  const idKey = result?.results.map((r) => r.creator_id).join(",") ?? "";

  useEffect(() => {
    if (!idKey) return;
    let cancelled = false;
    getPassportStrip(idKey.split(","))
      .then((m) => !cancelled && setStrips(m))
      .catch(() => {
        // The strip is supplementary; a failed fetch just shows none.
      });
    return () => {
      cancelled = true;
    };
  }, [idKey]);

  useEffect(() => {
    if (!product) return;
    let cancelled = false;
    getClash(product)
      .then((c) => !cancelled && setClash(c))
      .catch(() => {
        // The clash warning is supplementary; a failed fetch just shows none.
      });
    return () => {
      cancelled = true;
    };
  }, [product]);

  useEffect(() => {
    if (assumed === 0) return;
    let cancelled = false;
    getSpilloverScenario(assumed)
      .then((s) => {
        if (cancelled) return;
        setLoaded(s);
        setScenarioError(false);
      })
      .catch(() => !cancelled && setScenarioError(true));
    return () => {
      cancelled = true;
    };
  }, [assumed]);
  // Only show a scenario that belongs to the strength now selected (a stale one is hidden while the next loads).
  const scenario = assumed !== 0 && loaded && loaded.assumed_effect_log === assumed ? loaded : null;
  const scenarioByCreator = new Map((scenario?.rows ?? []).map((r) => [r.creator_id, r]));

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

  // Creators whose profile text contains the brief's words; the rest were added as "broader" matches to fill the list.
  const exactCount = result.results.filter((r) => r.product_match !== "broader").length;
  const weakMatch = !result.is_mock_data && result.results.length > 0 && exactCount < Math.min(3, result.results.length);

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
          Showing demo data — the creator table was empty when queried, so built-in example creators are shown.
        </p>
      )}

      {weakMatch && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
          No strong match in our data: only {exactCount} of the {result.results.length} creators below mention &quot;{result.query.product_category}&quot; in their profile. The rest are broader matches added to fill the list, so use this ranking as a rough guide. Our data is strongest
          for fitness, sport and lifestyle creators.
        </p>
      )}

      <div className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor="spillover-what-if" className="font-medium">
            Spillover what-if
          </label>
          <select
            id="spillover-what-if"
            value={assumed}
            onChange={(e) => setAssumed(Number(e.target.value))}
            className="rounded-md border border-zinc-300 bg-transparent px-2 py-1 text-xs focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30 dark:border-zinc-700"
          >
            <option value={0}>Off</option>
            <option value={0.25}>If spillover were +28% (mild)</option>
            <option value={0.5}>If spillover were +65% (moderate)</option>
            <option value={1}>If spillover were +172% (strong)</option>
          </select>
          {scenario && (
            <span className="text-xs text-zinc-500">
              {scenario.creators_exposed} of {scenario.creators_with_links} linked creators have a collaborator sponsored in the last {scenario.window_days} days
            </span>
          )}
        </div>
        <p className="mt-2 text-xs text-zinc-500">
          {scenario
            ? scenario.note
            : "The real data shows no detectable spillover, so no creator has a measured spillover. This switch shows who spillover would reach if it had the strength you pick. It is an assumption and never changes a score."}
        </p>
        {scenarioError && <p className="mt-1 text-xs text-red-600 dark:text-red-400">Couldn&apos;t load the scenario. Is the backend running?</p>}
      </div>

      <ul className="flex flex-col gap-4">
        {result.results.map((influencer, index) => {
          const alerts = alertsByCreator.get(influencer.creator_id) ?? [];
          const basis = (influencer.spillover_basis ?? "placeholder") as SpilloverBasis;
          const spilloverRaw = influencer.score_breakdown.spillover_score;
          return (
            <li
              key={influencer.creator_id}
              className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-800"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span className="text-xs font-medium text-zinc-500">#{index + 1}</span>
                  <h2 className="flex items-center gap-2.5 text-lg font-medium"><Avatar creatorId={influencer.creator_id} name={influencer.name} size={36} />{influencer.name}</h2>
                  <p className="text-xs text-zinc-500">
                    {[influencer.youtube_handle, influencer.instagram_handle, ...influencer.reddit_handles]
                      .filter(Boolean)
                      .join(" · ") || "no linked handles"}
                  </p>
                  {influencer.value ? (
                    <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
                      <p>
                        <span className="font-medium">
                          {Math.round(influencer.value.engagement_per_1000_inr).toLocaleString("en-IN")} {influencer.value.unit} per ₹1,000
                        </span>{" "}
                        on {influencer.value.platform} (range {Math.round(influencer.value.engagement_per_1000_inr_low).toLocaleString("en-IN")}–
                        {Math.round(influencer.value.engagement_per_1000_inr_high).toLocaleString("en-IN")}) · better than{" "}
                        {influencer.value.platform_percentile.toFixed(0)}% of {influencer.value.platform} creators
                      </p>
                      <p className="text-zinc-500">
                        est. cost ₹{Math.round(influencer.value.cost_mid_inr).toLocaleString("en-IN")} (estimate from a published rate card, range ₹
                        {Math.round(influencer.value.cost_low_inr).toLocaleString("en-IN")}–₹{Math.round(influencer.value.cost_high_inr).toLocaleString("en-IN")})
                      </p>
                      <details className="mt-0.5 text-zinc-500">
                        <summary className="cursor-pointer">Why this rank</summary>
                        <ul className="mt-1 list-disc pl-5">
                          {influencer.value.why.map((w) => (
                            <li key={w}>{w}</li>
                          ))}
                        </ul>
                      </details>
                    </div>
                  ) : (
                    influencer.estimated_cost != null && (
                      <p className="mt-1 text-xs text-zinc-500">
                        est. cost ₹{influencer.estimated_cost.toLocaleString()} (placeholder rate; no recent posts to rank by engagement per rupee)
                      </p>
                    )
                  )}
                  <div className="mt-2 flex items-center gap-2">
                    <SpilloverBadge basis={basis} />
                    {influencer.evidence_grade && <EvidenceBadge grade={influencer.evidence_grade} />}
                    {influencer.data_coverage === "none" && (
                      <span className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                        no data collected yet — score rests on category and graph only
                      </span>
                    )}
                    {influencer.product_match === "broader" && (
                      <span className="rounded-full border border-zinc-300 px-2 py-0.5 text-[11px] text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
                        broader match — product words not in profile
                      </span>
                    )}
                  </div>
                  <NoveltyStrip s={strips[influencer.creator_id]} />
                  {influencer.evidence_notes && influencer.evidence_notes.length > 0 && (
                    <details className="mt-1 text-xs text-zinc-500">
                      <summary className="cursor-pointer">Why evidence grade {influencer.evidence_grade}</summary>
                      <ul className="mt-1 list-disc pl-5">
                        {influencer.evidence_notes.map((n) => (
                          <li key={n}>{n}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {(() => {
                    const c = clash?.creators[influencer.creator_id];
                    if (!c) return null;
                    return (
                      <p className="mt-1 rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-300">
                        <span className="font-medium">Possible brand clash: </span>
                        promoted {c.brands.slice(0, 2).map((b) => `${b.brand} (${b.last_seen})`).join(", ")}
                        {c.total_brands > 2 ? ` and ${c.total_brands - 2} more` : ""} in the last {clash?.window_days} days (same category: {clash?.category}). Check exclusivity before booking.
                      </p>
                    );
                  })()}
                  {basis === "isolated" && (
                    <p className="mt-1 text-xs text-zinc-500">
                      no graph signal — degree 0 on collaborates_with + co_occurs_with; placeholder 0.5, never inferred.
                    </p>
                  )}
                  {scenario && (() => {
                    const row = scenarioByCreator.get(influencer.creator_id);
                    return (
                      <p className="mt-1 rounded-md bg-violet-50 px-2 py-1 text-xs text-violet-800 dark:bg-violet-950/30 dark:text-violet-300">
                        <span className="font-medium">What-if, not measured: </span>
                        {!row
                          ? "no linked collaborators, so a spillover scenario does not reach this creator."
                          : row.sponsored_collaborators === 0
                            ? `${row.linked_collaborators} linked collaborator${row.linked_collaborators === 1 ? "" : "s"}, none sponsored in the last ${scenario.window_days} days: no spillover reaches this creator.`
                            : `${row.sponsored_collaborators} of ${row.linked_collaborators} linked collaborators sponsored recently (${row.sponsored_names.join(", ")}${row.sponsored_collaborators > row.sponsored_names.length ? " and more" : ""}): ${row.projected_change_pct >= 0 ? "+" : ""}${row.projected_change_pct.toFixed(0)}% expected engagement if spillover were that strong.`}
                      </p>
                    );
                  })()}
                </div>
                <div className="text-right">
                  <div className="text-2xl font-semibold">{influencer.final_score.toFixed(0)}</div>
                  <div className="text-xs text-zinc-500">
                    confidence {influencer.confidence_low.toFixed(0)}–{influencer.confidence_high.toFixed(0)}
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-400">basis: {basis}</p>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
                <ScorePart
                  label="Spillover"
                  value={spilloverRaw.toFixed(2)}
                  sublabel={
                    basis === "trained"
                      ? "percentile · trained, very small N · context, not scored"
                      : basis === "inferred"
                        ? "percentile · inferred, wide · context, not scored"
                        : "no graph signal · context, not scored"
                  }
                />
                <ScorePart
                  label="Sentiment / Risk"
                  value={influencer.score_breakdown.sentiment_risk_score.toFixed(2)}
                  sublabel="comment sentiment · 0.5 if none scored"
                />
                <ScorePart
                  label="Feature Score"
                  value={influencer.score_breakdown.creator_feature_score.toFixed(2)}
                  sublabel="brief relevance + reach · 0.5 if unknown"
                />
              </div>

              <PlatformProfileCard creatorId={influencer.creator_id} />

              <div className="mt-4 flex items-center gap-2">
                {alerts.length === 0 ? (
                  <span className="rounded-full border border-zinc-300 px-2 py-1 text-xs text-zinc-500 dark:border-zinc-700">
                    no active alerts
                  </span>
                ) : (
                  <span className="rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-800 dark:bg-red-900/40 dark:text-red-300">
                    {alerts.length} alert{alerts.length > 1 ? "s" : ""}
                  </span>
                )}
                <Link href={`/passport?creator=${influencer.creator_id}`} className="ml-auto text-xs font-medium text-accent underline">
                  Creator Passport
                </Link>
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
