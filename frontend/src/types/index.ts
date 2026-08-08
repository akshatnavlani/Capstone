// Mirrors Track C's backend/app/schemas.py exactly (re-checked against
// origin/track-c-fusion-backend on 2026-08-09, after their same-day breaking
// change: creator_unique_id: str -> creator_id: uuid.UUID). See WIREFRAMES.md
// for the full mismatch history.

export interface ScoreBreakdown {
  spillover_score: number; // 0-1
  sentiment_risk_score: number; // 0-1
  creator_feature_score: number; // 0-1
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
  estimated_reach: number | null;
  estimated_cost: number | null; // placeholder cost heuristic used for budget filtering
  score_breakdown: ScoreBreakdown;
}

export interface BrandRecommendationResponse {
  query: BrandRecommendationRequest;
  results: InfluencerRecommendation[];
  is_mock_data: boolean;
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
  created_at: string;
  resolved: boolean;
}
