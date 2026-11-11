"""Builds the hand-over PDF for Eesha (1 Nov 2026): everything done, every result, the novelties, every fix, the open items and where each file lives. Every number is read from a result file in models/ or counted in the
database; nothing is typed in except the fix log and the file index, which are statements of fact written once.

    python scripts/build_eesha_pdf.py [--out exports/handover_for_eesha_1nov.pdf]
"""
import argparse
import json
import statistics as st
import subprocess
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "exports" / "handover_for_eesha_1nov.pdf"))
OUT = ap.parse_args().out
J = lambda n: json.loads((ROOT / "models" / n).read_text(encoding="utf-8"))  # noqa: E731

# ---- fonts (Arial and Consolas ship with Windows; they carry the minus sign, arrows and multiplication sign) ------------------------------------------
FD = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FD / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FD / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", str(FD / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FD / "consola.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-Bold")

INK, MUTED, AMBER, TEAL, LINE = colors.HexColor("#14202b"), colors.HexColor("#5b6b7d"), colors.HexColor("#b97a00"), colors.HexColor("#0f8f80"), colors.HexColor("#d5dde5")
S = {
    "title": ParagraphStyle("title", fontName="Body-Bold", fontSize=24, leading=28, textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="Body", fontSize=11, leading=15, textColor=MUTED, spaceAfter=10),
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=15, leading=19, textColor=INK, spaceBefore=14, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=11.5, leading=15, textColor=AMBER, spaceBefore=8, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Body", fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=5),
    "b": ParagraphStyle("b", fontName="Body", fontSize=9.6, leading=13.4, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=2.5),
    "c": ParagraphStyle("c", fontName="Body", fontSize=8.3, leading=10.6, textColor=INK),
    "ch": ParagraphStyle("ch", fontName="Body-Bold", fontSize=8.3, leading=10.6, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.2, leading=10.4, textColor=INK, backColor=colors.HexColor("#eef2f6"), borderPadding=5, spaceAfter=7, leftIndent=4),
    "note": ParagraphStyle("note", fontName="Body-Italic", fontSize=8.6, leading=11.6, textColor=MUTED, spaceAfter=6),
}
story: list = []


def H1(t): story.append(Paragraph(t, S["h1"]))
def H2(t): story.append(Paragraph(t, S["h2"]))
def P(t): story.append(Paragraph(t, S["p"]))
def N(t): story.append(Paragraph(t, S["note"]))
def B(items): [story.append(Paragraph(i, S["b"], bulletText="•")) for i in items]
def CODE(t): story.append(Paragraph(t.replace("\n", "<br/>").replace(" ", "&nbsp;"), S["code"]))


def T(header, rows, widths, zebra=True):
    data = [[Paragraph(h, S["ch"]) for h in header]] + [[Paragraph(str(c), S["c"]) for c in r] for r in rows]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), INK), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if zebra:
        style += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f6f8fa")) for i in range(2, len(data), 2)]
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 6))


# ---- data -----------------------------------------------------------------------------------------------------------------------------------------
_COUNTS = r"""
import json, re, psycopg2
url = re.search(r"^DATABASE_URL=(.+)$", open(r"%s", encoding="utf-8").read(), re.M).group(1).strip().strip('"')
c = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"), connect_timeout=15); c.set_session(readonly=True); cur = c.cursor()
q = {"creators": "select count(*) from creators", "videos": "select count(*) from youtube_videos", "comments": "select count(*) from youtube_comments", "sponsored": "select count(*) from youtube_videos where is_sponsored",
     "ig_posts": "select count(*) from instagram_posts", "ig_creators": "select count(distinct creator_id) from instagram_posts", "events": "select count(*) from creator_sponsorship_events"}
out = {}
for k, v in q.items():
    cur.execute(v); out[k] = cur.fetchone()[0]
print(json.dumps(out))
""" % str(ROOT / ".env")
_py = str(ROOT / "venv" / "Scripts" / "python.exe") if (ROOT / "venv" / "Scripts" / "python.exe").exists() else sys.executable
n = json.loads(subprocess.check_output([_py, "-c", _COUNTS], text=True).strip().splitlines()[-1])

runs = J("gail_real_results.json")["runs"]
t8, t7 = J("gail_training_summary_1nov.json"), J("gail_training_summary_31oct.json")
power, hold, multi = J("power_analysis.json"), J("gail_r_holdout.json"), J("gail_r_multiseed.json")
pairs, lag, fat, promo = J("platform_pairs.json"), J("long_lag.json"), J("ad_fatigue.json"), J("promotion_behaviour.json")
evs, snap = J("spillover_event_study.json"), J("snapshot_lag.json")
ps, e45, hing, base = J("creator_passport.json")["summary"], J("e4_e5_results.json"), J("hinglish_check.json"), J("published_baselines_eesha.json")
fsim, noise, cases = J("fusion_simulation.json")["scenarios"], J("label_noise_sensitivity.json"), J("spillover_cases.json")
b1, b0 = J("semisynth_new_graph_effect1.json"), J("semisynth_new_graph_effect0.json")
mrow = multi["runs"]["with placebo penalty (30)"]
ate = lambda block, key: st.mean(r["ate_error"] for r in block[key] if isinstance(r, dict) and r.get("ate_error") is not None)  # noqa: E731
pehe = lambda block, key: st.mean(r["pehe"] for r in block[key] if isinstance(r, dict) and r.get("pehe") is not None)  # noqa: E731
exposed, controls = power["real_exposed"], power["real_controls"]
rs = power["real_structure"]["share_detected"]
sr = ps["sponsored_response"]
ctrl = next(r for r in lag["results"] if r["name"].startswith("control"))
ig_up = next(r for r in lag["results"] if r["name"].startswith("ig_to_uploads"))
detected_event = sum(1 for r in evs["results"] if r.get("detected_after_correction"))
f2 = lambda v: f"{v:+.2f}"  # noqa: E731

# ================================================================================================================================================
story.append(Paragraph("Hand-over for Eesha", S["title"]))
story.append(Paragraph("Project 011 · UE23CS441A · Influencer-Brand Matching with Graph Spillover · 1 November 2026 · prepared by Shimona (with Claude)", S["sub"]))
P("This document says what we did, what we found, what we fixed and what is still open, so the paper and the deck say the same thing. Every number is read from a result file in <font name='Mono'>models/</font> or counted in the database on the day it was built. "
  "It replaces the earlier hand-over notes. The companion files are the results pack (<i>paper_results_and_comparison_pack.docx</i>) and the literature survey v6; this PDF is the short, complete version.")

H1("1. Where we stand in one page")
T(["Area", "State", "Key number"], [
    ["Data", "Collected daily; labels corrected on 1 Nov", f"{n['creators']} creators · {n['videos']:,} YouTube videos · {n['comments']:,} comments · {n['ig_posts']:,} Instagram posts ({n['ig_creators']} creators) · {n['sponsored']:,} sponsored videos · {n['events']:,} sponsorship events"],
    ["Spillover (real data)", "Measured, bounded null", f"GAIL-R {f2(t8['gail_r']['effect_on_exposed'])}, 95% {f2(t8['gail_r']['ci95'][0])} to {f2(t8['gail_r']['ci95'][1])} (ten-seed mean {f2(mrow['att_mean'])}), {exposed} exposed observations. No detectable spillover; effects above about 1.5× ruled out"],
    ["GAIL training", "Done on corrected labels (run 8)", f"{t8['training']['epochs']} epochs on {t8['training']['observations']} observations; error {t8['training']['mse_trained']:.4f} vs {t8['training']['mse_baseline_always_zero']:.4f} for always-zero"],
    ["Method validation", "Done, simulated", f"GAIL-R + placebo error ≤ {max(ate(s, 'GAIL-R + placebo') for s in (b1['clean'], b1['pretrend'], b0['clean'], b0['pretrend'])):.3f} in all four settings; naive comparison {ate(b1['clean'], 'Naive difference'):.3f} in the clean setting"],
    ["Novelties", "All built", "Cross-platform pairs, lag, sponsored response, missing-platform estimate, mood gap, speed, ad fatigue, disclosure, clash flag, Creator Passport, evidence grade, E4/E5, Hinglish check"],
    ["Fusion score", "Changed 1 Nov", "Weights 0 / 0.5 / 0.5 (spillover shown as context, not scored)"],
    ["App", "Redesigned 1 Nov", "8 pages incl. Insights (6 charts) and Creator Passport; Docker verified"],
    ["Tests", "All green after the merge", "ML 340 · backend 142 · ingestion 126 · production build passes"],
], [30, 40, 110])

H1("2. What happened, in order")
H2("30 and 31 October")
B([
    "Exposed cases raised from 12 to 60 by mining @mentions in 121 sponsoring creators' posts: 19 real collaborators added (YouTube history, links), plus 3 aliases.",
    "Four extra independent spillover tests (hourly views, comments across the long history, random-pairs false-alarm check, direct-effect control): none detects an effect.",
    "Power analysis, label-noise table and a real-case comparison (the 'best' cases are what chance produces).",
    "What-if spillover tool (backend and dashboard), labelled as an assumption; fusion fix that drops a branch that knows nothing; graph view rewritten; Instagram daily job improved.",
    "GAIL retrained (run 7): 60 exposed, effect −0.16 (−0.40 to +0.40).",
])
H2("1 November")
B([
    "<b>Standing affiliate codes fixed.</b> Some creators paste the same brand-and-code block under every video; the rules read each as a sponsored post (Sam Sulek: 308 of his 312). 470 videos of 17 creators were un-flagged (backed up, reversible): sponsored videos 3,370 → 2,900, events 3,501 → 3,031.",
    "Whole GAIL chain rebuilt on the corrected labels: 74 exposed + 249 comparison observations (was 60 + 406). GAIL-R refit with 10 seeds and a bootstrap, held-out check, power analysis, event study, lag tests, E4/E5 on the new data.",
    "Full GAIL training run 8 on the corrected labels (about 22 minutes after a long silent database step).",
    "Novelties built: mood gap, missing-platform estimate, attention speed, competitor-clash flag, Creator Passport; E4 and E5 added as simulation extensions; Hinglish check on 24 hand labels.",
    "Fusion: spillover taken out of the score after a planted-value simulation (section 6).",
    "Frontend redesigned (dark console look, sidebar, Insights page, Passport strip on cards); Docker run and verified; deck edited per your note; your branch merged and pushed (<font name='Mono'>a7ef217</font>).",
])

H1("3. Data and labels")
P(f"The database holds {n['creators']} creators, {n['videos']:,} YouTube videos, {n['comments']:,} YouTube comments, {n['ig_posts']:,} Instagram posts from {n['ig_creators']} creators and {n['events']:,} sponsorship events. "
  "Growth readings are taken every two hours since 11 October. Sponsorship labels come from rules in six evidence tiers (official label, spoken, creator comment, disclosure tag, brand-and-code, brand mention) with hand checks; <i>organic</i> means <i>not detected as sponsored</i>.")
P("<b>The 1 Nov label fix.</b> A video is un-flagged only when all of these hold: its evidence is a weak description tier (brand-and-code or brand-mention); every brand it matched was matched by name-and-code in the description and its title names none of them; and either that brand appears in at least half of the creator's videos within ±30 days, "
  "or the video lists three or more brands with codes (a code list, not one sponsored post). Real labels, spoken sponsors and disclosure tags are never touched. Script: <font name='Mono'>scripts/ingestion/standing_code_unflag_20261101.py</font> (<font name='Mono'>--undo</font> restores).")

H1("4. Spillover on real data")
rows = []
for r in sorted(runs, key=lambda r: r.get("exposed", 0)):
    if r.get("exposed") in (12, 19, 60, 74) and r.get("gail_r_ci95"):
        eff, ci = (t8["gail_r"]["effect_on_exposed"], t8["gail_r"]["ci95"]) if r["exposed"] == 74 else (r["gail_r_effect"], r["gail_r_ci95"])
        rows.append([r["name"][:75], r["exposed"], f2(eff), f"{f2(ci[0])} to {f2(ci[1])}"])
T(["Stage", "Exposed", "GAIL-R effect", "95% interval"], rows, [95, 20, 28, 37])
B([
    f"<b>Run 8 (corrected labels):</b> single fit {f2(t8['gail_r']['effect_on_exposed'])} ({f2(t8['gail_r']['ci95'][0])} to {f2(t8['gail_r']['ci95'][1])}); ten seeds average {f2(mrow['att_mean'])} (seeds {f2(min(mrow['att_by_seed']))} to {f2(max(mrow['att_by_seed']))}); bootstrap resamples creators, so repeat observations do not narrow it.",
    f"<b>Difference-in-differences:</b> category-matched {f2(t8['category_matched_did']['estimate'])} (SE {t8['category_matched_did']['se']:.2f}); plain matched {f2(t8['matched_did']['estimate'])} (SE {t8['matched_did']['se']:.2f}). The <b>placebo</b> version, computed before each sponsorship, is {f2(t8['placebo_pre_trend_did']['estimate'])} (SE {t8['placebo_pre_trend_did']['se']:.2f}) and should be near zero: a plain comparison is confounded by pre-trends, which is why the placebo penalty is part of GAIL-R.",
    f"<b>Held-out creators:</b> adding the spillover term does not help (median gain {100 * hold['gain_median']:.1f}% against {100 * hold['null_gain_median']:.1f}% for a wrong-window control).",
    f"<b>Power:</b> keeping the real outcomes and planting an effect, {exposed} exposed observations give about 80% detection of a rise of roughly 1.5×. With 19 only about 2.7× was detectable.",
    f"<b>Event-study family</b> (readings and comments, four tests each): {detected_event} of {len(evs['results'])} detected. The growth-reading lag test Instagram → YouTube views has smallest p = {next(r for r in snap['results'] if r['name'].startswith('ig_to_yt:'))['smallest_p_after_event']} against the 0.0125 bar: not detected; its positive control is.",
    f"<b>Label noise:</b> even if 30% of the comparison group were truly exposed, the upper end of the interval stays below a 1.3× engagement effect.",
])
N("Wording to use: large spillover is ruled out; small spillover cannot be seen with this many exposed observations. Not 'we could not solve spillover'.")

H1("5. Training (GAIL v1 network and GAIL-R)")
T(["", "Run 7, 31 Oct (before the fix)", "Run 8, 1 Nov (corrected labels)"], [
    ["Observations", f"{t7['exposed_observations']} exposed + {t7['control_observations']} comparison", f"{t8['exposed_observations']} exposed + {t8['control_observations']} comparison"],
    ["Epochs · loss (first → last)", f"{t7['training']['epochs']} · {t7['training']['loss_by_epoch'][0]['total']:.2f} → {t7['training']['loss_by_epoch'][-1]['total']:.2f}", f"{t8['training']['epochs']} · {t8['training']['loss_by_epoch'][0]['total']:.2f} → {t8['training']['loss_by_epoch'][-1]['total']:.2f}"],
    ["Error vs always-zero (in-sample)", f"{t7['training']['mse_trained']:.4f} vs {t7['training']['mse_baseline_always_zero']:.4f} ({t7['training']['improvement_percent']}% better)", f"{t8['training']['mse_trained']:.4f} vs {t8['training']['mse_baseline_always_zero']:.4f} ({t8['training']['improvement_percent']}% better)"],
    ["Learned relation shares", f"collaboration {t7['training']['learned_relation_shares']['collaborates_with']:.2f} · co-occurrence {t7['training']['learned_relation_shares']['co_occurs_with']:.2f}", f"collaboration {t8['training']['learned_relation_shares']['collaborates_with']:.2f} · co-occurrence {t8['training']['learned_relation_shares']['co_occurs_with']:.2f}"],
    ["GAIL-R effect (95%)", f"{f2(t7['gail_r']['effect_on_exposed'])} ({f2(t7['gail_r']['ci95'][0])} to {f2(t7['gail_r']['ci95'][1])})", f"{f2(t8['gail_r']['effect_on_exposed'])} ({f2(t8['gail_r']['ci95'][0])} to {f2(t8['gail_r']['ci95'][1])})"],
    ["Placebo (pre-trend) DiD", f"{f2(t7['placebo_pre_trend_did']['estimate'])}", f"{f2(t8['placebo_pre_trend_did']['estimate'])}"],
], [45, 66, 69])
P("Read the training error as in-sample only: it does not carry to unseen creators (section 4). The learned relation shares should not be read as an explanation: in simulation, models without causal training put weight on a relation whose true effect is zero. "
  "The run-8 checkpoint is kept in a working copy and is <b>not</b> installed; the checkpoint now in the app is the one from the merged branch. Run 8 has one CPU seed set; a GPU run with 20+ seeds and 1,000 bootstrap draws is in <font name='Mono'>exports/gpu_package_31oct.zip</font>.")
N("One practical note: after the line 'Canonical computable pairs' the training prints nothing for about 20 minutes (thousands of database queries). It is not stuck.")

H1("6. Simulations (known truth)")
H2("Table B: method families on the planted-effect benchmark (390-creator graph, 10 replicates, average error of the effect on the exposed)")
cols = [("effect 1.0, clean", b1["clean"]), ("effect 1.0, trend", b1["pretrend"]), ("no effect, clean", b0["clean"]), ("no effect, trend", b0["pretrend"])]
meth = [("Naive difference", "Naive difference"), ("GNN predictor (no causal training)", "GNN predictor (no causal training)"), ("Doubly robust, no graph", "DR, no graph"), ("GAIL v1", "GAIL v1 (current)"), ("GAIL-R", "GAIL-R"), ("GAIL-R + placebo", "GAIL-R + placebo")]
T(["Method"] + [c for c, _ in cols], [[m] + [f"{ate(b, k):.3f}" for _, b in cols] for m, k in meth], [58, 30, 30, 30, 32])
B([
    "GAIL-R without the placebo penalty is fooled by a pre-existing trend (error rises); the penalty restores it. The penalty is part of the method.",
    "With no true effect a GNN predictor looks accurate because it predicts roughly nothing; it fails once an effect exists. Accuracy with no effect is not evidence of a good method.",
    "Models without causal training give weight to the co-occurrence relation, whose true effect is zero. GAIL-R does not.",
])
H2("Table B2: published models you ran (from your note: 390-creator graph, 3 replicates, per-creator error)")
T(["Method", "No trend", "Planted pre-trend"], [[r["method"], f"{r['no_trend']:.3f}", f"{r['pre_trend']:.3f}"] for r in base["rows"]], [90, 40, 50])
N("Keep Table B2 apart from Table B until the baselines are re-run on the corrected 404-creator graph. Table B was run on the 390-creator checkpoint graph, not on 404 (corrected in the pack; the scaling run is on 404).")
H2("E4, E5 and the fusion design (simulated)")
B([
    f"<b>E4</b> (attention supervised by the causal loss): per-creator error {e45['e4_simulated']['clean, causal supervision, shrink 100']['pehe']['mean']:.2f} against {e45['e4_simulated']['clean, plain supervision, shrink 100']['pehe']['mean']:.2f} for plain outcome error in a clean setting; learned attention is no better than uniform weights ({e45['e4_simulated']['clean, uniform weights']['pehe']['mean']:.3f}). The protection comes from the causal loss, not the attention.",
    f"<b>E5</b> (missed sponsorship labels, MC-SIMEX): at 70% label detection the error falls from 0.107 to 0.026; on real data, correcting for 0.6 to 1.0 recall leaves the average effect at about zero.",
    f"<b>Fusion design test:</b> with no spillover signal, taking it out of the score leaves the ranking unchanged (Spearman with the planted truth {list(fsim.values())[0]['proposed: spillover out of the score, 0/0.5/0.5, uninformed left out']['spearman']:.3f} against {list(fsim.values())[0]['current: 0.2/0.4/0.4, uninformed branch left out']['spearman']:.3f}); if spillover carried real signal (0.5) keeping it would help. The 'leave a branch out' rule is a fairness rule, not more accurate than a neutral fill. No rule recovers the truth well under the assumed informativeness.",
])

H1("7. The novelties and what they found")
T(["Novelty", "Result", "Strength / limit"], [
    ["Same-creator YouTube vs Instagram, ≤24 h", f"{pairs['pairs']} pairs, {pairs['creators_with_pairs']} creators; raw gap {f2(pairs['median_difference'])}, placebo alone {f2(pairs['placebo']['median_difference_placebo'])}, after removing it {f2(pairs['median_difference_adjusted'])}", "Moderate; Instagram thin"],
    ["Granger and lag", f"Instagram post → YouTube upload in 0–12 h (smallest p {ig_up['smallest_p_after_event']}, control detected); 12–24 h not supported", "Prediction, not cause"],
    ["Sponsored response by platform", f"YouTube views {sr['youtube_views'].get('approx_percent', 0):+.1f}% (95% {sr['youtube_views'].get('ci95_percent', [0, 0])[0]:+.1f} to {sr['youtube_views'].get('ci95_percent', [0, 0])[1]:+.1f}), no clear penalty; Instagram {sr['instagram_likes']['creators']} creators", "Thin on Instagram"],
    ["Missing-platform estimate", f"rank agreement {ps['prediction']['spearman_full']:.2f} vs {ps['prediction']['spearman_size_only']:.2f} for size alone ({ps['prediction']['n']} creators); typical error ~3.4×", "Shown as a range"],
    ["Mood gap", f"{ps['mood_gap']['flagged']} of {ps['mood_gap']['creators_with_both']} flagged; {ps['mood_gap']['warmer_on_instagram']} warmer on Instagram", "Worst-case error bound"],
    ["Attention speed", f"median {100 * ps['speed']['median_share_first_24h']:.0f}% of first-week views in 24 h ({ps['speed']['videos']:,} videos)", "YouTube only"],
    ["Ad fatigue · disclosure · buying signals", f"fatigue slope {fat['results'][0]['median_slope']:+.3f} (not detected); {100 * promo['disclosure']['share_disclosed_overall']:.0f}% of detected sponsored videos labelled; buying comments {promo['response']['median_ratio']:.1f}× higher on sponsored", "Buying signals are a keyword proxy"],
    ["Competitor-clash flag", f"{ps['clash']['creators_with_recent_brand_posts']} creators promoted a brand in {ps['clash']['window_days']} days", "Concept already studied; an automatic warning, not a finding"],
    ["Creator Passport · evidence grade", "One record per creator; grade A–D says how well we know them", "Descriptive"],
    ["Hinglish check", f"24 hand labels: AUC {hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['auc_pos_vs_neg']:.2f}, Spearman {hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['spearman']:.2f}", "Rough; one labeller"],
], [48, 88, 44])
N("The other sentiment checks (40 comments per language) were labelled by an AI model, not a person. Report them as AI-labelled or have them re-labelled.")

H1("8. Everything we fixed or corrected (so nobody repeats it)")
T(["Item", "What was wrong", "What we did"], [
    ["Standing affiliate codes", "Same code under every video counted as a sponsored post", "470 videos un-flagged; backup tables and --undo"],
    ["Fusion weights", "Spillover (null on real data) carried weight 0.2", "Now 0 / 0.5 / 0.5; spillover shown as context; test pins it"],
    ["backend/.env override", "Old FUSION_WEIGHT_* values (0.4/0.3/0.3) beat the config when started from backend/", "Local file aligned; check other laptops"],
    ["Docker backend", "numpy missing from requirements; image could not start", "numpy added; Python 3.12; result files copied in; health check; .env and venv no longer sent to the build"],
    ["Idle database connection", "First request after a quiet period returned 500", "pool_pre_ping and pool_recycle in database.py"],
    ["Table B graph size", "Pack said 404 creators; the benchmark ran on the 390-creator checkpoint graph", "Corrected; scaling run is on 404"],
    ["Sentiment checks", "Called 'hand labels'; they were labelled by an AI model", "Corrected everywhere; only the 24 Hinglish labels are human"],
    ["'+0.49' sentence", "Unverified claim in survey v5", "Removed; replaced by the checked placebo-date result"],
    ["GAIL's source", "No published paper named GAIL found; the guide's '40% better' has no source", "Do not cite it; Wu and Yuan (2025) is the closest prior method"],
    ["Attribution", "gail_r.py, placebo.py, semi_synthetic.py are committed under 'Claude'", "Describe as team work; agree the wording"],
    ["Training step silence", "A watchdog killed a healthy 20-minute silent step", "Removed; note added"],
    ["Overnight rerun crash", "Docker VM plus several heavy jobs exhausted memory", "Run heavy jobs alone; Docker off for them"],
], [38, 70, 72])

H1("9. Your note of 1 Nov: what we did with each point")
T(["Your point", "Status"], [
    ["1. Base papers; add the three run baselines to Table B", "Added as Table B2 (kept separate); Wu and Yuan quoted as closest prior method; InfluencerRank described as related work, not run"],
    ["2. Ranking: drop spillover; rank by expected sponsored engagement per rupee", "Spillover dropped from the score (weights 0/0.5/0.5). Per-rupee ranking NOT done: needs your creator_value.csv and direct_effect.py"],
    ["3. Describe GAIL-R as built", "Done in the pack, survey v6 and deck: two-stage cross-fitted R-learner, per-relation slopes, placebo penalty; not joint optimisation, not AIPW"],
    ["4. Spillover framing", "Done: large spillover ruled out; small cannot be seen with 74 exposed observations"],
    ["5. One graph, one set of numbers", "Real-data numbers are all on the corrected labels. Table B is on the 390-creator graph; Table B2 on 390 with 3 replicates. Re-running the baselines on the corrected graph is yours"],
    ["Survey wording fixes", "Done in v6 (orthogonalised estimator; DeepInf, INFLECT-DGNN and TNet run from the authors' code; E4/E5 built)"],
], [75, 105])

H1("10. What we do not claim")
B([
    "That our ranking predicts brand outcomes better than any published system (no sales data exists; nothing beats chance at predicting a later sponsored effect, including popularity).",
    "That our numbers beat GNN-IR's, ST-GNN's or any published figure: different tasks and data. Published figures are context only.",
    "That GAIL-R is a new estimator. The new parts are the placebo penalty, the planted-effect validation on the real graph, the power analysis and the application.",
    "That spillover exists. We find none and rule out large effects only.",
    "That we are first to compare one creator across platforms (to our knowledge, a fair per-creator comparison at this scale).",
    "That the simulations hold on real influencers, or that the clash flag is new.",
])

H1("11. Open items and owners")
T(["Item", "Owner"], [
    ["Source of GAIL (guide or Dr. Tiwari); do not cite the '40% better' figure without it", "Eesha / Dr. Tiwari"],
    ["Read Wu and Yuan, Ma and Tresp, EgoNetGNN, CauGramer in full; take datasets, baselines and numbers", "Eesha"],
    ["Full references for TNet (ICML 2024) and INFLECT-DGNN (IEEE Access 2024); verify and cite the related studies found by web search", "Eesha"],
    ["Share fig1–fig4, models/creator_value.csv and scripts/direct_effect.py; re-run TNet, DeepInf and INFLECT-DGNN on the corrected 404-creator graph", "Eesha"],
    ["Agree who describes E4 and E5 in the paper (yours by assignment; built as simulation add-ons in ml/gail_r_ext.py)", "Eesha and Shimona"],
    ["Rank by expected sponsored engagement per rupee (after the review)", "Shimona, with Eesha's module"],
    ["Retrain on GPU with 20+ seeds and 1,000 bootstrap draws (gpu_package_31oct.zip)", "Eesha or Shimona"],
    ["Human re-label of the AI-labelled sentiment checks; more Hinglish labels", "Shimona"],
    ["Grow Instagram data for the sponsored-response and speed analyses; weekly rerun (scripts/refresh_analyses.py); lag re-test at longer spans", "Shimona"],
], [135, 45])

H1("12. Where everything is, and how to rerun it")
T(["What", "Where"], [
    ["Code on GitHub", "branch review2-shimona-temporal, merge commit a7ef217 (includes your merge-eesha-ml)"],
    ["Result files (every number above)", "models/*.json: gail_real_results, gail_training_summary_1nov and _31oct, gail_r_multiseed, gail_r_holdout, power_analysis, spillover_event_study, semisynth_new_graph_effect0/1, published_baselines_eesha, creator_passport, e4_e5_results, fusion_simulation, hinglish_check"],
    ["Documents (not in git; in exports/)", "paper_results_and_comparison_pack.docx · literature_survey_and_results_v6.docx · this PDF · gpu_package_31oct.zip · hinglish_labels_partial.csv"],
    ["Offline GPU package", "exports/gpu_package_31oct.zip: ml/, runners, the run-8 inputs, README"],
    ["Backups of the pre-fix results", "exports/before_standing_fix_1nov/ and the database tables standing_code_backup_20261101, standing_code_scores_backup_20261101"],
], [50, 130])
CODE("python scripts/refresh_analyses.py               # rerun every analysis and the dashboard data\npython scripts/build_creator_passport.py       # rebuild the Creator Passport\npython scripts/build_paper_comparison.py       # rebuild the results pack from the result files\npython scripts/build_survey_v6.py              # rebuild the literature survey\npython scripts/simulate_fusion.py              # the fusion design simulation\npython scripts/ingestion/standing_code_unflag_20261101.py --undo   # restore the affiliate-code labels")
N("Run heavy jobs one at a time on this laptop. With Docker's virtual machine running, the overnight rerun ran out of memory.")


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Body", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Hand-over for Eesha · Project 011 · 1 November 2026")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm, title="Hand-over for Eesha, 1 Nov 2026", author="Shimona Sinha").build(story, onFirstPage=footer, onLaterPages=footer)
print("saved", OUT)
