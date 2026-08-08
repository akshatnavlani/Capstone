// Mirrors Track C's backend/app/schemas.py exactly (checked against
// origin/track-c-fusion-backend on 2026-08-09). See WIREFRAMES.md for the
// list of mismatches versus Track D's original Weeks 1-2 field-name guesses.

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
  budget: number; // INR
  target_region?: string;
  target_demographic?: string;
  platform_preference?: ("youtube" | "instagram" | "reddit")[];
  max_results?: number;
}

export interface InfluencerRecommendation {
  creator_unique_id: string;
  name: string;
  category: string | null;
  youtube_handle: string | null;
  instagram_handle: string | null;
  reddit_handle: string | null;
  final_score: number; // 0-100
  confidence_low: number;
  confidence_high: number;
  estimated_reach: number | null;
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
  creator_unique_id: string;
  severity: AlertSeverity;
  reason: string;
  source: string;
  created_at: string;
  resolved: boolean;
}
