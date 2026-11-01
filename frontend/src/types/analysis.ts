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
  fixed: number;
}

export interface S9Estimate {
  difference_in_means: number;
  difference_in_means_ci: [number, number];
  difference_in_means_excludes_zero: boolean;
  n_exposed: number;
  n_unexposed: number;
}

export interface SemiSynthCell {
  mean_estimate: number;
  error_vs_truth: number;
  detects_effect_share: number;
}

/** Live results added 2026-10-26: lag on the growth readings, spillover on the real network, a simulated detection curve, and the data inventory. */
export interface S9Data {
  as_of: string;
  inventory: Record<string, number>;
  spillover_basis_counts: Record<string, number>;
  graph_links: { of: number; today: number; shared_brand_alone: number; with_shared_brand: number; mentions_alone?: number; with_shared_brand_and_mentions?: number };
  placebo: {
    scopes: Record<
      "in_the_150" | "everyone",
      Record<
        "all" | "mature",
        {
          event_rows: number;
          with_placebo: number;
          median_paired_difference?: number;
          share_event_higher_than_placebo?: number;
          per_neighbour?: { n: number; median_of_means: number; ci: [number, number]; events_beat_placebo: number };
          per_sponsoring_creator?: { n: number; median: number; ci: [number, number] };
        }
      >
    >;
  };
  lag: {
    days_of_readings: number;
    method_check: string;
    limits: string;
    results: {
      name: string;
      n_units: number;
      n_creators: number;
      smallest_p_after_event: number;
      window_of_smallest_p: string;
      detected_after_correction: boolean;
      note?: string | null;
    }[];
  };
  /** SIMULATED validation on the real network (scripts/sim_semisynthetic_benchmark.py). */
  semisynthetic?: {
    simulated: boolean;
    real_rows: number;
    real_neighbours: number;
    assumptions: Record<string, string | number>;
    table: Record<string, { naive: SemiSynthCell; placebo: SemiSynthCell }>;
    table_effect_reaches_20_percent_of_neighbours: Record<string, { naive: SemiSynthCell; placebo: SemiSynthCell }>;
  };
  /** SIMULATED: extra attention planted after real Instagram posts (scripts/sim_lag_power.py). */
  sim_lag_power?: { simulated: boolean; how: string; sets: Record<string, { units: number; creators: number; by_size: Record<string, { detected_share: number; median_smallest_p: number | null }> }> };
  label_quality?: {
    labelled_rows: number;
    claude_text_only_readings?: { decided_flagged_events: number; look_sponsored: number; share: number; wilson95: [number, number] };
    human_checked_precision_by_tier: Record<string, { real_ads: number; checked: number; precision: number }>;
    pooled_precision_checked_flagged_events: { real_ads: number; checked: number; precision: number; wilson95: [number, number] };
    grouped_cv_flagged_events_only?: Record<"text_and_tier" | "tier_only", { auc: number }>;
    unchecked_weak_tier_events_in_spillover_pairs: number;
  };
  spillover_restricted_150: Record<"shared_brand" | "collaboration", Record<string, S9Estimate>>;
  power_curve: {
    exposed: number;
    "effect_0.25": number;
    "effect_0.50": number;
    "effect_0.75": number;
    "effect_1.00": number;
    false_alarm: number;
  }[];
  /** Hybrid what-if (31 Oct 2026): simulated extra exposed creators on real outcomes. Never a result. */
  power_curve_simulated?: {
    exposed: number;
    "effect_0.25": number;
    "effect_0.50": number;
    "effect_0.75": number;
    "effect_1.00": number;
    false_alarm: number;
  }[];
  power_real_exposed?: number;
  /** SIMULATED: GAIL-R error as the number of exposed creators grows (real graph, planted effect). */
  gail_scaling?: { planted_effect: number; noise: number; rows: { scenario: string; exposed: number; mean_abs_error: number; reps: number }[] } | null;
  /** Sensitivity of the real null result to missed sponsorship labels (31 Oct 2026). */
  /** Real exposed cases (a linked collaborator posted a sponsored video) with the unexposed base rate; an illustration, not proof. */
  spillover_cases?: {
    summary: { exposed: number; unexposed: number; median_lift_exposed: number; median_lift_unexposed: number; share_above_0_5_exposed: number; share_above_0_5_unexposed: number };
    top_cases: { creator: string; category: string; window: string[]; lift: number; sponsoring_collaborator: string | null; sponsored_video: string | null; sponsored_on: string | null }[];
    reading: string;
  } | null;
  label_noise?: { rows: { share_of_comparison_group_truly_exposed: number; corrected_estimate: number; ci95: [number, number]; upper_bound_as_engagement_ratio: number }[]; reading: string } | null;
  /** E4 (attention supervision) and E5 (mismeasured treatment): SIMULATED benchmark with known truth, plus the real-data E5 sensitivity. */
  e4_e5?: {
    reps: number;
    e4_simulated: Record<string, { pehe: { mean: number; sd: number }; abs_error_of_mean_effect: { mean: number; sd: number } }>;
    e5_simulated: Record<string, { true_ate: number; naive_ate: { mean: number }; simex_ate: { mean: number }; naive_abs_error: number; simex_abs_error: number }>;
    e5_real: Record<string, { naive: Record<string, number>; corrected: Record<string, number> }>;
  } | null;
}

/** Added 2026-10-30: YouTube-vs-Instagram comparison, Granger, ad fatigue, long lag, promotion behaviour, GAIL real-data results and the power analysis. */
export interface S10Data {
  pairs: {
    window_hours: number;
    pairs: number;
    creators_with_pairs: number;
    median_difference: number;
    median_difference_adjusted: number;
    share_pairs_instagram_better_adjusted: number;
    pairs_with_text_overlap: number;
    median_difference_with_overlap: number;
    placebo: { runs: number; median_difference_placebo: number; share_instagram_better_placebo: number };
    calibration_subtracted: number;
    granger: Record<string, { creators: number; tests: Record<string, { F: number; placebo_F_median: number; p_value: number }> }>;
    stronger_platform_counts: Record<string, number>;
    limits: string;
  };
  ad_fatigue: {
    window_days: number;
    creators: number;
    organic_videos: number;
    results: { outcome: string; creators: number; median_slope: number; ci95: number[]; placebo_median: number; p_one_sided_fatigue: number; share_of_creators_with_negative_slope: number }[];
    limits: string;
  };
  long_lag: {
    method_check_passed: boolean;
    limits: string;
    results: { name: string; n_units: number; n_creators: number; smallest_p_after_event: number | null; window_of_smallest_p: string | null; detected_after_correction: boolean }[];
  };
  promotion: {
    disclosure: { creators: number; sponsored_videos: number; share_disclosed_overall: number; median_creator_share: number | null; creators_most: number; creators_some: number; creators_few: number };
    response: { creators: number; median_ratio: number | null; ci95_ratio: number[] | null; placebo_median_ratio: number | null; p_one_sided_more_on_sponsored: number | null; creators_more: number; creators_fewer: number; creators_same: number };
    limits: string;
  };
  gail: {
    note: string;
    runs: { name: string; log: string; exposed: number; observations: number; creators: number; gail_r_effect: number; gail_r_ci95: number[]; matched_did: number; matched_did_se: number; verdict: string }[];
    held_out: { what: string; mse: Record<string, number>; spearman: number; spearman_p: number; verdict: string };
    acceptance: { what: string; passed: number; of: number; verdict: string };
    benchmark: { what: string; caveat: string; rows: { setting: string; method: string; ate_error: number; pehe: number | null }[] };
    held_out_gail_r?: { gain_median: number; null_gain_median: number; null_gain_95th: number; verdict: string };
    benchmark_hard?: {
      what: string;
      reading: string;
      rows: { effect: number; noise: number; scenario: string; true_mean_effect: number; naive: number; gail_v1: number; gail_r: number; gail_r_placebo: number }[];
    };
  };
  power: {
    real_exposed: number;
    real_controls: number;
    real_estimate: number;
    real_se: number;
    deltas: number[];
    reps: number;
    real_structure: { share_detected: Record<string, number[]>; min_detectable_80pct: Record<string, number | null> };
    limits: string;
  };
}

export interface AnalysisData {
  generated_at: string;
  s10?: S10Data;
  s9?: S9Data;
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
    demo_query_fixed: Record<string, DemoCounts>;
    region_fixed: { dropped: number; still_with_india_evidence: number; athlete_5M_India_results: number };
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
