"""Paper changes for Eesha (23 Nov 2026): what to change in the IEEE paper (version of 13 Nov, 6 pages) now that the final
results are in, with ready-to-paste text, four new figures (also saved as PNG for the .tex) and every number's source.

    python scripts/build_paper_changes_pdf.py
    -> exports/paper_changes_for_eesha_23nov.pdf and exports/paper_figures_23nov/*.png

Every number below is copied from a result file written when that test ran (named next to it) or from a live read-only
count of the database on 23 Nov 2026. Nothing here is a new analysis. The hybrid simulation is method validation only.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from math import erf, log, sqrt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "exports" / "paper_changes_for_eesha_23nov.pdf"
FIG = ROOT / "exports" / "paper_figures_23nov"
FIG.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- numbers (source in each comment)
# SPILLOVER results: (label, estimate, lo, hi, group, source)
FOREST = [
    ("Tag: tagged creator, 7 days (291 events)", 0.095, 0.005, 0.185, "detected", "AUDIENCE_FLOW_RESULTS_8NOV.md l.128"),
    ("Joint video: small featured creators, 14 days (67)", 0.277, 0.113, 0.529, "detected", "AUDIENCE_FLOW_RESULTS_8NOV.md l.164"),
    ("After a linked creator's bad moment: small creators (417)", 0.1075, 0.0175, 0.1992, "detected", "NEGATIVE_SPILLOVER_PLAN_14NOV.md l.40"),
    ("GAIL-R final: small creators (187 exposed)", 0.1288, -0.1000, 0.3781, "gail", "GAIL_R_RESULTS_15NOV.md sec. 9"),
    ("GAIL-R final: all creators (924 exposed)", 0.0176, -0.0623, 0.0886, "gail", "GAIL_R_RESULTS_15NOV.md sec. 9"),
    ("Negative spillover: all linked creators (1,794)", 0.0082, -0.0332, 0.0502, "none", "NEGATIVE_SPILLOVER_PLAN_14NOV.md l.38"),
    ("Placebo pre-trend, final GAIL-R run", 0.0223, 0.0223 - 1.96 * 0.0396, 0.0223 + 1.96 * 0.0396, "placebo", "GAIL_R_RESULTS_15NOV.md sec. 9 (SE 0.0396)"),
]
POWER_SE = {"All creators (924 exposed)": 0.0385, "Small creators (187 exposed)": 0.1220}  # GAIL_R_RESULTS_15NOV.md sec. 10
HYB1 = [(0, 0), (10, 0), (20, 0), (30, 1), (40, 4), (60, 13)]  # sec. 11: planted %, detected of 40
HYB2 = {"+13% planted": [(2, 4), (4, 7), (8, 9)], "+30% planted": [(2, 8), (4, 9), (8, 10)]}  # sec. 12: x creators, detected of 10
GRANGER = [("Instagram posts -> YouTube comments", 1.559, 1.016, 0.002), ("YouTube comments -> Instagram posts", 1.561, 1.013, 0.014)]  # models/cross_promotion_mechanism_10nov.json
LIVE = [  # read-only counts, 23 Nov 2026
    ("Creators", "660"), ("Dated sponsorship events", "4,294"), ("YouTube videos / comments", "343,676 / 2,333,098"),
    ("Post readings over time (snapshots)", "794,355"), ("Profile readings over time", "136,727"), ("Instagram posts / comments", "4,146 / 37,692"),
    ("Instagram profiles", "28,413"), ("Reddit posts / comments", "3,308 / 61,570"),
]
FINAL_RUN = [  # GAIL_R_RESULTS_15NOV.md sec. 9
    ("Collaboration events (tags + joint videos, pooled)", "1,768 events on 754 pairs"), ("Directed event edges in the model graph", "728"),
    ("Computable pairs", "1,701"), ("Exposed observations, all creators", "924"), ("Exposed, small creators (< 100k)", "187 of 5,744 rows"),
]

# ---------------------------------------------------------------- figures (light, paper style)
plt.rcParams.update({"font.family": "Arial", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
C = {"detected": "#0f8f80", "gail": "#b97a00", "none": "#5b6b7d", "placebo": "#9aa7b4"}


def fig_forest():
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    for i, (lab, e, lo, hi, g, _) in enumerate(reversed(FOREST)):
        ax.plot([lo, hi], [i, i], color=C[g], lw=2.2, solid_capstyle="round")
        ax.plot(e, i, "o", color=C[g], ms=6, mec="white", mew=1)
        ax.text(hi + 0.012, i, "%+.3f" % (int(e * 1000 + (0.5 if e >= 0 else -0.5)) / 1000), va="center", fontsize=8, color="#14202b")  # round half away from zero, as in the table
    ax.axvline(0, color="#14202b", lw=0.8, ls="--")
    ax.set_yticks(range(len(FOREST)), [f[0] for f in reversed(FOREST)], fontsize=8)
    ax.set_xlabel("Spillover effect, 95% interval (log scale; 0.1 = about +10%)")
    handles = [plt.Line2D([], [], color=C[k], lw=2.2, marker="o", label=v) for k, v in
               [("detected", "detected (interval above 0)"), ("gail", "GAIL-R, not significant"), ("none", "not detected"), ("placebo", "placebo check")]]
    ax.legend(handles=handles, fontsize=7, frameon=False, loc="lower right")
    fig.tight_layout()
    p = FIG / "fig_spillover_forest.png"
    fig.savefig(p, dpi=220)
    plt.close(fig)
    return p


def phi(z):
    return 0.5 * (1 + erf(z / sqrt(2)))


def fig_power():
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    xs = [i for i in range(0, 61)]
    for (lab, se), col in zip(POWER_SE.items(), ["#0f8f80", "#b97a00"]):
        ax.plot(xs, [100 * phi(log(1 + x / 100) / se - 1.96) for x in xs], color=col, lw=2.2, label=f"{lab}, SE {se}")
    ax.axhline(80, color="#5b6b7d", lw=0.8, ls="--")
    ax.text(1, 82, "80% power", fontsize=7, color="#5b6b7d")
    ax.axvline(12.9, color="#b97a00", lw=0.8, ls=":")
    ax.text(13.5, 8, "real small-creator\nestimate +12.9%", fontsize=7, color="#b97a00")
    ax.set_xlabel("True spillover (% engagement)")
    ax.set_ylabel("Chance GAIL-R detects it (%)")
    ax.set_ylim(0, 102)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    fig.tight_layout()
    p = FIG / "fig_gailr_power.png"
    fig.savefig(p, dpi=220)
    plt.close(fig)
    return p


def fig_hybrid():
    fig, (a, b) = plt.subplots(1, 2, figsize=(6.6, 2.7))
    a.bar([str(x) for x, _ in HYB1], [100 * d / 40 for _, d in HYB1], color="#b97a00", width=0.6)
    a.set_xlabel("Planted spillover (%), real 187 small creators")
    a.set_ylabel("Studies detecting it (%)")
    a.set_title("A. Real sample size (40 studies each)", fontsize=8.5, loc="left")
    a.set_ylim(0, 100)
    for (lab, pts), col in zip(HYB2.items(), ["#b97a00", "#0f8f80"]):
        b.plot([x for x, _ in pts], [10 * d for _, d in pts], "o-", color=col, lw=2.2, label=lab)
    b.axhline(80, color="#5b6b7d", lw=0.8, ls="--")
    b.set_xticks([2, 4, 8], ["2x\n(336)", "4x\n(672)", "8x\n(1,344)"])
    b.set_xlabel("Small creators per study")
    b.set_ylim(0, 105)
    b.set_title("B. More creators (10 studies each)", fontsize=8.5, loc="left")
    b.legend(fontsize=7, frameon=False, loc="lower right")
    fig.tight_layout()
    p = FIG / "fig_hybrid_detection.png"
    fig.savefig(p, dpi=220)
    plt.close(fig)
    return p


def fig_granger():
    fig, ax = plt.subplots(figsize=(5.4, 2.7))
    labs = [g[0] for g in GRANGER]
    y = range(len(GRANGER))
    ax.barh([i + 0.18 for i in y], [g[1] for g in GRANGER], height=0.34, color="#0f8f80", label="real timing")
    ax.barh([i - 0.18 for i in y], [g[2] for g in GRANGER], height=0.34, color="#c7d0d9", label="placebo (shuffled timing), median")
    for i, g in enumerate(GRANGER):
        ax.text(g[1] + 0.02, i + 0.18, f"F {g[1]}, p = {g[3]}", va="center", fontsize=7.5)
    ax.set_yticks(list(y), labs, fontsize=8)
    ax.set_xlabel("Granger F statistic (105 creators, lags 1-3 days)")
    ax.set_xlim(0, 2.1)
    ax.legend(fontsize=7, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    fig.tight_layout()
    p = FIG / "fig_cross_platform_granger_105.png"
    fig.savefig(p, dpi=220)
    plt.close(fig)
    return p


figs = {"forest": fig_forest(), "power": fig_power(), "hybrid": fig_hybrid(), "granger": fig_granger()}

# ---------------------------------------------------------------- PDF
FD = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FD / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FD / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", str(FD / "ariali.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-Bold")
INK, MUTED, AMBER, TEAL, LINE, RED = (colors.HexColor(h) for h in ("#14202b", "#5b6b7d", "#b97a00", "#0f8f80", "#d5dde5", "#b3261e"))
S = {
    "title": ParagraphStyle("t", fontName="Body-Bold", fontSize=20, leading=24, textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("s", fontName="Body", fontSize=10, leading=14, textColor=MUTED, spaceAfter=8),
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=13.5, leading=17, textColor=INK, spaceBefore=12, spaceAfter=5),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=10.5, leading=14, textColor=AMBER, spaceBefore=7, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Body", fontSize=9.4, leading=13.2, textColor=INK, spaceAfter=4),
    "li": ParagraphStyle("li", fontName="Body", fontSize=9.4, leading=13, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=2),
    "paste": ParagraphStyle("paste", fontName="Body", fontSize=9.2, leading=13, textColor=INK, backColor=colors.HexColor("#f3f7f6"),
                            borderColor=colors.HexColor("#b9dcd6"), borderWidth=0.6, borderPadding=6, spaceBefore=4, spaceAfter=8),
    "small": ParagraphStyle("sm", fontName="Body", fontSize=8, leading=11, textColor=MUTED, spaceAfter=3),
    "cell": ParagraphStyle("c", fontName="Body", fontSize=8.4, leading=11, textColor=INK),
    "cellb": ParagraphStyle("cb", fontName="Body-Bold", fontSize=8.4, leading=11, textColor=INK),
}
P = lambda t, s="p": Paragraph(t, S[s])  # noqa: E731
B = lambda t: Paragraph(t, S["li"], bulletText="•")  # noqa: E731


def table(rows, widths, head=True):
    t = Table([[Paragraph(str(c), S["cellb" if head and i == 0 else "cell"]) for c in r] for i, r in enumerate(rows)], colWidths=widths, repeatRows=1 if head else 0)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f5") if head else colors.white),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def figure(path, caption, w=170):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(str(path)).getSize()
    return KeepTogether([Image(str(path), width=w * mm, height=w * mm * ih / iw), P(caption, "small"), Spacer(1, 4)])


story = [
    P("Paper changes for the final version", "title"),
    P("For Eesha · prepared 23 Nov 2026 · applies to <i>capstone_paper</i> of 13 Nov 2026 (6 pages) · every number has its source file", "sub"),
    P("Why the paper must change", "h1"),
    P("The 13 Nov paper says spillover was <b>not</b> detected and that GAIL-R bounds it <b>below about 3%</b>, so <i>\"a brand's return comes from the "
      "sponsored creator's own audience\"</i>. That reading came from paid sponsorships onto all collaborators (305 exposed). The final work "
      "(14-22 Nov) changes the story:"),
    B("Spillover <b>is detected</b> through creator <b>collaborations</b>: a tagged creator gains about <b>+10%</b> engagement in 7 days; small creators "
      "(&lt;100k) featured in a joint video gain about <b>+32%</b> in 14 days."),
    B("The same creator's <b>Instagram posts predict YouTube comments</b> 1-3 days later (105 creators, p = 0.002), and the reverse (p = 0.014)."),
    B("A creator's bad audience moment does <b>not</b> hurt linked creators; small linked creators even rose (+11%)."),
    B("The final GAIL-R run on all data is <b>positive</b> (small creators +12.9%, all +1.8%) but <b>not significant</b>; a power analysis and a hybrid "
      "simulation show why: it needs about 2-8x more small-creator collaborations."),
    B("Paid sponsorship onto collaborators stays small: above about +8% is ruled out (GAIL-R 14 Nov, -0.090 [-0.203, +0.074])."),
    P("So the <b>\"below 3%\" claim and the \"return comes only from the creator's own audience\" conclusion must be removed</b>: the 3% bound was for "
      "paid sponsorship on the earlier 305-observation sample, and collaboration spillover is now detected."),
    P("<font color='#b3261e'><b>Honesty rules to keep in the text:</b></font> the hybrid simulation uses planted effects and is method validation only, "
      "never evidence that spillover exists; Granger is prediction, not cause; secondary results are labelled secondary.", "p"),

    P("1. Abstract (replace fully)", "h1"),
    P("We study sponsorship and collaboration spillover on a multi-platform network of 660 Indian fitness and health creators with 4,294 dated "
      "sponsorship events and about 3.7 million records. The original design, GAIL, a jointly trained doubly robust graph-attention model, memorised "
      "outcomes on data of this size. We therefore propose GAIL-R, a cross-fitted R-learner with relation-specific exposure, time-window effects, "
      "attention shrunk toward uniform weights, and a placebo penalty against pre-existing trends. On a benchmark built from the real graph GAIL-R's "
      "per-creator error is 0.07-0.13, against 0.44-0.58 for TNet, DeepInf and INFLECT-DGNN, and on a randomised field experiment with a published "
      "spillover of +0.291 it estimates +0.313. On our network, pre-registered tests detect spillover through collaborations: a tagged creator's "
      "engagement rises about 10% in the following week (95% interval +0.005 to +0.185, log scale) and small creators featured in a joint video gain "
      "about 32% (+0.113 to +0.529). The same creator's Instagram posts predict comments on their YouTube videos one to three days later (p = 0.002). "
      "GAIL-R's estimate for small creators is positive (+0.129) but not yet significant; a power analysis and a hybrid simulation with planted "
      "effects show it needs two to eight times more small-creator collaborations. A ranking for brands combines value per rupee, audience mood and "
      "content fit, and reports GAIL's network reach alongside.", "paste"),

    P("2. Introduction: objectives (Section I.C)", "h1"),
    B("Objective 3: change <i>\"determine the degree of impact that cannot be excluded\"</i> to <i>\"test for spillover through sponsorships and creator "
      "collaborations, and across platforms for the same creator\"</i>."),
    B("Add an objective: <i>\"To test whether a creator's activity on Instagram predicts audience activity on their YouTube channel (cross-platform "
      "lag).\"</i>"),

    P("3. Data (Section III, Table I)", "h1"),
    P("Replace Table I with the counts below (read-only database count, 23 Nov 2026) and add the final GAIL-R run's sample.", "p"),
    table([["Item", "Count"]] + [list(r) for r in LIVE], [95 * mm, 70 * mm]),
    Spacer(1, 5),
    table([["Final GAIL-R run (21-22 Nov data)", "Count"]] + [list(r) for r in FINAL_RUN], [95 * mm, 70 * mm]),
    P("Source: GAIL_R_RESULTS_15NOV.md section 9. In III.C replace \"7,061 computable pairs ... 305 observations\" with the final-run numbers. The "
      "creator count also changes in the abstract, Table I and the text (651 to 660).", "small"),

    P("4. Methods: add a short subsection \"Pre-registered spillover tests\" (Section IV)", "h1"),
    P("Every test below had its plan written and pushed before its data, was run once, and is reported whatever the result. Suggested text:", "p"),
    P("<b>Event tests.</b> For a collaboration event (creator A tags B, or B appears in A's joint video) we compare B's engagement (views + likes) on posts "
      "in the window after the event with B's own 30-day baseline, on the log scale, with a placebo that moves the event back one window; an effect is "
      "detected when its 95% interval is above zero. <b>Cross-platform lag.</b> Per creator we build daily series of Instagram posts and YouTube comments "
      "over 365 days and test whether Instagram posts lagged one to three days improve the prediction of YouTube comments beyond their own lags (pooled "
      "Granger F test [27]), against a placebo with shuffled timing. <b>Negative spillover.</b> A creator's bad audience moment is a video whose comment "
      "mood falls well below their usual; we test linked creators' engagement after it. <b>Power and hybrid simulation.</b> On the final run's real "
      "inputs we remove the real estimate, plant a known effect and rerun GAIL-R, to measure how often it detects effects of a given size; these "
      "studies are method validation only.", "paste"),

    P("5. Results (Section V): replace V.A.3 and Table IV, add new tables and figures", "h1"),
    P("5a. New table: spillover tests on the creator network", "h2"),
    table([["Test", "Effect (log), 95% interval", "Verdict"],
           ["Tag: tagged creator, 7 days (291 events)", "+0.095 [+0.005, +0.185]; placebo -0.010", "Detected, secondary test of its plan (about +10%)"],
           ["Joint video: small featured creators (&lt;100k), 14 days (67 events)", "+0.277 [+0.113, +0.529]; placebo +0.118 [-0.001, +0.204]", "Detected, secondary (about +32%)"],
           ["Cross-platform, same creator: Instagram posts -> YouTube comments (105 creators)", "F 1.559 vs placebo 1.016, p = 0.002", "Detected"],
           ["Reverse: YouTube comments -> Instagram posts", "F 1.561 vs placebo 1.013, p = 0.014", "Detected"],
           ["Bad audience moment -> small linked creators (417)", "+0.108 [+0.018, +0.199]", "Rises (secondary)"],
           ["Bad audience moment -> all linked creators (1,794)", "+0.008 [-0.033, +0.050]", "No harm detected"],
           ["Paid sponsorship -> collaborators, GAIL-R (14 Nov)", "-0.090 [-0.203, +0.074]", "Not detected; above about +8% ruled out"],
           ["GAIL-R final, small creators (187 exposed)", "+0.129 [-0.100, +0.378]", "Positive, not significant"],
           ["GAIL-R final, all creators (924 exposed)", "+0.018 [-0.062, +0.089]; placebo DiD +0.022", "Positive, not significant"]],
          [72 * mm, 62 * mm, 36 * mm]),
    P("Sources: AUDIENCE_FLOW_RESULTS_8NOV.md (l.128, 164), models/cross_promotion_mechanism_10nov.json, NEGATIVE_SPILLOVER_PLAN_14NOV.md (result), "
      "GAIL_R_RESULTS_15NOV.md (sections 1 and 9), SPILLOVER_RESULTS_OVERALL_22NOV.md.", "small"),
    figure(figs["forest"], "New Fig. 3 (replaces the old Fig. 3): spillover tests on the creator network with 95% intervals. Green: detected; amber: "
           "GAIL-R final run, positive but not significant; grey: not detected and the placebo check. File: exports/paper_figures_23nov/fig_spillover_forest.png"),
    figure(figs["granger"], "New figure: cross-platform lag for the same creator. Real timing beats shuffled timing in both directions. "
           "File: fig_cross_platform_granger_105.png", w=140),
    P("5b. New subsection: \"Why GAIL-R is not yet significant: power and hybrid simulation\"", "h2"),
    P("Suggested text:", "p"),
    P("From the final run's intervals (standard error 0.0385 for all creators, 0.1220 for the 187 small creators), GAIL-R detects a true effect 80% of "
      "the time from about +11% for all creators but only from about +41% for small creators (Fig. X). The real small-creator estimate (+12.9%) and the "
      "simple joint-video result (+27.7%) both lie below that threshold. In a hybrid simulation on the real inputs with a planted effect, GAIL-R raised "
      "no false alarm at 0% (0/40) and its estimates rose with the planted effect, but at the real sample it detected a +60% effect in only 13 of 40 "
      "studies. With two times more small creators a +30% effect was detected in 8 of 10 studies, and with eight times more a +13% effect in 9 of 10. "
      "GAIL-R's non-significance on real data therefore reflects sample size, not a failure of the method.", "paste"),
    figure(figs["power"], "New figure: chance GAIL-R detects a true spillover of a given size at the final run's sample (normal approximation from "
           "its 95% intervals). File: fig_gailr_power.png", w=130),
    figure(figs["hybrid"], "New figure (SIMULATED, method validation only): hybrid simulation with planted spillover on the real inputs. A: at the real "
           "187 small creators. B: with 2x, 4x and 8x small creators. File: fig_hybrid_detection.png"),
    P("Caveats to state with it (GAIL_R_RESULTS_15NOV.md section 12): estimates lean slightly upward (about +0.03 to +0.07, +0.071 at 0%); the "
      "false-alarm check at 8x gave 1/10; extra creators are resampled copies of real ones.", "small"),

    P("6. Ranking section (IV.B.4)", "h1"),
    B("<i>s<sub>fit</sub></i>: say exactly how it is built: cosine similarity between the brief's CLIP-text and BERT embeddings and the creator's CLIP "
      "image (thumbnails), CLIP text and BERT text embeddings; each similarity is turned into a percentile rank among creators before averaging, then "
      "combined 70% relevance and 30% engagement/reach. Measured: AUC about 0.85 for fitness briefs (already in V.A.4)."),
    B("Add one sentence: <i>\"GAIL's network score (each creator's percentile among graph-connected creators) is reported alongside the ranking; its "
      "weight in Eq. (5) is zero until GAIL-R's estimate is significant.\"</i>"),
    B("Optional system paragraph: the dashboard now shows a live matching animation, a GAIL network-reach chart, a YouTube vs Instagram comparison, a "
      "content map (CLIP + BERT, PCA) and a campaign simulator. One screenshot can replace a paragraph if space allows."),

    P("7. Discussion (V.B, last paragraph) and Conclusion (VI): rewrite", "h1"),
    P("Replace <i>\"On the creator network GAIL-R shows that sponsoring a fitness creator raises their collaborators' engagement by at most about 3% ... "
      "pay for a creator's own audience\"</i> with:", "p"),
    P("On the creator network, spillover appears through collaborations rather than paid posts: a tagged creator gains about 10% engagement in the "
      "following week, and small creators featured in a joint video gain about 32% over two weeks, in line with Koch et al. [9], who found short-lived "
      "collaboration gains, and Ji et al. [10], who found spillover mainly among micro-influencers. Paid sponsorship onto collaborators is small: an "
      "effect above about 8% is ruled out. For a brand, the practical reading is that a creator's own audience carries most of the value of a paid post, "
      "while collaborations with small creators bring extra reach. GAIL-R points the same way (small creators +12.9%) but, at 187 exposed small "
      "creators, cannot yet separate this from zero; our simulations show it would with two to eight times more collaborations.", "paste"),
    P("Conclusion: replace the sentence <i>\"it bounds the spillover of a sponsorship onto collaborators below about 3% of engagement\"</i> with <i>\"it "
      "is validated on planted and published spillover, and on our network collaboration spillover is detected by pre-registered tests while GAIL-R's "
      "own estimate is positive but under-powered\"</i>. Future work: more small-creator collaborations (the forward tests are still collecting: 9 and 2 "
      "events of the 20 required), wider Instagram coverage, and sales data to fit the fusion weights, including GAIL's.", "p"),

    P("8. Limitations (V.C): add", "h1"),
    B("About 25 spillover tests were run. Both detected collaboration results were secondary tests of their plans (the primary audience-flow "
      "and all-creator tests were not detected); the joint-video subgroup (67 events) has its own placebo only just including zero, and net of that "
      "placebo drift the gain is about +17%."),
    B("The tag result was not repeated on new pairs (12 Nov: -0.115 [-0.339, +0.122], wide) and was positive but not significant in the older period "
      "(+0.050 [-0.006, +0.107])."),
    B("Granger tests show prediction, not cause; the cross-platform link is consistent with audiences following creators, or with a shared posting "
      "rhythm (explicit cross-promotion in captions does not explain it)."),
    B("The hybrid simulation resamples real creators and leans slightly upward; it validates the method and is never used as evidence of spillover."),

    P("9. Figures and tables: checklist", "h1"),
    table([["Item", "Action"],
           ["Abstract", "Replace (section 1 above)"],
           ["Table I", "Update counts (section 3)"],
           ["Table IV", "Replace with the new spillover table (5a)"],
           ["Fig. 3", "Replace with fig_spillover_forest.png"],
           ["New figure", "fig_cross_platform_granger_105.png (cross-platform)"],
           ["New figure", "fig_gailr_power.png (power)"],
           ["New figure", "fig_hybrid_detection.png (simulated, label it)"],
           ["Tables II, III, V", "Keep (benchmark, field experiment, published models)"],
           ["Section V.A.3, V.B, VI", "Rewrite (sections 5 and 7)"],
           ["Limitations", "Add the four points (section 8)"]],
          [50 * mm, 120 * mm]),
    P("All four figures are in <b>exports/paper_figures_23nov/</b> (PNG, 220 dpi) in the repository. Full per-test detail: SPILLOVER_RESULTS_OVERALL_22NOV.md "
      "and GAIL_R_RESULTS_15NOV.md.", "p"),
]

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                        title="Paper changes for the final version", author="Capstone team")
doc.build(story)
print(f"wrote {OUT} and {len(figs)} figures in {FIG}")
