// Mirrors Track C's backend/app/schemas.py exactly (re-checked against
// origin/track-c-fusion-backend commit 65ec502, 2026-08-26 P1.6). See
// WIREFRAMES.md for the full mismatch history.

export type SpilloverBasis = "trained" | "inferred" | "placeholder" | "isolated";

export interface ScoreBreakdown {
  spillover_score: number; // 0-1: the creator's percentile among graph-connected creators (raw GAIL lift is unbounded); 0.5 = no graph signal
  sentiment_risk_score: number; // 0-1 — Temporal branch (comment sentiment + risk propagated from collaborators); 0.5 when the creator has no scored comments
  creator_feature_score: number; // 0-1 — CLIP/BERT relevance to the brief + engagement/reach percentile; 0.5 when nothing is known
  weight_spillover: number;
  weight_sentiment_risk: number;
  weight_creator_feature: number;
}

export interface BrandRecommendationRequest {
  product_category: string;
  budget: number; // INR, must be > 0 and finite
  target_region?: string;
  target_demographic?: string;
  platform_preference?: ("youtube" | "instagram" | "reddit")[];
  max_results?: number;
  // When fewer than max_results creators match the product words, fill the list with the best-scoring others,
  // each marked product_match "broader" (backend/app/schemas.py).
  include_broader_matches?: boolean;
}

export interface InfluencerRecommendation {
  creator_id: string; // uuid
  name: string;
  category: string | null;
  youtube_handle: string | null;
  instagram_handle: string | null;
  reddit_handles: string[]; // array, not a single handle
  final_score: number; // 0-100
  confidence_low: number;
  confidence_high: number;
  // Honest provenance per backend/app/schemas.py:65ec502 + API_CONTRACTS.md P1.6.
  // Optional for stale sessionStorage (old cache lacks field) — render fallback ?? "placeholder".
  spillover_basis?: SpilloverBasis;
  estimated_reach: number | null;
  estimated_cost: number | null; // placeholder cost heuristic used for budget filtering
  // "exact": the brief's product words appear in the creator's profile text; "broader": added to fill a short list.
  product_match?: "exact" | "broader";
  data_coverage?: "youtube+instagram" | "youtube" | "instagram" | "none";
  score_breakdown: ScoreBreakdown;
}

export interface BrandRecommendationResponse {
  query: BrandRecommendationRequest;
  results: InfluencerRecommendation[];
  is_mock_data: boolean;
}

// Subset of Track C's CreatorFeatureRecord (backend/app/schemas.py) -- only
// the fields needed to resolve a creator_id to a display name on /monitoring.
export interface CreatorSummary {
  creator_id: string; // uuid
  name: string;
}

// GET /feature-store/edges/collaborations and /edges/co-occurrence (same shape).
// weight = number of matched relations / co-occurrences between the pair.
export interface GraphEdge {
  source_creator_id: string; // uuid
  target_creator_id: string; // uuid
  weight: number;
}

export type AlertSeverity = "low" | "medium" | "high";

export interface AlertResponse {
  id: number;
  creator_id: string; // uuid
  // Server-side: AlertCreate.severity is a strict Literal["low","medium","high"],
  // but AlertResponse.severity is still typed as plain `str` on the read side
  // (not tightened) — assume the 3 values in practice, not contractually guaranteed.
  severity: AlertSeverity;
  reason: string;
  source: string;
  // Added by Track C 2026-08-09 ahead of Weeks 14-15 Sentiment Propagation.
  // The creator whose controversy caused this alert to propagate here, if any.
  // Expected to stay null until the Sentiment Propagation branch ships.
  propagated_from_creator_id: string | null;
  created_at: string;
  resolved: boolean;
  // Names come with the alert (GET /alerts); optional so older cached responses still type-check.
  creator_name?: string | null;
  propagated_from_name?: string | null;
}

/** GET /platform-profiles/{creator_id}: YouTube and Instagram status side by side (backend/app/platform_profile.py). */
export type PlatformStatus = "strong" | "typical" | "weak" | "unknown";

export interface FirstDayGrowth {
  items_with_a_first_day_reading: number;
  median_value_at_24h: number | null;
  median_share_of_current_total: number | null;
}

export interface PlatformSide {
  platform: "youtube" | "instagram";
  available: boolean;
  audience: number | null;
  items_total: number;
  items_with_counts: number;
  items_last_90_days: number;
  latest_item_at: string | null;
  typical_views: number | null;
  typical_likes: number | null;
  typical_comments: number | null;
  engagement_rate: number | null;
  views_per_subscriber: number | null;
  sponsored_vs_usual: number | null;
  status: PlatformStatus;
  percentile: number | null;
  first_day: FirstDayGrowth | null;
  notes: string[];
}

export interface PlatformProfile {
  creator_id: string;
  summary: string;
  youtube: PlatformSide;
  instagram: PlatformSide;
}
