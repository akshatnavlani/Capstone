// Shape of GET /analysis (backend/app/routers/analysis.py), written by
// scripts/export_analysis_dashboard.py. Only the fields the Analysis tab reads.

export interface SentimentSummary {
  scored: number;
  total: number;
  mean: number;
  min: number;
  max: number;
  histogram: { lo: number; hi: number; n: number }[];
  lowest: { name: string; safety: number; comments: number }[];
  highest: { name: string; safety: number; comments: number }[];
}

export interface PostingLag {
  cause: string;
  effect: string;
  bin_hours: number;
  creators_with_both: number;
  creators_usable: number;
  best_lag_hours: number;
  best_corr: number;
  lag_p_value: number;
  profile: Record<string, number>;
  granger_creators: number;
  granger_combined_p: number;
}

export interface EventLagRow {
  pairs?: number;
  usable: number;
  cross_platform?: boolean;
  excess?: number[];
  p?: number[];
  labels?: string[];
}

export interface SameCreatorLag {
  creators: string[];
  lags: number[];
  pairs: number[];
  corr: (number | null)[];
  p: number[];
  min_posts: number;
}

export interface Curve {
  name: string;
  youtube: [number, number][];
  instagram: [number, number][];
}

export interface Alert {
  severity: string;
  creator: string;
  source: string | null;
  reason: string;
}

export interface BriefTop {
  name: string;
  score: number;
  has_image: boolean;
  has_text: boolean;
  engagement: number | null;
  reach: number | null;
}

export interface CreatorMeta {
  id: string;
  name: string;
  category: string | null;
  basis: string;
}

export interface BriefInputs {
  spillover: number[];
  sentiment: number[];
  feature: number[];
}

export interface BriefSensitivity {
  near: { top10_overlap_median: number; top10_overlap_min: number; spearman_median: number; spearman_min: number };
  all: { top10_overlap_median: number; top10_overlap_min: number; spearman_median: number; spearman_min: number };
}

export interface DemoCounts {
  considered: number;
  budget: number;
  region: number;
  product: number;
  kept: number;
}

export interface CostRow {
  budget: number;
  model: string;
  eligible: number;
  eligible_flat: number;
  jaccard: number;
  top10_overlap: number;
  flips: number;
}

export interface ProductRow {
  current: number;
  whole_word: number;
  stemmed: number;
  recoverable: number;
  substring_only_keeps: number;
}

export interface AnalysisData {
  generated_at: string;
  s1: {
    sentiment: SentimentSummary;
    alerts: Alert[];
    lag_posting: PostingLag[];
    lag_event: Record<string, EventLagRow>;
    lag_same_creator: SameCreatorLag;
    curves: Curve[];
  };
  s2: {
    auc: Record<string, Record<string, number>>;
    briefs: Record<string, BriefTop[]>;
    coverage: { creators: number; with_text: number; with_thumbnails: number; with_neither: number; with_engagement: number; with_reach: number };
  };
  s3: {
    calibration: {
      labelled_outcomes: number;
      association_with_lift: Record<string, { spearman: number; perm_p: number }>;
      per_brief: Record<string, BriefSensitivity>;
      ci_width_points: { min: number; median: number; max: number };
      ci_spans_whole_range: number;
      creators: number;
    };
    baseline_weights: number[];
    creators: CreatorMeta[];
    briefs: Record<string, BriefInputs>;
  };
  s7: {
    demo_query: Record<string, DemoCounts>;
    region: { dropped: number; india_evidence: number; iso_code_IN: number; foreign: number; unknown: number; india_in_name: string[] };
    product: Record<string, ProductRow>;
    noop: { no_region_signal: number; no_product_signal: number; creators: number };
    cost_stability: CostRow[];
    canary_athlete_5M_India: Record<string, number>;
    hand_review: {
      region_unknown_split: { india: number; foreign: number; cannot_tell: number; n: number };
      product_recovered_sensible: { correct: number; n: number };
      substring_only_keeps: { accidents: number; n: number };
    };
  };
  s8: {
    coverage: { creators: number; youtube: number; instagram: number; reddit: number; platforms_per_creator: Record<string, number>; multi_platform: number };
    youtube: { links: number; evidence: Record<string, number>; how_obtained: Record<string, number> };
    instagram: { with_handle: number; profile_fetched: number; never_fetched: number; verified: number; linked_profiles: number; name_is_handle: number };
    reddit: {
      links: number;
      name_evidenced_strict: number;
      pairs: number;
      pairs_naming_both_strict: number;
    };
    reddit_roster_posts: { posts_8plus: number; pairs_only_from_them: number; pairs: number };
    post_ownership: {
      audited: number;
      wrong_at_audit: number;
      still_wrong_today: number;
      posts_total: number;
      sponsored_total: number;
      sponsored_audited: number;
      wrong_pre_filter: [number, number];
      wrong_post_filter: [number, number];
      unaudited_pre_filter: number;
      unaudited_sponsored_pre_filter: number;
    };
    null_creator_events: { events_without_creator: number; events: number };
    cross_platform_pairs: {
      pairs: number;
      by_platform_combo: Record<string, number>;
      measured_on_2plus: number;
      pair_count_meta: { computable_pairs: number; same_platform_computable: number; cross_platform_only: number; effective_N_labeled_nodes: number };
    };
    collaboration_edges: { related_rows: number; pairs: number; mutual: number; team_or_league_pairs: number; same_entity: string[][]; top_hubs: [string, number][] };
    hand_review: {
      reddit_strict_sample: { correct: number; n: number };
      reddit_weak_sample: { correct: number; wrong: number; unclear: number; n: number };
      collab_pairs_sample: { plausible: number; same_entity: number; cannot_judge: number; clearly_false: number; n: number };
      non_creator_accounts: { low: number; high: number; reviewed: number; classifier_flags: number };
      youtube_doubtful: { low: number; high: number; links: number };
    };
  };
}
