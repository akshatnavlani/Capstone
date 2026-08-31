// Mirrors Track C's backend/app/schemas.py exactly (re-checked against
// origin/track-c-fusion-backend commit 65ec502, 2026-08-26 P1.6). See
// WIREFRAMES.md for the full mismatch history.

export type SpilloverBasis = "trained" | "inferred" | "placeholder" | "isolated";

export interface ScoreBreakdown {
  spillover_score: number; // nominal 0-1, but live GAIL can be >>1 (e.g. Virat 21.6) — render raw
  sentiment_risk_score: number; // 0-1 — STILL PLACEHOLDER 0.5 per CAPSTONE_NEXT_STEPS.md:822 (Temporal branch 0% built) — do not present as real
  creator_feature_score: number; // 0-1 — still placeholder 0.5 (CLIP/BERT not in this track)
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
  score_breakdown: ScoreBreakdown;
}

export interface BrandRecommendationResponse {
  query: BrandRecommendationRequest;
  results: InfluencerRecommendation[];
  is_mock_data: boolean;
  explanation?: string;
  counts?: { [k: string]: number };
}

// Subset of Track C's CreatorFeatureRecord (backend/app/schemas.py) -- only
// the fields needed to resolve a creator_id to a display name on /monitoring.
export interface CreatorSummary {
  creator_id: string; // uuid
  name: string;
}

export interface CollaborationEdge {
  source_creator_id: string;
  target_creator_id: string;
  weight: number;
}

export interface SponsorshipEdge {
  creator_id: string;
  brand_id: string;
  content_id: string;
  platform: "youtube" | "instagram" | "reddit";
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
}
