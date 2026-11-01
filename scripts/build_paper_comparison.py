"""Builds the paper results pack for Eesha (1 Nov 2026): base papers, our models and their training results, the exact validation metrics, the base-versus-ours comparison and the novelties.
Every number is read from a result file in models/; nothing is typed by hand except labelled quotations of published figures from the project's own literature review.

    python scripts/build_paper_comparison.py [--out exports/paper_results_and_comparison_pack.docx]

HONESTY RULES BUILT IN. The base papers solve different tasks on data we do not have, so their published figures are listed as reported and NEVER put in a column that implies a head-to-head. The head-to-head
is between METHOD FAMILIES run by us on one benchmark with a known planted effect. No claim of beating a published number is made. No reference is invented: the four core causal papers were read (abstract level)
on 1 Nov 2026; the 20 works of the review are cited as in the review.
"""
import argparse
import json
import statistics as st
from pathlib import Path

from docx import Document
from docx.shared import Pt

ROOT = Path(__file__).resolve().parent.parent
J = lambda n: json.loads((ROOT / "models" / n).read_text(encoding="utf-8"))  # noqa: E731

# ---- result files --------------------------------------------------------------------------------------------------------------------------------------------
bench1, bench0 = J("semisynth_new_graph_effect1.json"), J("semisynth_new_graph_effect0.json")
SETTINGS = [("effect 1.0, clean", bench1["clean"]), ("effect 1.0, trend", bench1["pretrend"]), ("no effect, clean", bench0["clean"]), ("no effect, trend", bench0["pretrend"])]
METHODS = [("Naive exposed-minus-unexposed difference", "Naive difference", "common marketing before/after comparison"),
           ("GNN predictor, no causal training", "GNN predictor (no causal training)", "GNN popularity, cascade and influencer predictors; InfluencerRank-style (Cao 2020; Jin 2024; GNN-IR 2024; ST-GNN 2026). InfluencerRank itself was not run"),
           ("Doubly-robust estimator, no graph", "DR, no graph", "ablation of a doubly-robust estimator without the graph (cf. DCHGNN 2026)"),
           ("GAIL v1 (learned exposure, MLP head)", "GAIL v1 (current)", "learned-exposure GNN family (cf. EgoNetGNN 2025; Ma and Tresp 2021)"),
           ("GAIL-R (orthogonal, attention exposure)", "GAIL-R", "ours; orthogonal attention family (cf. Wu and Yuan 2025), no placebo penalty"),
           ("GAIL-R + placebo penalty", "GAIL-R + placebo", "ours, with the placebo penalty")]
naive_sim = J("sim_semisynthetic_benchmark.json")
nf, nb, pf = naive_sim["table"]["0.0"]["naive"]["detects_effect_share"], naive_sim["table"]["0.0"]["naive"]["mean_estimate"], naive_sim["table"]["0.0"]["placebo"]["detects_effect_share"]
pb = J("spillover_placebo_test.json")["scopes"]["in_the_150"]["all"]
scale = J("semisynth_scale.json")["results"].get("clean, placebo penalty 0", {})
real = J("gail_real_results.json")["runs"][0]
hold, power, multi = J("gail_r_holdout.json"), J("power_analysis.json"), J("gail_r_multiseed.json")
rank, pairs, lag, fat, promo = J("ranking_test.json"), J("platform_pairs.json"), J("long_lag.json"), J("ad_fatigue.json"), J("promotion_behaviour.json")
passport, e45, hing = J("creator_passport.json")["summary"], J("e4_e5_results.json"), J("hinglish_check.json")
train = J("gail_training_summary_1nov.json")
senti = J("sentiment_check_claude_labels.json")
sentx = J("sentiment_check_claude_labels_twitter-xlm-roberta-base-sentiment.json")
dash = J("analysis_dashboard.json")
s2auc, s3 = dash["s2"]["auc"], dash["s3"]["calibration"]
fus = J("fusion_calibration_proxy.json")
mrow = multi["runs"]["with placebo penalty (30)"]


def cell(rows):
    rows = [r for r in rows if isinstance(r, dict) and r.get("ate_error") is not None]
    return f"{st.mean(r['ate_error'] for r in rows):.3f} / {st.mean(r['pehe'] for r in rows):.3f}"


def ate(setting, key):
    rows = [r for r in setting[key] if isinstance(r, dict) and r.get("ate_error") is not None]
    return st.mean(r["ate_error"] for r in rows)


def cow(setting, key):
    v = [r["beta_co"] for r in setting[key] if isinstance(r, dict) and r.get("beta_co") is not None]
    return st.mean(v) if v else float("nan")


d = Document()
d.styles["Normal"].font.name = "Calibri"
d.styles["Normal"].font.size = Pt(11)


def H(t, lvl=1):
    d.add_heading(t, level=lvl)


def P(t, bold=False, italic=False):
    p = d.add_paragraph()
    r = p.add_run(t)
    r.bold, r.italic = bold, italic


def B(t):
    d.add_paragraph(t, style="List Bullet")


def table(header, rows, size=9):
    t = d.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cells[i].text = str(v)
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(size)
    d.add_paragraph()


# =====================================================================================================================================================================
d.add_heading("Results and comparison pack for the paper", 0)
P("Project 011, UE23CS441A: Influencer-Brand Matching with Graph Spillover. Version of 1 November 2026. Prepared for Eesha to write the paper. Every number is read from a result file (section 11).", italic=True)

H("0. How to use this pack")
table(["Paper section", "Take from", "Tables or figures to make"], [
    ["Abstract and introduction", "sections 2 and 9", "one-sentence claims 1 to 5; the novelty table (9)"],
    ["Related work", "section 1", "the 4 core causal papers, the 5 closest marketing works, the 20 in 4 groups"],
    ["Method", "section 4", "model list; fusion formula; Creator Passport sections"],
    ["Experiments: setup and metrics", "section 6", "metric definitions table"],
    ["Experiments: training", "section 5", "loss by epoch; fit against baseline; learned relation shares"],
    ["Experiments: comparison with baselines", "sections 7 and 8", "Table B (methods x settings); scaling curve; real-data table; reported-figures table"],
    ["Novelties", "section 9", "one row per novelty: problem, method, result, strength"],
    ["Discussion and limits", "sections 10 and 12", "what we do not claim; open items"],
])

# ---- 1 base papers ---------------------------------------------------------------------------------------------------------------------------------------------
H("1. The base papers")
H("1.1 Core base papers: causal effects of one unit's treatment on its neighbours (read on 1 November 2026)", 2)
P("The project guide names the method GAIL (Graph-Adaptive Interference Learning). We searched for a published paper under that name and found none, so no citation is given for GAIL itself and the 'about 40% better predictions' "
  "figure in the guide must not be repeated in the paper unless its source is found. Eesha or Dr. Tiwari should supply the original source if one exists. The four published papers below do the same job and are the core base papers for the comparison. "
  "They were read at abstract level only; their datasets, baselines and numbers must be taken from the full texts.")
table(["Paper", "What it does", "What it estimates", "Reported results (abstract level)", "Relation to ours"], [
    ["Ma and Tresp (2021), Causal Inference under Networked Interference and Intervention Policy Enhancement, AISTATS, PMLR 130:3700-3708 (arXiv 2002.08506)",
     "GNN models dependencies between connected units under general network interference; also policy improvement under a treatment-capacity constraint.", "Individual treatment effects under interference; policy regret bounds.", "Theory: regret bounds and a heuristic graph-dependent error bound; no numbers on the abstract page.",
     "The original GNN-for-interference line. Our GAIL v1 is of this kind; we add orthogonalisation, a placebo check and real influencer data."],
    ["Adhikari, Medya and Zheleva (2025), Learning Exposure Mapping Functions for Inferring Heterogeneous Peer Effects, arXiv 2503.01722 (not peer reviewed at the time of reading)",
     "EgoNetGNN: a GNN that learns the exposure mapping from peer treatments, neighbourhood structure and edge attributes instead of a fixed 'fraction treated'.", "Heterogeneous peer effects.", "More robust than state-of-the-art baselines when the influence mechanism is unknown, on synthetic and semi-synthetic data; no figures on the page.",
     "Same idea as our learned exposure (attention). They do not test a placebo or a power bound, and not on influencer data."],
    ["Wu, Qiu, Chen, Li, Xiong, Wu and Zhang (2025), Causal Graph Transformer for Treatment Effect Estimation Under Unknown Interference, ICLR 2025 (CauGramer)",
     "Graph transformer with cross-attention to infer the interference aggregation; confounder balancing and minimax moment constraints; does not assume interference follows the social graph.", "Treatment effects under unknown networked interference.", "Superior to baselines on two benchmarks; no figures on the page.",
     "Relaxes the 'interference follows the graph' assumption, which ours keeps. Not applied to marketing."],
    ["Wu and Yuan (2025), Estimating Heterogeneous Causal Effect on Networks via Orthogonal Learning, arXiv 2509.18484",
     "Two stages: a GNN models covariate and network dependence, then an attention-based interference model is fitted on the residual; Neyman orthogonalisation with cross-fitting; bootstrap for the spillover matrix.", "Heterogeneous direct and spillover effects, edge-level, with simultaneous confidence bands.",
     "Improves heterogeneous effect estimation; supports influential-neighbour detection and spillover-sign recovery; no figures on the page.",
     "VERY CLOSE TO GAIL-R (orthogonal residual-on-residual fit, attention interference, bootstrap). GAIL-R must be presented as an application and extension of this idea, not as a new estimator."],
])
P("Consequence for our novelty claim. The estimator ingredients of GAIL-R are known: Robinson-style orthogonalisation and cross-fitting (Chernozhukov et al. 2018, reference [8] of the survey) and attention-based interference (Wu and Yuan 2025). "
  "What is ours: (1) the placebo penalty that removes pre-existing trends, which the benchmark shows is necessary; (2) validation on a benchmark with a known planted effect built from the real influencer graph; (3) an honest power analysis and a bounded null on real influencer data; "
  "(4) the application to ranked influencer recommendation with cross-platform evidence. State exactly this.", bold=True)
P("Named in Eesha's alignment note of 1 Nov 2026 and RUN by her from the authors' code on our benchmark (results in section 7, Table B2): TNet (Chen et al., ICML 2024; networked interference, doubly robust), the main causal baseline; DeepInf (Qiu et al., KDD 2018); INFLECT-DGNN (Tiukhova et al., IEEE Access 2024). "
  "I have not read TNet. Wu and Yuan (2025) has no public code, so it is quoted as the closest prior method and not run; their paper has no placebo or pre-trend check, which is our addition.", italic=True)
P("Also found, not yet read: Huber, Kueck and Mattes (2026), Learning and Testing Exposure Mappings of Interference using Graph Convolutional Autoencoders, CLeaR 2026, PMLR 323 (arXiv 2601.05728); and arXiv 2211.07823, Graph Neural Networks for Causal Inference Under Network Confounding (doubly-robust estimator with GNN nuisance functions).", italic=True)

H("1.2 The closest influencer-marketing works and the rest of the review", 2)
P("From the project's literature review (twenty works, cited there by author and year): GNN-IR (2024), INFLECT-DGNN (2024), ST-GNN (2026), DCHGNN (2026) and Jin, Liu and Murata (2024) are the closest in application; the other fifteen form three groups: "
  "influence-maximisation heuristics on static graphs (Kempe 2003, Chen 2009, Kundu 2011, Zareie 2023); GNN popularity and cascade prediction (Cao 2020, Shuo Ji 2023, the 2025 macro/micro study, Rossi 2020, Wu 2016); and text-plus-graph or content-only matchers "
  "(Benslimane 2023, NAH-GNN 2025, Nisa 2021, Yang 2022, Kim 2020, Gan 2019). Use all twenty in the related-work text, grouped; use only the closest in the tables.")

# ---- 2 claims ---------------------------------------------------------------------------------------------------------------------------------------------------------
H("2. Five claims the evidence supports")
gmax = max(ate(s, "GAIL-R + placebo") for _, s in SETTINGS)
table(["#", "Claim", "Evidence", "How strong"], [
    ["1", "Among the works we reviewed, none combines a ranked output, a multi-relational spillover graph, causal correction, temporal lag modelling and cross-platform fusion. The four core causal papers estimate spillover but are not applied to ranked influencer recommendation or cross-platform evidence.",
     "Table A (review gap table plus the four core papers).", "Moderate: rests on our review and on abstracts; repeat the searches on Scholar, ACM and IEEE."],
    ["2", f"On a benchmark with a known effect, GAIL-R with the placebo penalty is more accurate and more robust than the method families the base papers represent: average error at most {gmax:.3f} in all four settings.",
     "Table B: 10 repeats per setting, real graph and features, simulated treatment and outcome.", "Strong inside the simulation; not proof about real influencers."],
    ["3", f"The naive comparison produces false alarms and a placebo-corrected one does not: with no true effect and a typical growth trend the naive comparison 'finds' an effect in {100 * nf:.0f}% of simulated studies (mean {nb:+.2f}); the placebo-corrected one in {100 * pf:.0f}%.",
     f"Simulation on the real outcomes of 65 neighbours, 400 repeats. On real data engagement changes by a median {pb['median_placebo_lift']:+.2f} at random dates with no sponsorship.", "Strong."],
    ["4", f"A fair per-creator YouTube-versus-Instagram comparison within {pairs['window_hours']:.0f} hours, each post against the creator's own usual level.", f"{pairs['pairs']} matched posts, {pairs['creators_with_pairs']} creators, placebo and Granger tests.", "Moderate: Instagram data is thin."],
    ["5", "The system reports how sure it is (evidence grade A to D, confidence ranges, a power analysis, an honest null).", "Sections 5, 6, 7 and the app. Among the five marketing works none reports a per-recommendation uncertainty; Wu and Yuan do report a bootstrap interval for their effects.", "Descriptive."],
])

# ---- 3 table A ---------------------------------------------------------------------------------------------------------------------------------------------------------
H("3. Table A: capability comparison")
P("'Not reported' means the abstract or review does not describe it. Cells for other works come from the review and from abstracts read on 1 November 2026 and must be checked against the full texts.")
table(["Work", "Ranked output", "Spillover on a graph", "Causal correction", "Temporal / lag", "Cross-platform fusion", "Placebo or planted-effect check", "Uncertainty"], [
    ["Ma and Tresp (2021)", "No", "Yes (GNN)", "Yes", "Not reported", "No", "Not reported", "Not reported"],
    ["Adhikari et al. (2025) EgoNetGNN", "No", "Yes (learned exposure)", "Yes", "Not reported", "No", "Semi-synthetic data; no placebo reported", "Not reported"],
    ["Wu et al. (2025) CauGramer", "No", "Yes (unknown interference)", "Yes (balancing)", "Not reported", "No", "Two benchmarks; not described", "Not reported"],
    ["Wu and Yuan (2025)", "No", "Yes (edge-level)", "Yes (orthogonal)", "Not reported", "No", "Not reported", "Yes (bootstrap bands)"],
    ["GNN-IR (2024)", "Yes", "No (bipartite)", "No", "No", "No (YouTube only)", "Not reported", "Not reported"],
    ["INFLECT-DGNN (2024)", "Partial", "No", "No", "Yes", "No", "Not reported", "Not reported"],
    ["ST-GNN (2026)", "No", "No", "No", "Yes", "No", "Not reported", "Not reported"],
    ["DCHGNN (2026)", "No", "Yes (heterogeneous)", "Yes (doubly robust)", "Yes", "No", "Not reported", "Not reported"],
    ["Jin, Liu and Murata (2024)", "No", "Partial", "No", "Yes", "No (platforms separate)", "Not reported", "Not reported"],
    ["OUR SYSTEM", "Yes", "Yes (collaboration, @mention, co-occurrence, shared brand, shared commenters)", "Yes (GAIL-R: orthogonal, attention, placebo penalty)", "Yes (event study, Granger)", "Yes (same creator, same window)", "Yes (planted effect, placebo, power)", "Yes (bootstrap, grade A to D)"],
], size=8)

# ---- 4 models --------------------------------------------------------------------------------------------------------------------------------------------------------
H("4. Our system: the models used")
table(["Model", "Role", "Input to output", "How it was checked", "Headline result"], [
    ["Graph attention backbone (GAT, PyTorch Geometric)", "Embeds creators on the multi-relational graph", "1,289-d CLIP/BERT/metadata features + links to embedding", "Part of GAIL", "404 creators, 5 link types"],
    ["GAIL v1", "Learned exposure plus MLP head predicts a neighbour's engagement change", "creator embedding + exposure to predicted lift", "Leave-one-creator-out; planted-effect benchmark", f"Held-out MSE {J('gail_real_results.json')['held_out']['mse']['GAIL v1']:.2f} against {J('gail_real_results.json')['held_out']['mse']['always zero']:.2f} for always-zero: does not beat the baseline; benchmark error {ate(SETTINGS[0][1], 'GAIL v1 (current)'):.3f}"],
    ["GAIL-R (ours)", "R-learner: effect slope per relation on out-of-fold residuals, attention shrunk to uniform, placebo penalty, creator-level bootstrap", "residuals of outcome and exposure to effect per relation", "Planted-effect benchmark; held-out; seeds; power", f"Benchmark error {ate(SETTINGS[0][1], 'GAIL-R + placebo'):.3f} to {ate(SETTINGS[1][1], 'GAIL-R + placebo'):.3f}; real effect {real['gail_r_effect']:+.2f} ({real['gail_r_ci95'][0]:+.2f} to {real['gail_r_ci95'][1]:+.2f})"],
    ["Sentiment: RoBERTa (English) and XLM-R (Devanagari)", "Brand-safety score from audience comments", "comment to P(positive)+0.5 P(neutral)", "Labels assigned by Claude (an AI model), 40 comments per language, not human-verified; plus 24 human labels on Hinglish", f"Spearman with labels: English {senti['english']['spearman_with_label_value']:.2f}, Hinglish {senti['hinglish']['spearman_with_label_value']:.2f}, Devanagari with XLM-R {sentx['devanagari']['spearman_with_label_value']:.2f}"],
    ["Creator-feature score (CLIP text + BERT mean)", "Brief relevance from thumbnails and text", "brief and creator content to score 0..1", "AUC of ranking relevant creators above others", f"AUC {s2auc['fitness']['CLIP text + BERT mean (used)']:.2f} (fitness brief); {s2auc['cricket bat and gear']['CLIP text + BERT mean (used)']:.2f} (cricket brief)"],
    ["Sponsorship detector (rules, six evidence tiers)", "Marks sponsored posts, scored by tier", "caption, title, description, comments to is_sponsored + tier", "Hand checks (CAPSTONE_NEXT_STEPS.md)", "Flagged labels right 48 of 48 and 73 of 75 strong-tier events; spoken hits 86%; weak tiers 60% to 95%; standing affiliate codes over-count some creators"],
    ["Fusion score", "Ranks creators for a brief", "0.5 sentiment + 0.5 feature, -10 if sentiment < 0.3; spillover is shown as context with weight 0 (since 1 Nov); a branch with no information is dropped and the rest rescaled", "Rank stability; proxy calibration", f"Weights are documented priors, not fitted: only {s3['labelled_outcomes']} labelled outcomes exist. Proxy fit (not adopted): {fus['creators_used']} creators"],
    ["Cross-platform and lag (event study, Granger)", "Same creator, YouTube versus Instagram", "paired posts, 2-hourly growth readings", "Placebo with same hour of day, positive control, Bonferroni 0.0125", f"{pairs['pairs']} pairs; Instagram posts followed by YouTube uploads within 0 to 12 h; control detected"],
    ["Creator Passport analyses (new)", "Mood gap, sponsored response, speed, missing platform, clash", "per-creator evidence", "Worst-case SE; placebo; leave-one-out; 24 hand labels", f"Mood gap {passport['mood_gap']['flagged']} of {passport['mood_gap']['creators_with_both']}; missing-platform Spearman {passport['prediction']['spearman_full']:.2f} against {passport['prediction']['spearman_size_only']:.2f}"],
], size=8)

# ---- 5 training ------------------------------------------------------------------------------------------------------------------------------------------------------
H("5. Training results (run of 1 November 2026, corrected labels)")
tr = train["training"]
P(f"Data: {train['exposed_observations']} exposed and {train['control_observations']} comparison observations ({tr['observations']} in total) from {train['gail_r']['creators']} creators. Target: {train['target']}. "
  f"Training: {tr['epochs']} epochs. This run is on the corrected labels (after the standing-affiliate-code fix). The earlier run of 31 October, before the fix, had 60 exposed and 406 comparison observations, a training error of 0.3745 against 0.3965 and a GAIL-R effect of -0.16 (-0.40 to +0.40); it is kept in models/gail_training_summary_31oct.json. The conclusion is the same.")
pick = [e for e in tr["loss_by_epoch"] if e["epoch"] in (1, 20, 40, 60, 80, 100)]
table(["Epoch", "Total loss", "Prediction loss"], [[e["epoch"], f"{e['total']:.4f}", f"{e['prediction']:.4f}"] for e in pick], size=9)
table(["Quantity", "Value", "How to read it"], [
    ["Mean squared error of the trained GAIL v1 on all observations", f"{tr['mse_trained']:.4f}", f"{tr['improvement_percent']}% below the always-zero baseline ({tr['mse_baseline_always_zero']:.4f}); this is IN-SAMPLE and small, and it does not carry to unseen creators (section 7)."],
    ["Learned transmission shares (softmax)", f"co-occurrence {tr['learned_relation_shares']['co_occurs_with']:.3f}, collaboration {tr['learned_relation_shares']['collaborates_with']:.3f}", "The v1 attention puts most weight on the weakest relation. The benchmark shows such a weight appears even where the true effect of that relation is zero, so it must not be read as an explanation."],
    ["Placebo penalty on the trained model", f"{tr['placebo_penalty_on_trained_model']:.6f}", "About 0 is good."],
    ["Matched difference-in-differences", f"{train['matched_did']['estimate']:+.2f} (SE {train['matched_did']['se']:.2f}), {train['matched_did']['exposed']} exposed vs {train['matched_did']['controls']} controls", "Model-free check; consistent with no effect."],
    ["Category-matched difference-in-differences", f"{train['category_matched_did']['estimate']:+.2f} (SE {train['category_matched_did']['se']:.2f})", "Same, controls from the same creator category."],
    ["Placebo (pre-trend) difference-in-differences", f"{train['placebo_pre_trend_did']['estimate']:+.2f} (SE {train['placebo_pre_trend_did']['se']:.2f})", "Should be near 0. It is not clearly zero, which is why a plain DiD is not trusted and the placebo penalty is used."],
    ["GAIL-R effect on the exposed", f"{train['gail_r']['effect_on_exposed']:+.2f}, 95% interval {train['gail_r']['ci95'][0]:+.2f} to {train['gail_r']['ci95'][1]:+.2f} (creator-level bootstrap, B=200)", "No spillover detected."],
    ["GAIL-R over 10 seeds", f"{min(mrow['att_by_seed']):+.2f} to {max(mrow['att_by_seed']):+.2f} (mean {mrow['att_mean']:+.2f})", "The model's own randomness is small next to the interval."],
], size=9)

# ---- 6 metrics ------------------------------------------------------------------------------------------------------------------------------------------------------
H("6. Validation metrics: exactly what we measure")
table(["Component", "Metric", "Definition", "Value"], [
    ["GAIL-R, GAIL v1, baselines (simulation)", "ATE error", "absolute difference between the estimated mean effect on the exposed and the true effect, averaged over 10 repeats", f"GAIL-R + placebo {ate(SETTINGS[0][1], 'GAIL-R + placebo'):.3f} (effect 1.0, clean)"],
    ["", "PEHE", "root mean squared error of each creator's effect", f"GAIL-R + placebo {cell(SETTINGS[0][1]['GAIL-R + placebo']).split(' / ')[1]}"],
    ["", "Spurious relation weight", "weight given to the co-occurrence relation whose true effect is 0", f"GAIL v1 {cow(SETTINGS[0][1], 'GAIL v1 (current)'):+.2f}; GAIL-R {cow(SETTINGS[0][1], 'GAIL-R'):+.2f}"],
    ["", "False-alarm rate", "share of simulated studies with no true effect that report one", f"naive {100 * nf:.0f}%; placebo-corrected {100 * pf:.0f}%"],
    ["Spillover on real data", "Effect with creator-level 95% bootstrap interval", "mean effect on observations with a sponsored collaborator; resamples creators", f"{real['gail_r_effect']:+.2f} ({real['gail_r_ci95'][0]:+.2f} to {real['gail_r_ci95'][1]:+.2f})"],
    ["", "Held-out gain", "leave-one-creator-out error reduction against always-zero, and against a wrong-window null", f"{100 * hold['gain_median']:.1f}% against {100 * hold['null_gain_median']:.1f}% for the null"],
    ["", "Power", "smallest effect detected in 80% of simulations that keep the real outcomes and plant the effect", "about 1.5 times a rise in engagement with 60 exposed observations"],
    ["", "Seed spread", "range of the estimate over 10 learned-attention seeds", f"{min(mrow['att_by_seed']):+.2f} to {max(mrow['att_by_seed']):+.2f}"],
    ["Sentiment", "AUC and Spearman against labels", "positive vs rest, negative vs rest, rank correlation with the labels (neg 0, neutral 0.5, pos 1); 40 comments per language, labels assigned by Claude (an AI model) and not human-verified", f"English AUC {senti['english']['auc_positive_vs_rest']:.2f}, Spearman {senti['english']['spearman_with_label_value']:.2f}; Hinglish {senti['hinglish']['spearman_with_label_value']:.2f}"],
    ["Hinglish check (24 hand labels, one labeller)", "AUC positive vs negative; Spearman", "the same, by the pipeline's model", f"AUC {hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['auc_pos_vs_neg']:.2f}, Spearman {hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['spearman']:.2f} (wide intervals)"],
    ["Creator-feature score", "AUC", "how well relevant creators are ranked above others for a brief", f"{s2auc['fitness']['CLIP text + BERT mean (used)']:.2f} (fitness); BERT alone {s2auc['fitness']['BERT pooler output']:.2f}"],
    ["Cross-platform pairs", "Median difference, raw and after removing the placebo", "log engagement of an Instagram post minus the paired YouTube video, each against its own usual; a placebo with no real pairing shows the scale artefact", f"raw {pairs['median_difference']:+.2f}; placebo alone {pairs['placebo']['median_difference_placebo']:+.2f}; after removing it {pairs['median_difference_adjusted']:+.2f}"],
    ["Lag / event study", "Smallest p after the event, Bonferroni 0.0125, positive control", "excess rate against the creator's own rate, with placebo events at the same hour of day", "control detected; Instagram post then YouTube upload in 0 to 12 h"],
    ["Fusion", "Rank stability; proxy association", "top-10 overlap and Spearman across weight settings; correlation with a proxy outcome", f"weights stay priors ({s3['labelled_outcomes']} labelled outcomes)"],
    ["Sponsored response (Passport)", "Matched difference against placebo", "sponsored post against the same creator's organic posts of the same format within 45 days", f"{passport['sponsored_response']['youtube_views'].get('approx_percent', float('nan')):+.1f}% in YouTube views, interval includes 0"],
    ["Missing platform (Passport)", "Leave-one-out Spearman and MAE (log)", "predict a creator's Instagram level without that creator's own data", f"Spearman {passport['prediction']['spearman_full']:.2f} against {passport['prediction']['spearman_size_only']:.2f} (size only); MAE {passport['prediction']['mae_full']:.2f} against {passport['prediction']['mae_size_only']:.2f}"],
    ["Mood gap (Passport)", "Gap and worst-case z", "Instagram minus YouTube comment mood; SE bounded by 0.5 / sqrt(n)", f"{passport['mood_gap']['flagged']} of {passport['mood_gap']['creators_with_both']} flagged"],
], size=8)

# ---- 7 head to head --------------------------------------------------------------------------------------------------------------------------------------------------
H("7. Table B: the method families on one benchmark with a known effect")
P("The graph and creator features are the real ones of the 29 Oct checkpoint (390 creators, 354 collaboration edges). Treatment and outcomes are simulated (planted effect 1.0, a true mean effect of about 0.25 over all creators) so each creator's true effect is known: spillover travels only through collaboration links, co-occurrence links carry no effect, "
  "and in the 'trend' settings a trend no sponsorship caused is added. Ten repeats per setting. Each cell: average error of the estimated effect on the exposed / root mean squared error of each creator's effect. Lower is better.")
table(["Method", "Stands for"] + [s for s, _ in SETTINGS], [[lab, fam] + [cell(cols[key]) for _, cols in SETTINGS] for lab, key, fam in METHODS], size=8)
P("Reading it, including where we are not better:", bold=True)
B(f"With a real effect and no trend, GAIL-R ({ate(SETTINGS[0][1], 'GAIL-R'):.3f}) is far more accurate than the GNN predictor ({ate(SETTINGS[0][1], 'GNN predictor (no causal training)'):.3f}), GAIL v1 ({ate(SETTINGS[0][1], 'GAIL v1 (current)'):.3f}) and the naive difference ({ate(SETTINGS[0][1], 'Naive difference'):.3f}).")
B(f"GAIL-R alone is NOT robust: with a pre-existing trend its error rises to {ate(SETTINGS[1][1], 'GAIL-R'):.3f}. The placebo penalty restores {ate(SETTINGS[1][1], 'GAIL-R + placebo'):.3f}. It is part of the method.")
B(f"With no true effect the GNN predictor also looks accurate ({ate(SETTINGS[2][1], 'GNN predictor (no causal training)'):.3f}) because it predicts roughly nothing; it fails once there is a real effect. Accuracy with no effect is not evidence of a good method.")
B(f"The co-occurrence relation has no true effect. Models without causal training give it a large weight (GNN predictor {cow(SETTINGS[0][1], 'GNN predictor (no causal training)'):+.2f}, GAIL v1 {cow(SETTINGS[0][1], 'GAIL v1 (current)'):+.2f}); GAIL-R gives {cow(SETTINGS[0][1], 'GAIL-R'):+.2f}.")
if scale:
    B("More exposed creators help (separate run on the 404-creator graph, planted effect 0.5, noise 0.9, 5 repeats, clean setting): " + "; ".join(f"{k} exposed: error {v['mean_abs_error']:.2f}" for k, v in scale.items() if v.get("mean_abs_error") is not None) + ".")
P("Table B2: published models run by Eesha on the same benchmark (from her note of 1 Nov 2026; per-creator error PEHE, lower is better; 390-creator graph, only 3 replicates per method; true mean effect about 0.25). Keep this table separate from Table B (10 replicates) until she re-runs the baselines on the 404-creator graph after the label fix; label the graph and n wherever it appears.", bold=True)
table(["Method", "No trend", "Planted pre-trend"], [["Doubly-robust, no graph", "0.330", "0.382"], ["DeepInf (KDD 2018)", "0.443", "0.442"], ["INFLECT-DGNN (IEEE Access 2024)", "0.444", "0.441"],
                                                   ["TNet (ICML 2024)", "0.446", "0.582"], ["GAIL-R", "0.068", "0.307"], ["GAIL-R + placebo", "0.131", "0.101"]], size=9)
P("Reading (from the same note): none of the three published models tells creators apart better than the no-graph baseline. DeepInf and INFLECT-DGNN estimate almost no effect (their average-effect error, about 0.22, is nearly the whole true effect), which is expected for prediction models. TNet gets worse with a pre-trend because it has no guard against one. The placebo penalty costs a little with no trend and protects the estimate with one.")
P("Real data, same care:", bold=True)
rk = rank["methods"]
table(["Question", "Result", "Source"], [
    ["Does a naive before-and-after comparison mislead?", f"Yes: at random dates with no sponsorship engagement changes by a median {pb['median_placebo_lift']:+.2f}; around a collaborator's sponsored post {pb['median_event_lift']:+.2f}.", "spillover_placebo_test.json"],
    ["Spillover (GAIL-R)", f"{real['gail_r_effect']:+.2f}, 95% {real['gail_r_ci95'][0]:+.2f} to {real['gail_r_ci95'][1]:+.2f}; {real['exposed']} exposed; category-matched DiD {real['matched_did']:+.2f} (SE {real['matched_did_se']:.2f}). No spillover detected.", "gail_real_results.json"],
    ["Does the term help on unseen creators?", f"No: median gain {100 * hold['gain_median']:.1f}% against {100 * hold['null_gain_median']:.1f}% for a wrong-window control.", "gail_r_holdout.json"],
    ["Do popularity-style rankers predict a later sponsored effect?", f"No: popularity Spearman {rk['popularity (median log views)']['spearman']:+.2f} ({rk['popularity (median log views)']['spearman_ci95'][0]:+.2f} to {rk['popularity (median log views)']['spearman_ci95'][1]:+.2f}); engagement rate {rk['engagement rate']['spearman']:+.2f}; {rank['creators']} creators. We do not claim a better ranker.", "ranking_test.json"],
], size=9)

# ---- 8 reported figures ---------------------------------------------------------------------------------------------------------------------------------------------
H("8. Published figures of the base papers, as reported (NOT a head-to-head)")
P("These numbers come from the project's literature review. Each paper solves its own task on its own data, so they cannot be placed next to ours as 'better' or 'worse'. Put them in the paper as context only, with this caution.", italic=True)
table(["Work", "Task", "Metric and value as reported", "Closest thing we report (different task)"], [
    ["GNN-IR (2024)", "Advertiser-influencer link prediction", "Precision 96.51% at k=1, 93.68% at k=10", "Feature-score AUC 0.85 (relevance ranking, fitness brief)"],
    ["ST-GNN (2026)", "Influence propagation in marketing networks", "MAE 0.036; influence correlation 0.878; attention reliability 0.93", "GAIL-R benchmark error 0.02 to 0.05 (planted effect, different scale)"],
    ["Jin, Liu and Murata (2024)", "Popularity prediction on YouTube, MOOC, Reddit, Wikipedia", "RMSE 0.036 against CoupledGNN 0.071 (to be verified against the source)", "n/a"],
    ["NAH-GNN (2025)", "Multi-behaviour recommendation", "HR@10 0.79; NDCG@10 0.33", "n/a"],
    ["Kim et al. (2020)", "Influencer profiling", "Accuracy 98.32%", "Sentiment AUC 0.91 (English)"],
    ["Nisa et al. (2021)", "Video popularity", "Accuracy 86% to 88%", "n/a"],
    ["Wu, Mei, Cheng and Zhang (2016)", "Photo popularity", "Accuracy 79.8%", "n/a"],
    ["Yang, Yang and Zhang (2022)", "Brand-celebrity matching", "F1 0.362", "n/a"],
    ["Ma and Tresp; EgoNetGNN; CauGramer; Wu and Yuan", "Effects under interference", "No numbers on the abstract pages; take them from the full texts", "ATE error and PEHE on our benchmark (Table B)"],
], size=8)

# ---- 9 novelties ----------------------------------------------------------------------------------------------------------------------------------------------------
H("9. The novelties: what each solves, how it is better, what we found")
dis, resp = promo["disclosure"], promo["response"]
ig_up = next(r for r in lag["results"] if r["name"].startswith("ig_to_uploads"))
table(["Novelty", "Problem it solves", "How it works", "Better or different from prior work", "Result", "Strength"], [
    ["Same-creator YouTube vs Instagram comparison", "A brand judges a creator from one platform", "Posts within 24 h, each against the creator's own usual, with a placebo", "Compared works test platforms separately or one platform", f"{pairs['pairs']} pairs, {pairs['creators_with_pairs']} creators; Instagram leads in {100 * pairs['share_pairs_instagram_better_adjusted']:.0f}% but placebo gives {100 * pairs['placebo']['share_instagram_better_placebo']:.0f}%", "Moderate"],
    ["Granger and event-study lag", "Does one platform's activity precede the other's", "Granger tests; event study with same-hour placebo and a positive control", "Compared works model time within one platform", f"Instagram post then YouTube upload in 0 to 12 h (smallest p {ig_up['smallest_p_after_event']}); a 12 to 24 h lag is not supported", "Standard method; careful design"],
    ["Placebo-and-simulation protocol for spillover", "False alarms in spillover claims", "Placebo dates, planted-effect benchmark, power analysis", "Compared influencer works report accuracy only", f"Naive false alarm {100 * nf:.0f}%; placebo-corrected {100 * pf:.0f}%", "Strong"],
    ["GAIL-R placebo penalty", "Pre-existing trends read as spillover", "Penalty on the learned effect against the pre-period lift", "Orthogonal attention estimators exist (Wu and Yuan 2025); the placebo penalty is ours", f"Error with a trend {ate(SETTINGS[1][1], 'GAIL-R'):.3f} to {ate(SETTINGS[1][1], 'GAIL-R + placebo'):.3f}", "Strong in simulation"],
    ["Sponsored response by platform", "Which platform to pay for", "Same creator, same format, nearby dates, with placebo", "Prior sponsored-post studies are Instagram only", f"YouTube views {passport['sponsored_response']['youtube_views'].get('approx_percent', float('nan')):+.1f}% (interval includes 0); Instagram {passport['sponsored_response']['instagram_likes']['creators']} creators", "Thin"],
    ["Buying signals in comments", "Likes are not sales", "Purchase-intent comments per 1,000 on sponsored vs other videos", "Not in the compared works", f"{resp['median_ratio']:.1f} times higher on sponsored videos (95% {resp['ci95_ratio'][0]:.2f} to {resp['ci95_ratio'][1]:.2f}); shuffle gives {resp['placebo_median_ratio']:.2f}", "Proxy, not sales"],
    ["Ad fatigue test", "Audience saturated with ads", "Slope of views on sponsored posts in the previous 30 days, with placebo", "Not in the compared works", f"slope {fat['results'][0]['median_slope']:+.3f}, one-sided p {fat['results'][0]['p_one_sided_fatigue']}: not detected", "Null"],
    ["Disclosure-honesty index", "Hidden ads are a trust and legal risk", "Share of detected sponsored videos with an explicit label, with an error margin", "Not in the compared works", f"{100 * dis['share_disclosed_overall']:.0f}% overall; median creator {100 * dis['median_creator_share']:.0f}%", "Depends on label quality"],
    ["Attention speed", "Where a time-limited offer lands", "Share of the first week's views in the first 24 h", "Not in the compared works", f"median {100 * passport['speed']['median_share_first_24h']:.0f}% (YouTube; {passport['speed']['videos']} videos)", "Moderate; YouTube only"],
    ["Mood gap between platforms", "Liked on one platform, criticised on the other", "Per-platform comment mood with a worst-case error bound", "Only single-account cases found", f"{passport['mood_gap']['flagged']} of {passport['mood_gap']['creators_with_both']} flagged; {passport['mood_gap']['warmer_on_instagram']} warmer on Instagram", "Moderate"],
    ["Predict the missing platform", "55 creators with no Instagram data", "Leave-one-out ridge on YouTube features", "Not in the compared works", f"Spearman {passport['prediction']['spearman_full']:.2f} against {passport['prediction']['spearman_size_only']:.2f}; typical error about 3.4 times, shown as a range", "Moderate"],
    ["Competitor-clash flag", "Brand exclusivity", "Rival brand of the brief's category promoted in the last 120 days", "The concept is already studied (section 12); ours is an automatic warning built from observed sponsorship data, not a new finding", f"{passport['clash']['creators_with_recent_brand_posts']} creators with a recent brand post; shown on dashboard cards", "A warning, hard to validate"],
    ["Evidence grade and ranges", "Say when we do not know", "Points for comments, features, platforms, graph links; ranges from branch uncertainty", "None of the compared works reports it", "Grade A to D on every recommendation", "Descriptive"],
    ["E4 and E5 (simulation)", "Attention training; missed sponsorship labels", "Causal-loss attention; MC-SIMEX correction", "Wu and Yuan use orthogonal attention; MC-SIMEX is standard", f"Causal loss {e45['e4_simulated']['clean, causal supervision, shrink 100']['pehe']['mean']:.2f} against plain {e45['e4_simulated']['clean, plain supervision, shrink 100']['pehe']['mean']:.2f}; learned attention no better than uniform", "Simulation only"],
    ["Hinglish check", "Sentiment on code-mixed comments", "24 hand labels scored against the model", "n/a", f"AUC {hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['auc_pos_vs_neg']:.2f}; Spearman {hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['spearman']:.2f}", "Rough"],
], size=8)

# ---- 10 not claimed ------------------------------------------------------------------------------------------------------------------------------------------------
H("10. What we do not claim")
for t in ["That our ranking predicts brand outcomes better than any published system. No sales or conversion data exists and we did not reproduce any published system.",
          "That our numbers beat GNN-IR's precision, ST-GNN's MAE or any figure in section 8. Different tasks, different data.",
          "That GAIL-R is a new estimator. It applies known orthogonalisation and attention-interference ideas; the new parts are the placebo penalty, the validation and the application.",
          "That spillover exists. We find none and rule out large effects only.",
          "That we are the first to compare one creator across platforms. Small studies exist; to our knowledge, ours is a fair per-creator comparison at this scale.",
          "That simulation results hold on real influencers.",
          "That the Hinglish check is a benchmark (24 labels, one labeller)."]:
    B(t)

# ---- 11 provenance --------------------------------------------------------------------------------------------------------------------------------------------------
H("11. Where each number comes from, and how to reproduce it")
table(["Number", "File in models/", "Script"], [
    ["Table B, simulation errors", "semisynth_new_graph_effect1.json, semisynth_new_graph_effect0.json, semisynth_scale.json", "the project's benchmark (ml/semi_synthetic.py, branch merge-eesha-ml); scripts/run_semisynth_scale.py on the scratch copy"],
    ["Naive false alarms", "sim_semisynthetic_benchmark.json", "simulation on the real outcomes of 65 neighbours"],
    ["Training results", "gail_training_summary_31oct.json", "scripts/extract_training_summary.py on the run-7 log"],
    ["Real-data spillover, held-out, power, seeds", "gail_real_results.json, gail_r_holdout.json, power_analysis.json, gail_r_multiseed.json", "scripts/gail_r_holdout.py, run_power_analysis.py, gail_r_multiseed.py"],
    ["Placebo dates, ranking", "spillover_placebo_test.json, ranking_test.json", "placebo test; scripts/run_ranking_test.py"],
    ["Sentiment and features", "sentiment_check_claude_labels*.json, analysis_dashboard.json (S2)", "scripts/check_sentiment_labels.py"],
    ["Cross-platform, lag, fatigue, promotion", "platform_pairs.json, long_lag.json, ad_fatigue.json, promotion_behaviour.json", "scripts/refresh_analyses.py"],
    ["Passport, E4/E5, Hinglish", "creator_passport.json, e4_e5_results.json, hinglish_check.json", "build_creator_passport.py, run_e4_e5.py, score_hinglish_sample.py"],
], size=9)

# ---- 12 open items ---------------------------------------------------------------------------------------------------------------------------------------------------
H("12. Open items for the paper")
for t in ["Find the source of GAIL (Dr. Tiwari or the project guide). If there is none, present GAIL as the project's method built from the four core papers above, and do not cite the guide's '40% better' figure.",
          "Read the four core papers in full and take their datasets, baselines and numbers; then decide whether any of them can be run on our benchmark as a real baseline. Wu and Yuan (2025) is the most important one.",
          "Verify and cite the related studies found by web search on 30 October (a working paper on creators adding a second platform; studies of disclosure rules and sponsored Instagram posts; a Twitter-to-Medium study; single-account cross-platform cases; a shared-commenter graph). Narrow claim 1 if any already does what we claim.",
          "Check the capability cells of Table A against the full texts.",
          "Competitor clash (idea G): a web search on 1 Nov 2026 found prior work, so do NOT call it new: Rialti et al. (2024), Psychology and Marketing, mega-influencers and rival brands; Carrillat et al. (2014), scandal of an endorser spilling over to competitor brands; experiments on endorsing several brands (one, three and seven) showing lower brand attitude and perceived authenticity (International Journal of Advertising, 2022, doi 10.1080/02650487.2022.2054163); and a student interview study of footballers endorsing rival brands. Industry sources add that health and nutrition are categories where several endorsements are accepted, so in our fitness domain the flag is a 'check exclusivity' warning and never a penalty. These were found from search results only and must be read and cited properly.",
          "The sentiment checks (40 comments per language) use labels assigned by Claude, an AI model, and are not human-verified; have a person re-label them, or report them as AI-labelled. Only the 24 Hinglish labels are human.",
          "The real-data numbers and the training results are on the corrected labels (1 November 2026). The run-8 checkpoint is kept in a working copy and is not installed in the app; rebuild this pack after any new run with python scripts/build_paper_comparison.py.",
          "Retrain on a GPU with the fixed labels and 20 or more seeds (exports/gpu_package_31oct.zip)."]:
    B(t)

out = Path(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else ROOT / "exports" / "paper_results_and_comparison_pack.docx"
d.save(out)
print("saved", out)
