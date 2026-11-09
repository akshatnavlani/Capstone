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

export interface CreatorValue {
  platform: string;
  unit: string; // "views + likes" (YouTube) or "likes + comments" (Instagram)
  expected_engagement: number; // one sponsored post
  cost_tier: string | null;
  cost_low_inr: number;
  cost_mid_inr: number; // ESTIMATED, published rate card
  cost_high_inr: number;
  engagement_per_1000_inr: number;
  engagement_per_1000_inr_low: number;
  engagement_per_1000_inr_high: number;
  platform_percentile: number; // 0-100 within the same platform: the ranking key
  direct_basis: string; // "measured" | "prior"
  overseas: boolean;
  india_link: string | null;
  why: string[];
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
  estimated_cost: number | null; // ESTIMATED cost used for the budget filter: rate-card mid when value is set, else placeholder
  // Track A4: engagement per rupee, the ranking key (backend/app/creator_value.py). Optional for stale sessionStorage.
  value?: CreatorValue | null;
  // "exact": the brief's product words appear in the creator's profile text; "broader": added to fill a short list.
  product_match?: "exact" | "broader";
  data_coverage?: "youtube+instagram" | "youtube" | "instagram" | "none";
  // A-D: how much real data stands behind the score (backend/app/evidence.py). Optional for stale sessionStorage.
  evidence_grade?: "A" | "B" | "C" | "D";
  evidence_notes?: string[];
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
  category?: string | null; // the endpoint returns it; the graph colours nodes by it
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

/** Same creator on both platforms within 24 h, each measured against the creator's own usual (scripts/run_platform_pairs.py). */
export interface PairedEvidence {
  pairs: number;
  pairs_with_baseline: number;
  stronger_platform: "YouTube" | "Instagram" | "balanced" | "not enough pairs";
  median_difference_adjusted: number | null;
  text: string;
  as_of: string | null;
}

export interface PromotionBehaviour {
  disclosure: { sponsored_videos: number; disclosed: number; share: number; text: string } | null;
  response: {
    sponsored_videos: number;
    other_videos: number;
    intent_per_1000_sponsored: number;
    intent_per_1000_other: number;
    ratio: number;
    ci95: number[];
    verdict: string;
    text: string;
  } | null;
  as_of: string | null;
}

export interface PlatformProfile {
  creator_id: string;
  summary: string;
  youtube: PlatformSide;
  instagram: PlatformSide;
  paired: PairedEvidence | null;
  promotion?: PromotionBehaviour | null;
}

// GET /scenario/spillover (31 Oct 2026): the real graph and real current sponsorships with an ASSUMED spillover strength. An assumption, never an estimate; changes no score.
export interface SpilloverScenarioRow {
  creator_id: string;
  linked_collaborators: number;
  sponsored_collaborators: number;
  sponsored_names: string[];
  exposure: number; // 0-1
  projected_change_pct: number;
}

export interface SpilloverScenario {
  assumed_effect_log: number;
  window_days: number;
  creators_with_links: number;
  creators_exposed: number;
  note: string;
  rows: SpilloverScenarioRow[];
}

// GET /passport/* (1 Nov 2026): one record per creator gathering every analysis, each part with its own sample size. Read-only; changes no score.
export interface PassportCreatorLite {
  creator_id: string;
  name: string;
  category: string;
  platforms: string;
  grade: "A" | "B" | "C" | "D";
  mood_gap_flag: boolean;
  has_recent_brand_posts: boolean;
  sections_filled: number;
}

export interface PassportPenalty {
  sponsored_posts: number;
  matched: number;
  median_log_difference: number;
  approx_percent: number;
  enough: boolean;
}

export interface PassportBrandPost {
  brand: string;
  category: string;
  last_seen: string;
  tier: string | null;
  posts: number;
}

export interface PassportRecord {
  creator_id: string;
  name: string;
  category: string;
  coverage: { platforms: string; youtube_videos: number; instagram_posts: number; growth_readings: number };
  platform_strength: { pairs: number; stronger_platform: string; youtube_vs_usual_median: number; instagram_vs_usual_median: number; basis: string[] } | null;
  mood: {
    youtube?: { score: number; n: number };
    instagram?: { score: number; n: number };
    gap?: number;
    z?: number;
    significant?: boolean;
    label: string;
  } | null;
  speed: { videos: number; share_first_24h: number } | null;
  sponsored: {
    youtube_views: PassportPenalty | null;
    youtube_likes: PassportPenalty | null;
    instagram_likes: PassportPenalty | null;
    buying_signals: { sponsored_videos: number; other_videos: number; intent_per_1000_sponsored: number; intent_per_1000_other: number; ratio: number | null; ci95: [number, number] | null; verdict: string } | null;
    disclosure: { sponsored_videos: number; disclosed: number; share: number; ci95: [number, number]; label: string } | null;
  };
  fatigue: { sponsored_last_30d: number; usual_per_30d: number; above_usual: boolean } | null;
  network: { linked_creators: number; linked_sponsored_last_30d: number; shared_brand_creators: number };
  clash_events: PassportBrandPost[];
  predicted_instagram: { typical_likes: number; range_80: [number, number]; reliable: boolean } | null;
  evidence: { grade: "A" | "B" | "C" | "D"; notes: string[] };
}

export interface PassportPooled {
  creators: number;
  mean: number | null;
  ci95: [number, number] | null;
  approx_percent?: number;
  ci95_percent?: [number, number];
  placebo: { runs: number; mean: number | null; ci95: [number, number] | null };
}

export interface PassportSummary {
  as_of: string;
  summary: {
    creators: number;
    mood_gap: { creators_with_both: number; flagged: number; warmer_on_instagram: number; warmer_on_youtube: number; median_gap: number | null; note: string };
    sponsored_response: { youtube_views: PassportPooled; youtube_likes: PassportPooled; instagram_likes: PassportPooled; note: string };
    speed: { videos: number; creators: number; median_share_first_24h: number | null; note: string };
    prediction: { n: number; mae_average?: number; mae_size_only?: number; mae_full?: number; spearman_size_only?: number; spearman_full?: number; beats_size_only?: boolean; residual_p10_p90?: [number, number] };
    fatigue: { creators_above_usual: number; global_test: { median_slope: number; ci95: [number, number]; creators: number }; note: string };
    clash: { creators_with_recent_brand_posts: number; window_days: number };
  };
  limits: string[];
}

export interface ClashResult {
  category: string | null;
  window_days: number | null;
  creators: Record<string, { brands: PassportBrandPost[]; total_brands: number }>;
}

// GET /passport/insights (1 Nov 2026): the numbers behind the Insights charts, all read from result files. Blocks marked simulated must be labelled so on screen.
export interface InsightsData {
  spillover_journey: { source: string; rows: { label: string; exposed: number; effect: number; lo: number; hi: number }[] };
  benchmark: { source: string; simulated: boolean; metric: string; methods: string[]; settings: { setting: string; errors: Record<string, number | null> }[] };
  published_baselines: {
    source: string; graph: string; replicates: number; true_mean_effect: number; metric: string; caveat: string;
    rows: { method: string; no_trend: number; pre_trend: number }[];
  } | null;
  power: { source: string; simulated: boolean; effects: number[]; real_exposed: number | null; series: { n: number; share: number[] }[] };
  passport: {
    source: string; as_of: string | null; creators: number;
    mood_gaps: { gap: number; flagged: boolean }[]; speed_shares: number[]; grades: Record<"A" | "B" | "C" | "D", number>;
    sponsored_response: Record<"youtube_views" | "youtube_likes" | "instagram_likes", { creators: number; mean: number | null; ci95: [number, number] | null; approx_percent?: number; ci95_percent?: [number, number] }> | null;
    prediction: { n: number; spearman_full?: number; spearman_size_only?: number; mae_full?: number; mae_size_only?: number } | null;
    mood_gap_summary: { creators_with_both: number; flagged: number; warmer_on_instagram: number; warmer_on_youtube: number } | null;
    clash: { creators_with_recent_brand_posts: number; window_days: number } | null;
  };
  fusion_simulation: { source: string; simulated: boolean; scenarios: Record<string, Record<string, { spearman: number; top20_of_20: number }>> };
  extensions: { source: string; simulated: boolean; e4: Record<string, { pehe: { mean: number } }> | null; e5: Record<string, { true_ate: number; naive_ate: { mean: number }; simex_ate: { mean: number } }> | null };
}

// GET /passport/strip: compact Passport facts for the dashboard cards. A missing part is null, never guessed.
export interface PassportStrip {
  grade: "A" | "B" | "C" | "D";
  mood: { gap: number | null; significant: boolean; label: string | null } | null;
  speed_first_24h: number | null;
  ad_load: { sponsored_last_30d: number; usual_per_30d: number; above_usual: boolean } | null;
  sponsored_views_percent: number | null;
  linked_creators: number;
  recent_brands: number;
}
