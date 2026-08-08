// Expected shapes for the Track C (Fusion+Backend) API. Not yet confirmed against
// Track C's actual contract — see WIREFRAMES.md at the repo root for the
// cross-check note. Field names are our best guess based on PROJECT_PLAN.md
// Sections 1, 4, and 5.

export interface BrandInputRequest {
  product_category: string;
  budget_inr: number;
  region_proxy: string;
  demographic_proxy: string;
}

export interface ScoreBreakdown {
  spillover_score: number;
  sentiment_risk_score: number;
  feature_score: number;
}

export type RiskSeverity = "low" | "medium" | "high";

export interface RiskFlag {
  type: string;
  severity: RiskSeverity;
  message: string;
}

export interface InfluencerRecommendation {
  influencer_id: string;
  name: string;
  platform_handles: Partial<Record<"youtube" | "instagram" | "reddit", string>>;
  overall_score: number; // 0-100
  confidence_interval: [number, number];
  score_breakdown: ScoreBreakdown;
  risk_flags: RiskFlag[];
}

export interface MonitoringAlert {
  alert_id: string;
  influencer_id: string;
  influencer_name: string;
  alert_type: string;
  severity: RiskSeverity;
  detected_at: string; // ISO timestamp
  description: string;
  propagated_from_influencer_id?: string;
}
