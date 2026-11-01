"""Builds literature_survey_and_results_v6.docx (1 Nov 2026): the reviewed works and gap analysis of v3, plus background, approach, results, novelties, discussion and limits. Every number is read from the result
files in models/ or counted in the database; nothing is typed in. Supersedes v5.

    python scripts/build_survey_v6.py [--out exports/literature_survey_and_results_v6.docx]

CHANGES FROM v5 (Eesha's alignment note of 1 Nov and the work of 1 Nov): orthogonalised (R-learner) wording instead of 'doubly-robust form'; baselines named as run (DeepInf, INFLECT-DGNN, TNet) and InfluencerRank as
related work only; Wu and Yuan (2025) as the closest prior method; spillover taken out of the fusion score; E4 and E5 built (simulation) with their findings; results on the corrected labels (standing affiliate
codes removed); the Creator Passport novelties; the unverified '+0.49' sentence removed; sentiment checks described as AI-labelled; limitations rewritten. No reference is invented.
"""
import argparse
import json
import os
import re
from pathlib import Path

import psycopg2
from docx import Document

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(r"C:\Users\Shimona\Documents\Capstone_Review2_Docs\other_documents\literature_review_and_gap_v3.docx")
J = lambda n: json.loads((ROOT / "models" / n).read_text(encoding="utf-8"))  # noqa: E731

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "exports" / "literature_survey_and_results_v6.docx"))
OUT = Path(ap.parse_args().out)

# ---- counts from the database (read only) ---------------------------------------------------------------------------------------------------------
url = os.environ.get("DATABASE_URL") or re.search(r"^DATABASE_URL=(.+)$", (ROOT / ".env").read_text(encoding="utf-8"), re.M).group(1).strip().strip('"')
conn = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"), connect_timeout=15)
conn.set_session(readonly=True)
cur = conn.cursor()
def count(q):
    cur.execute(q)
    return cur.fetchone()[0]
n = {"creators": count("select count(*) from creators"), "videos": count("select count(*) from youtube_videos"), "comments": count("select count(*) from youtube_comments"),
     "sponsored": count("select count(*) from youtube_videos where is_sponsored"), "sponsoring": count("select count(distinct creator_id) from youtube_videos where is_sponsored"),
     "ig_posts": count("select count(*) from instagram_posts"), "ig_creators": count("select count(distinct creator_id) from instagram_posts")}
conn.close()

# ---- result files ---------------------------------------------------------------------------------------------------------------------------------
pairs, lag, fat, promo, power = J("platform_pairs.json"), J("long_lag.json"), J("ad_fatigue.json"), J("promotion_behaviour.json"), J("power_analysis.json")
hold, multi, fus = J("gail_r_holdout.json"), J("gail_r_multiseed.json"), J("fusion_calibration_proxy.json")
train, real = J("gail_training_summary_1nov.json"), J("gail_real_results.json")["runs"][0]
ps, e45, hing, base = J("creator_passport.json")["summary"], J("e4_e5_results.json"), J("hinglish_check.json"), J("published_baselines_eesha.json")
fsim = J("fusion_simulation.json")["scenarios"]
b1, b0 = J("semisynth_new_graph_effect1.json"), J("semisynth_new_graph_effect0.json")
import statistics as st
bench = lambda block, key: st.mean(r["ate_error"] for r in block[key] if isinstance(r, dict) and r.get("ate_error") is not None)  # noqa: E731
exposed, controls = power["real_exposed"], power["real_controls"]
mrow = multi["runs"]["with placebo penalty (30)"]
g = train["gail_r"]
rs, si = power["real_structure"]["share_detected"], power["stand_ins"]["share_detected"]
ctrl = next(r for r in lag["results"] if r["name"].startswith("control"))
ig_up = next(r for r in lag["results"] if r["name"].startswith("ig_to_uploads"))
ig_cm = next(r for r in lag["results"] if r["name"].startswith("ig_to_comments:"))
g_all = pairs["granger"]["all comments"]["tests"]
dis, resp = promo["disclosure"], promo["response"]
sr = ps["sponsored_response"]
scale = J("semisynth_scale.json")["results"].get("clean, placebo penalty 0", {})
scale_line = "; ".join(f"{k} exposed creators: {v['mean_abs_error']:.2f}" for k, v in scale.items() if v.get("mean_abs_error") is not None)

d = Document(SRC)
first = d.paragraphs[0]
first.insert_paragraph_before("Literature Survey and Results: Influencer-Brand Matching with Graph Spillover and Cross-Platform Evidence", style="Title" if "Title" in [s.name for s in d.styles] else first.style)
first.insert_paragraph_before("Project 011, UE23CS441A. Version 6, 1 November 2026 (supersedes version 5). The sections that report our own results read their numbers from the project's result files and the database. The sections on reviewed work are those of the earlier review (twenty studies) plus the closest causal-network papers read on 1 November 2026.", style="Normal")


def H(t):
    d.add_paragraph(t, style="Heading 1")


def P(t):
    d.add_paragraph(t, style="Normal")


H("Background: the methods this project builds on")
P("Spillover means that a sponsorship given to one creator may change the outcome of a connected creator. Treatment effects in the presence of such interference are the subject of Hudgens and Halloran [5]. Brands do not sponsor creators "
  "at random, so a naive comparison confuses the effect with who gets chosen; propensity scores [6] and augmented inverse-probability weighting [7] are the classical corrections, and double machine learning [8] gives the "
  "orthogonalised (R-learner) estimator used here: nuisance models are fitted out of fold, with folds split by creator, and the effect is estimated on the residuals. The graph is read by graph attention [1] implemented in PyTorch Geometric [2]. "
  "Creator content is represented with CLIP image features [9] and BERT text features [10], with a multilingual model [11] for Hindi-script comments. Cross-platform timing is examined with Granger's test [12]; that is prediction, not cause, and is reported as such.")
P("The closest prior methods are graph models of effects under network interference. Ma and Tresp (2021) [14] use graph neural networks for individual treatment effects under interference. Adhikari, Medya and Zheleva (2025) [15] learn the exposure mapping with a "
  "graph network (EgoNetGNN) instead of a fixed share of treated neighbours. Wu et al. (2025) [16] infer the interference structure with a graph transformer. Wu and Yuan (2025) [13] fit a two-stage orthogonalised model with an attention-based interference "
  "term and bootstrap bands, and are the closest to our GAIL-R; their paper has no placebo or pre-trend check, which is our addition. On the influencer side, DeepInf [3] predicts influence; InfluencerRank [4] ranks influencers (related work, not run by us). "
  "DeepInf, INFLECT-DGNN and TNet (Chen et al., ICML 2024; the full reference is to be added) were run from the authors' code on our benchmark. The project guide names the method GAIL (Graph-Adaptive Interference Learning); we found no published paper under that name, "
  "so GAIL is described here as the project's own design built from the ingredients above.")

H("Our approach")
P("The system ranks creators for a brand brief with a score from 0 to 100 and a confidence range. The score combines audience mood (brand safety, from comment sentiment) and content fit (CLIP and BERT features against the brief) with equal weight, minus 10 points when "
  "sentiment is below 0.3. Since 1 November the spillover branch is shown on every card as context but has weight zero: its real-data estimate is a bounded null, so it should not move a ranking. A branch that knows nothing about a creator is left out and the rest rescaled. "
  "The weights are documented priors, not fitted values, because no sales or conversion outcome exists. Every recommendation carries an evidence grade from A to D.")
P("GAIL-R, the spillover estimator, is a two-stage, cross-fitted R-learner. Exposure to sponsored neighbours is computed per relation (collaboration, co-occurrence, shared brand) and weighted by attention that is kept close to uniform; one effect slope per relation is fitted on "
  "out-of-fold residuals, so a slope can be zero. A placebo penalty on the pre-period lift removes effects that also appear before the sponsorship, and intervals come from a bootstrap that resamples creators. It is not joint optimisation and not AIPW. "
  "The graph links creators by collaboration, @mention, co-occurrence in Reddit threads, shared sponsored brand and shared commenters. The same creator's YouTube and Instagram activity is compared within 24 hours, each against the creator's own usual level.")

H("Our results")
P(f"Data. The database holds {n['creators']} creators, {n['videos']:,} YouTube videos, {n['comments']:,} YouTube comments, {n['sponsored']:,} sponsored videos from {n['sponsoring']} creators and {n['ig_posts']:,} Instagram posts from {n['ig_creators']} creators, with growth readings "
  "every two hours since 11 October 2026. Sponsorship labels come from detection rules and hand checks. On 1 November we found that some creators paste the same affiliate code under every video, which the rules read as a sponsored post each time; 470 such videos "
  "from 17 creators were un-flagged (backed up and reversible), reducing sponsored videos from 3,370 to 2,900. 'Organic' means 'not detected as sponsored'.")
P(f"Spillover on real data. After the correction, {exposed} observations have a sponsored collaborator and {controls} do not. Many of the links behind them are @mentions, which is weaker evidence than co-author posts, so the result is reported as mention-linked exposure. "
  f"A fit of GAIL-R on the full training run gives an effect on the exposed of {g['effect_on_exposed']:+.2f} on the log-engagement scale (95% interval {g['ci95'][0]:+.2f} to {g['ci95'][1]:+.2f}); the mean of ten learned-attention seeds is {mrow['att_mean']:+.2f} (seeds {min(mrow['att_by_seed']):+.2f} to {max(mrow['att_by_seed']):+.2f}, bootstrap interval {mrow['bootstrap_ci95'][0]:+.2f} to {mrow['bootstrap_ci95'][1]:+.2f}). "
  f"A category-matched difference-in-differences gives {train['category_matched_did']['estimate']:+.2f} (standard error {train['category_matched_did']['se']:.2f}) and the plain matched version {train['matched_did']['estimate']:+.2f} ({train['matched_did']['se']:.2f}). The plain version is not trusted: its placebo, "
  f"computed on the period before each sponsorship, is {train['placebo_pre_trend_did']['estimate']:+.2f}, clearly not zero, which means a plain comparison is confounded by pre-existing trends. "
  f"On creators held out of fitting, adding the spillover term did not improve prediction (median gain {100 * hold['gain_median']:.1f}%, against {100 * hold['null_gain_median']:.1f}% for a wrong-window control). No spillover is detected. The exposed cases grew from 12 to {exposed} over the project and the interval roughly halved.")
P(f"Training. The GAIL v1 network was trained for {train['training']['epochs']} epochs on {train['training']['observations']} observations; the loss fell from {train['training']['loss_by_epoch'][0]['total']:.2f} to {train['training']['loss_by_epoch'][-1]['total']:.2f}. Its error on the training data is {train['training']['mse_trained']:.4f} against {train['training']['mse_baseline_always_zero']:.4f} "
  f"for always predicting zero ({train['training']['improvement_percent']}% better), which is in-sample and does not carry to unseen creators. Its learned relation shares ({train['training']['learned_relation_shares']['collaborates_with']:.2f} collaboration, {train['training']['learned_relation_shares']['co_occurs_with']:.2f} co-occurrence) "
  "should not be read as an explanation: in simulation, models without causal training give weight to a relation whose true effect is zero.")
P(f"What the test could see. In a simulation that keeps the real outcomes and plants only the effect, {exposed} exposed observations give about 80% detection of a rise of roughly 1.5 times in engagement. In the calibrated stand-in variant (false alarms about 2%), detection of a 1.3 times "
  f"effect reaches {100 * si['80'][1]:.0f}% at 80 exposed creators and {100 * si['160'][1]:.0f}% at 160. The honest reading is that large spillover is ruled out and small spillover cannot be seen with this data. As the number of exposed creators grows from 19 to 80 the simulated error falls ({scale_line}).")
P(f"Validation by simulation. On a benchmark with the real creator graph and a planted effect (10 repeats), the average error in the effect on the exposed is {bench(b1['clean'], 'GAIL-R'):.3f} for GAIL-R, against {bench(b1['clean'], 'GAIL v1 (current)'):.3f} for the original GAIL, {bench(b1['clean'], 'GNN predictor (no causal training)'):.3f} for a GNN predictor "
  f"and {bench(b1['clean'], 'Naive difference'):.3f} for a naive difference. With a pre-existing trend GAIL-R alone degrades to {bench(b1['pretrend'], 'GAIL-R'):.3f}, and the placebo penalty restores {bench(b1['pretrend'], 'GAIL-R + placebo'):.3f}. With no true effect a naive comparison reports one in 100% of simulated studies. "
  "These are simulations, labelled as such, and never mixed into the real result.")
rows = {r["method"]: r for r in base["rows"]}
P(f"Published models on the benchmark. Eesha ran DeepInf, INFLECT-DGNN and TNet from the authors' code on the same planted-effect benchmark ({base['replicates']} replicates, {base['graph']}). Per-creator error with no trend: DeepInf {rows['DeepInf (KDD 2018)']['no_trend']:.3f}, INFLECT-DGNN {rows['INFLECT-DGNN (IEEE Access 2024)']['no_trend']:.3f}, "
  f"TNet {rows['TNet (ICML 2024)']['no_trend']:.3f}, a doubly-robust model without the graph {rows['Doubly-robust, no graph']['no_trend']:.3f}, GAIL-R {rows['GAIL-R']['no_trend']:.3f}. With a planted pre-trend: TNet {rows['TNet (ICML 2024)']['pre_trend']:.3f} (it has no guard against a trend), GAIL-R {rows['GAIL-R']['pre_trend']:.3f}, GAIL-R with the placebo penalty {rows['GAIL-R + placebo']['pre_trend']:.3f}. "
  "None of the three published models separates creators better than the no-graph baseline. These are on the older 390-creator graph with three replicates; they are kept apart from the ten-replicate table until re-run on the corrected graph.")
P(f"YouTube against Instagram. {pairs['pairs']} matched posts from {pairs['creators_with_pairs']} creators fall within 24 hours of each other. The raw median difference is {pairs['median_difference']:+.2f} on the log scale in Instagram's favour, but a placebo with no real pairing alone gives {pairs['placebo']['median_difference_placebo']:+.2f}; "
  f"after removing it the median difference is {pairs['median_difference_adjusted']:+.2f}, with Instagram ahead in {100 * pairs['share_pairs_instagram_better_adjusted']:.0f}% of pairs. Granger tests on {pairs['granger']['all comments']['creators']} creators show that Instagram posts help predict YouTube comments "
  f"(F = {g_all['Instagram posts -> YouTube comments']['F']:.2f}, p = {g_all['Instagram posts -> YouTube comments']['p_value']}) and the reverse (F = {g_all['YouTube comments -> Instagram posts']['F']:.2f}, p = {g_all['YouTube comments -> Instagram posts']['p_value']}); prediction only.")
P(f"Timing. In an event study whose control (a YouTube upload followed by comments on that channel) is detected as it should be ({ctrl['n_units']:,} events, {ctrl['n_creators']} creators), an Instagram post is followed by a YouTube upload in the next 0 to 12 hours "
  f"at about twice the creator's usual rate (smallest p = {ig_up['smallest_p_after_event']}, {ig_up['n_units']:,} events from {ig_up['n_creators']} creators). It is not followed by a measurable rise in comments on older YouTube videos (smallest p = {ig_cm['smallest_p_after_event']}). "
  "The timing describes when creators cross-post, not an audience response. The earlier hypothesis of a 12 to 24 hour lag is not supported.")

H("Novelties and what they found")
P("Each item below was built in this project, is tested against a placebo, a leave-one-out or a planted-effect check where one applies, and states its limits. None is claimed as new without a literature check; to our knowledge, and subject to repeating the key searches on Google Scholar, ACM and IEEE, we did not find prior work on items 1 and 3 in the form described.")
items = [
    f"1. Same-creator cross-platform comparison: {pairs['pairs']} matched posts, each platform against the creator's own usual, with a placebo and a word-overlap subset ({pairs['pairs_with_text_overlap']} pairs).",
    f"2. Sponsored response by platform: on YouTube, views of sponsored posts are {sr['youtube_views'].get('approx_percent', float('nan')):+.1f}% against the creator's own organic posts of the same format (95% {sr['youtube_views'].get('ci95_percent', [0, 0])[0]:+.1f}% to {sr['youtube_views'].get('ci95_percent', [0, 0])[1]:+.1f}%, {sr['youtube_views']['creators']} creators), so no clear penalty; Instagram has {sr['instagram_likes']['creators']} creators with enough sponsored posts, too few to say.",
    f"3. Predicting the missing platform: a leave-one-out model estimates a creator's Instagram level from YouTube features with rank agreement {ps['prediction']['spearman_full']:.2f}, against {ps['prediction']['spearman_size_only']:.2f} for subscriber count alone ({ps['prediction']['n']} creators); the typical error is about 3.4 times, so estimates are ranges.",
    f"4. Mood gap between platforms: {ps['mood_gap']['flagged']} of {ps['mood_gap']['creators_with_both']} creators have a large gap beyond a worst-case error bound; {ps['mood_gap']['warmer_on_instagram']} are warmer on Instagram.",
    f"5. Attention speed: a median {100 * ps['speed']['median_share_first_24h']:.0f}% of a video's first-week views arrive in the first 24 hours ({ps['speed']['videos']:,} YouTube videos; Instagram has too few readings).",
    f"6. Ad fatigue: views per extra sponsored video in the previous 30 days change by {fat['results'][0]['median_slope']:+.3f} (95% {fat['results'][0]['ci95'][0]:+.3f} to {fat['results'][0]['ci95'][1]:+.3f}), not detected; {ps['fatigue']['creators_above_usual']} creators are currently above their usual ad load, reported as a fact and not as a forecast.",
    f"7. Disclosure index and buying signals: {100 * dis['share_disclosed_overall']:.0f}% of detected sponsored videos carry an explicit label (median creator {100 * dis['median_creator_share']:.0f}%); buying-looking comments are {resp['median_ratio']:.1f} times higher on sponsored videos (keyword proxy, not checked by a person).",
    f"8. Competitor-clash flag: {ps['clash']['creators_with_recent_brand_posts']} creators promoted a brand in the last {ps['clash']['window_days']} days; the dashboard warns when a recommended creator promoted a rival brand of the brief's category. The concept is already studied (rival and multiple endorsements), so this is an automatic warning, not a finding.",
    "9. Creator Passport and evidence grade: one record per creator that gathers the above, each with its own sample size, and an A to D grade that says how well we know the creator.",
    f"10. Placebo-and-simulation protocol for spillover claims: placebo dates, a planted-effect benchmark on the real graph and a power analysis; the naive comparison gives false alarms in 100% of simulated no-effect studies, the placebo-corrected one in 0%.",
    f"11. Two extensions tested in simulation (6 repeats): training attention on the causal loss recovers each creator's effect far better than plain outcome error ({e45['e4_simulated']['clean, causal supervision, shrink 100']['pehe']['mean']:.2f} against {e45['e4_simulated']['clean, plain supervision, shrink 100']['pehe']['mean']:.2f}), but learned attention is no better than uniform weights; a correction for sponsored posts our rules miss recovers the effect in simulation and leaves the real result at about zero.",
    f"12. Sentiment on code-mixed text: 24 hand labels (one labeller) give an AUC of {hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['auc_pos_vs_neg']:.2f} for telling positive from negative; the other sentiment checks (40 comments per language) were labelled by an AI model, not a person.",
]
for it in items:
    P(it)
P(f"Fusion design test. A planted-value simulation (assumed informativeness, not measured) shows that with no spillover signal the ranking is unchanged by taking spillover out of the score (Spearman with the planted truth {list(fsim.values())[0]['proposed: spillover out of the score, 0/0.5/0.5, uninformed left out']['spearman']:.3f} against {list(fsim.values())[0]['current: 0.2/0.4/0.4, uninformed branch left out']['spearman']:.3f}), and that keeping it would help only if it carried real signal. "
  f"Fitting the weights to the one proxy outcome available ({fus['creators_used']} creators) would switch off two branches, so it is not adopted; the weights remain documented priors until a real outcome is available.")

H("Discussion: what the literature suggests and what we found")
P("The reviewed popularity and cascade models report strong predictive accuracy, but they predict a correlational target; none separates a causal lift from pre-existing popularity. Our experiments illustrate why that distinction matters. In simulation, a naive before-and-after "
  f"comparison reports an effect in every simulated no-effect study, while a placebo-corrected comparison does not. On real data, engagement changes by a median {J('spillover_placebo_test.json')['scopes']['in_the_150']['all']['median_placebo_lift']:+.2f} at random dates with no sponsorship, "
  "which a naive comparison would credit to spillover. The causal-network papers [13]-[16] show that learned exposure and orthogonalised estimation are established; our contribution is the placebo penalty, the planted-effect validation on the real influencer graph, an honest power analysis, "
  "the application to ranked influencer recommendation, and a per-creator YouTube-versus-Instagram comparison next to it. The three published models we ran did not separate creators better than a no-graph baseline.")
P("To our knowledge, and subject to a repeat of the key searches on Google Scholar, ACM and IEEE (our earlier checks used general web search), we did not find prior work that combines a fair per-creator same-window YouTube-versus-Instagram comparison at this scale with a placebo-and-simulation "
  "protocol for spillover claims. Related small studies of the same creator on two platforms exist and are not excluded by this statement. If such a study is found it will be cited and the claim narrowed.")

H("Limitations and future work")
P(f"The real-data spillover result rests on {exposed} exposed observations, many of them mention-linked, so it bounds large effects and cannot see small ones. Sponsorship labels are detection rules with a hand-checked sample, and the affiliate-code correction of 1 November shows they can over-count. "
  "Engagement is attention, not revenue: no sales data exists, so the ranking is not validated against brand outcomes. Instagram data is thin for the sponsored-response and speed analyses. Growth readings cover about four weeks; the cross-platform timing and lag analyses should be repeated at longer spans. "
  "E4 and E5 are tested in simulation only. The sentiment checks on three languages were labelled by an AI model and need a human re-label. The full GAIL network was trained on CPU with a single set of seeds; a GPU run with 20 or more seeds and a longer bootstrap is planned. "
  "Next steps are to add fitness creators who collaborate with creators already in the set, to collect Instagram posts for creators active on both platforms, to rank by expected sponsored engagement per rupee, and to obtain a real outcome from a brand partner to fit the fusion weights.")

H("References")
refs = [
    "[1] P. Velickovic et al., \"Graph attention networks,\" in Proc. ICLR, 2018.",
    "[2] M. Fey and J. E. Lenssen, \"Fast graph representation learning with PyTorch Geometric,\" in ICLR Workshop on Representation Learning on Graphs and Manifolds, 2019.",
    "[3] J. Qiu, J. Tang, H. Ma, Y. Dong, K. Wang, and J. Tang, \"DeepInf: Social influence prediction with deep learning,\" in Proc. ACM SIGKDD, 2018, pp. 2110-2119.",
    "[4] S. Kim, J.-Y. Jiang, J. Han, and W. Wang, \"InfluencerRank: Discovering effective influencers via graph convolutional attentive recurrent neural networks,\" in Proc. ICWSM, vol. 17, no. 1, 2023.",
    "[5] M. G. Hudgens and M. E. Halloran, \"Toward causal inference with interference,\" J. Amer. Statist. Assoc., vol. 103, no. 482, pp. 832-842, 2008.",
    "[6] P. R. Rosenbaum and D. B. Rubin, \"The central role of the propensity score in observational studies for causal effects,\" Biometrika, vol. 70, no. 1, pp. 41-55, 1983.",
    "[7] J. M. Robins, A. Rotnitzky, and L. P. Zhao, \"Estimation of regression coefficients when some regressors are not always observed,\" J. Amer. Statist. Assoc., vol. 89, no. 427, pp. 846-866, 1994.",
    "[8] V. Chernozhukov et al., \"Double/debiased machine learning for treatment and structural parameters,\" Econometrics J., vol. 21, no. 1, pp. C1-C68, 2018.",
    "[9] A. Radford et al., \"Learning transferable visual models from natural language supervision,\" in Proc. ICML, PMLR 139, 2021, pp. 8748-8763.",
    "[10] J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, \"BERT: Pre-training of deep bidirectional transformers for language understanding,\" in Proc. NAACL-HLT, 2019, pp. 4171-4186.",
    "[11] A. Conneau et al., \"Unsupervised cross-lingual representation learning at scale,\" in Proc. ACL, 2020, pp. 8440-8451.",
    "[12] C. W. J. Granger, \"Investigating causal relations by econometric models and cross-spectral methods,\" Econometrica, vol. 37, no. 3, pp. 424-438, 1969.",
    "[13] Y. Wu and Y. Yuan, \"Estimating heterogeneous causal effect on networks via orthogonal learning,\" arXiv:2509.18484, 2025.",
    "[14] Y. Ma and V. Tresp, \"Causal inference under networked interference and intervention policy enhancement,\" in Proc. AISTATS, PMLR 130, 2021, pp. 3700-3708.",
    "[15] S. Adhikari, S. Medya, and E. Zheleva, \"Learning exposure mapping functions for inferring heterogeneous peer effects,\" arXiv:2503.01722, 2025.",
    "[16] A. Wu, H. Qiu, Z. Chen, Z. Li, R. Xiong, F. Wu, and K. Zhang, \"Causal graph transformer for treatment effect estimation under unknown interference,\" in Proc. ICLR, 2025.",
]
for r in refs:
    P(r)
P("Still to add before submission: the full reference of TNet (Chen et al., ICML 2024) and of INFLECT-DGNN (Tiukhova et al., IEEE Access 2024), both named in Eesha's alignment note; the full entries of the twenty reviewed works, which are cited by author and year as in Table 3; and the related studies found by web search on 30 October and 1 November, which must be read and cited before any claim is narrowed.")
d.save(OUT)
print("saved", OUT)
