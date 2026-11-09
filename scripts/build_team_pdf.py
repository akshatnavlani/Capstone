"""Builds the whole-project guide for the four team members (1 Nov 2026): every part of the project in simple words, with small pieces of real code, the final work split, and the questions a panel is likely to ask.
Numbers are read from models/*.json and counted in the database on the day it is built; explanations and the split are written once.

    python scripts/build_team_pdf.py [--out exports/team_project_guide_1nov.pdf]
"""
import argparse
import html
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
ap.add_argument("--out", default=str(ROOT / "exports" / "team_project_guide_1nov.pdf"))
OUT = ap.parse_args().out
J = lambda n: json.loads((ROOT / "models" / n).read_text(encoding="utf-8"))  # noqa: E731

FD = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FD / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", str(FD / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", str(FD / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FD / "consola.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-Bold")

INK, MUTED, AMBER, TEAL, LINE = colors.HexColor("#14202b"), colors.HexColor("#5b6b7d"), colors.HexColor("#b97a00"), colors.HexColor("#0f8f80"), colors.HexColor("#d5dde5")
S = {
    "title": ParagraphStyle("title", fontName="Body-Bold", fontSize=26, leading=30, textColor=INK, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="Body", fontSize=11, leading=15, textColor=MUTED, spaceAfter=10),
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=16, leading=20, textColor=INK, spaceBefore=6, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=11.5, leading=15, textColor=AMBER, spaceBefore=8, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Body", fontSize=9.8, leading=14, textColor=INK, spaceAfter=5),
    "b": ParagraphStyle("b", fontName="Body", fontSize=9.8, leading=13.8, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=2.5),
    "c": ParagraphStyle("c", fontName="Body", fontSize=8.4, leading=10.8, textColor=INK),
    "ch": ParagraphStyle("ch", fontName="Body-Bold", fontSize=8.6, leading=11, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8, leading=10.2, textColor=INK, backColor=colors.HexColor("#eef2f6"), borderPadding=5, spaceAfter=8, leftIndent=4),
    "note": ParagraphStyle("note", fontName="Body-Italic", fontSize=8.8, leading=11.8, textColor=MUTED, spaceAfter=6),
    "q": ParagraphStyle("q", fontName="Body-Bold", fontSize=9.8, leading=13.4, textColor=INK, spaceBefore=5, spaceAfter=1),
    "a": ParagraphStyle("a", fontName="Body", fontSize=9.6, leading=13.4, textColor=INK, leftIndent=10, spaceAfter=3),
    "who": ParagraphStyle("who", fontName="Body-Italic", fontSize=8.6, leading=11.4, textColor=TEAL, spaceAfter=5),
}
story: list = []


def H1(t, new_page=True):
    if new_page:
        story.append(PageBreak())
    story.append(Paragraph(t, S["h1"]))


def H2(t): story.append(Paragraph(t, S["h2"]))
def P(t): story.append(Paragraph(t, S["p"]))
def N(t): story.append(Paragraph(t, S["note"]))
def WHO(t): story.append(Paragraph("Who: " + t, S["who"]))
def B(items): [story.append(Paragraph(i, S["b"], bulletText="•")) for i in items]
def CODE(t): story.append(Paragraph(html.escape(t).replace("\n", "<br/>").replace(" ", "&nbsp;"), S["code"]))


def QA(items):
    for q, a in items:
        story.append(KeepTogether([Paragraph("Q. " + q, S["q"]), Paragraph(a, S["a"])]))


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


# ---- numbers -----------------------------------------------------------------------------------------------------------------------------------
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

t8 = J("gail_training_summary_1nov.json")
power, multi, hold = J("power_analysis.json"), J("gail_r_multiseed.json"), J("gail_r_holdout.json")
pairs, lag, fat, promo = J("platform_pairs.json"), J("long_lag.json"), J("ad_fatigue.json"), J("promotion_behaviour.json")
evs, snap = J("spillover_event_study.json"), J("snapshot_lag.json")
ps, e45, hing, base = J("creator_passport.json")["summary"], J("e4_e5_results.json"), J("hinglish_check.json"), J("published_baselines_eesha.json")
b1, b0 = J("semisynth_new_graph_effect1.json"), J("semisynth_new_graph_effect0.json")
mrow = multi["runs"]["with placebo penalty (30)"]
ate = lambda block, key: st.mean(r["ate_error"] for r in block[key] if isinstance(r, dict) and r.get("ate_error") is not None)  # noqa: E731
exposed, controls = power["real_exposed"], power["real_controls"]
sr = ps["sponsored_response"]
ig_up = next(r for r in lag["results"] if r["name"].startswith("ig_to_uploads"))
detected_event = sum(1 for r in evs["results"] if r.get("detected_after_correction"))
f2 = lambda v: f"{v:+.2f}"  # noqa: E731
placebo_worst = max(ate(s, "GAIL-R + placebo") for s in (b1["clean"], b1["pretrend"], b0["clean"], b0["pretrend"]))

# ================================================================================================================================================
story.append(Spacer(1, 30 * mm))
story.append(Paragraph("The whole project, in simple words", S["title"]))
story.append(Paragraph("Influencer-Brand Matching with Graph Spillover · UE23CS441A Project 011 · Review on 2 November 2026", S["sub"]))
story.append(Paragraph("Guide for Shimona, Eesha, Akshat and Abhyudyay. Read it once, front to back, and you can answer a panel on any part of it, not only your own.", S["sub"]))
story.append(Spacer(1, 6 * mm))
T(["Part", "What it covers"], [
    ["1", "The project in one minute"],
    ["2", "How the pieces fit together"],
    ["3", "Data: where it comes from and what we hold"],
    ["4", "Sponsorship labels, and the standing-affiliate-code fix"],
    ["5", "The graph"],
    ["6", "The big question: spillover, and how we test it"],
    ["7", "GAIL v1 and GAIL-R (the models), training and the simulations"],
    ["8", "The mood branch: comments, sentiment, Hinglish"],
    ["9", "Creator features and the fusion score"],
    ["10", "The novelties (what is new in our work)"],
    ["11", "Backend, Docker, tests"],
    ["12", "The app (frontend)"],
    ["13", "Results on one page, and what we do not claim"],
    ["14", "Who did what (final split)"],
    ["15", "Questions the panel may ask, with answers"],
    ["16", "Glossary"],
], [18, 150])
N("Numbers in this guide are read from the result files in models/ and counted in the database on the day it was built (1 Nov 2026). If any number changes after a rerun, rebuild with scripts/build_team_pdf.py.")

# ---- 1 ---------------------------------------------------------------------------------------------------------------------------------------
H1("1. The project in one minute")
P("<b>The problem.</b> A brand wants an influencer. Today it picks by follower count, which says nothing about who is safe, who fits the product, or how sure anyone is. "
  "We built a system that takes a brief (product, budget) and ranks creators with a score, a range (how sure we are), a grade (how much evidence we have) and warnings.")
P("<b>The research question.</b> When a brand sponsors creator A, does it also change the engagement of creators linked to A (their collaborators)? That knock-on effect is called <b>spillover</b>. "
  "Our model for it is <b>GAIL</b>, which works on a graph of creators.")
P("<b>The honest answer.</b> With the data we have, we find <b>no detectable spillover</b>. We can rule out large effects (about 1.5 times the size we could detect or more), but not tiny ones. "
  "So the app shows spillover as context and does not put it into the score. This is a result, not a failure, and we tested it from many angles to make sure it is not a mistake of ours.")
P("<b>What else we built.</b> A pipeline that collects YouTube and Instagram data daily; a rule-based sponsorship labeller; a comment-mood branch; creator features from images and text; a fusion score; a Creator Passport that puts both platforms on one page; and a website with an evidence room.")
B([
    f"Data: {n['creators']} creators, {n['videos']:,} YouTube videos, {n['comments']:,} comments, {n['ig_posts']:,} Instagram posts, {n['sponsored']:,} sponsored videos.",
    f"Spillover: GAIL-R {f2(t8['gail_r']['effect_on_exposed'])} (95% {f2(t8['gail_r']['ci95'][0])} to {f2(t8['gail_r']['ci95'][1])}) on {exposed} exposed observations: no detectable effect.",
    "Score: spillover weight 0, mood 0.5, creator features 0.5, shown with a range and an evidence grade A to D.",
])

# ---- 2 ---------------------------------------------------------------------------------------------------------------------------------------
H1("2. How the pieces fit together")
P("Think of a factory line. Raw material (posts and comments) comes in at one end and a ranked list comes out at the other. Each stage has one job.")
T(["Stage", "Job", "Where in the code"], [
    ["1. Collect", "Pull posts, comments and growth readings from YouTube, Instagram and Reddit into the database (daily, hourly readings every 2 hours)", "scripts/ingestion/"],
    ["2. Label", "Decide which posts are sponsored, and for which brand (rules in six evidence tiers)", "backend/app/labeling.py, scripts/ingestion/"],
    ["3. Build the graph", "Creators are dots; collaboration, shared-brand and co-occurrence links are lines", "ml/schema.py, creator_related_accounts, ml/link_evidence.py"],
    ["4. Measure spillover", "Compare creators whose neighbour was just sponsored with creators whose neighbour was not (GAIL, GAIL-R, matched tests, event study)", "ml/gail_r.py, ml/placebo.py, ml/temporal/"],
    ["5. Read the mood", "Score comment sentiment, look for risk that travels along links", "ml/temporal/sentiment.py, propagation.py"],
    ["6. Describe the creator", "Match the brief to the creator's images and text (CLIP and BERT)", "backend/app/creator_features.py"],
    ["7. Fuse", "Combine the branches into one 0 to 100 score with a range and a grade", "backend/app/fusion.py"],
    ["8. Serve", "API for the app (FastAPI) and the Creator Passport", "backend/app/routers/"],
    ["9. Show", "Website: brief, ranked list, passport, evidence room, graph", "frontend/src/app/"],
], [28, 90, 60])
P("<b>Technology in one line each.</b> Database: Postgres on Supabase. Backend: Python, FastAPI, SQLModel. Models: PyTorch and PyTorch Geometric. Sentiment: Hugging Face transformers. Frontend: Next.js 16 with Tailwind and hand-drawn SVG charts. Packaging: Docker.")
P("<b>A brief travelling through the system.</b> The brand types a product and a budget. The backend finds creators, asks the three branches for a score each (spillover context, mood, features), fuses them with the weights, adds the range and grade, and returns a ranked list. "
  "The app then shows each creator's Passport strip and flags a clash if the creator promoted a competitor recently.")

# ---- 3 ---------------------------------------------------------------------------------------------------------------------------------------
H1("3. Data: where it comes from and what we hold")
T(["What", "Count", "How it arrives"], [
    ["Creators", f"{n['creators']}", "Chosen fitness, health and lifestyle creators (about 150 tracked closely; the rest are neighbours found through links)"],
    ["YouTube videos", f"{n['videos']:,}", "YouTube Data API, history backfilled about 24 months, then daily"],
    ["YouTube comments", f"{n['comments']:,}", "Same API, sampled per video (quota limited)"],
    ["Instagram posts", f"{n['ig_posts']:,} ({n['ig_creators']} creators)", "Daily job that opens each profile page in Chrome through the OpenCLI tool; capped at about 130 page loads a day, so it is thin"],
    ["Growth readings", "every 2 hours since 11 Oct", "A timer job reads view and like counts; this is what lets us see changes hour by hour around a sponsorship"],
    ["Sponsorship events", f"{n['events']:,}", "Made by the labeller (next part)"],
], [34, 36, 108])
B([
    "<b>Why daily and hourly?</b> To see spillover you must see engagement <i>before</i> and <i>after</i> a sponsorship. Hourly readings catch the days right around it.",
    "<b>Limit 1: Instagram is thin.</b> A hard daily page-load cap means few posts per creator. Any Instagram result is reported with that warning.",
    "<b>Limit 2: no brand-side outcome.</b> We have no sales or conversions, only public engagement. So we never claim a creator will sell more.",
    "<b>Limit 3: the data is small for causal work.</b> Few creators have both a sponsor-linked neighbour and enough posts around it. That is why the result is a bounded null rather than a firm yes or no.",
])
WHO("Shimona (data fixing, re-collection, labels); Akshat (data collection through OpenCLI, ingestion, database).")

# ---- 4 ---------------------------------------------------------------------------------------------------------------------------------------
H1("4. Sponsorship labels, and the standing-affiliate-code fix")
P("To measure sponsorship we first have to know which posts <i>are</i> sponsored. We use rules, strongest evidence first:")
T(["Tier", "Evidence", "Strength"], [
    ["1", "Official paid-partnership label (Instagram) or YouTube's own paid-promotion tag", "Strongest"],
    ["2", "Spoken sponsor (the creator says 'brought to you by...' in a short video, found by a scan)", "Strong"],
    ["3", "Creator's own comment naming the sponsor", "Strong"],
    ["4", "Disclosure tag such as #ad or #sponsored", "Strong"],
    ["5", "Brand name and a promo code in the description", "Weak"],
    ["6", "Brand name only in the description", "Weakest"],
], [14, 130, 34])
P("<i>Organic</i> in our data means <i>not detected as sponsored</i>. We cannot prove a post is organic. About 81% of events at one point were the two weak tiers, which is why we protect against them (below).")
H2("The problem we found on 1 November")
P("Some creators paste the same brand-and-code block under <b>every</b> video (for example a gym-wear code). Our rule read each of those as a new sponsored post. One creator had 308 of 312 videos flagged. "
  "A standing deal is not a new sponsorship, and it distorted the control group. We un-flagged 470 videos of 17 creators (3,370 to 2,900 sponsored videos).")
CODE("""WINDOW_DAYS = 30        # look 30 days either side
MIN_WINDOW = 6          # need at least 6 videos in that window
STANDING_SHARE = 0.5    # brand in at least half of them => standing
MIN_LIST_BRANDS = 3     # 3+ brands with codes => a code list, not one ad
WEAK = ("brand_and_code", "brand_mention")   # only weak tiers are ever touched""")
P("A video is un-flagged only if it is weak evidence, its title does not name the brand, and either the brand is in at least half of the creator's videos within 30 days, or the video lists three or more codes. "
  "Real labels, spoken sponsors and hashtags are never touched. The script backs up first and has <font name='Mono'>--undo</font>.")
P("<b>What changed after the fix.</b> Exposed observations went from 60 to 74 and comparison observations from 406 to 249, because many false 'sponsored' neighbours left the comparison group. The result stayed a null, with a narrower picture.")
WHO("Shimona (labels and the fix).")

# ---- 5 ---------------------------------------------------------------------------------------------------------------------------------------
H1("5. The graph")
P("A <b>graph</b> is dots (creators) and lines (links). Spillover is about effects travelling along lines, so we need to decide which lines are real. We use several kinds of link, called <b>relations</b>:")
T(["Relation", "Meaning", "Strength of evidence"], [
    ["collaborates_with", "The creators appear together (tagged, mentioned, @-mentioned in a sponsored post, listed as a related account)", "Strongest"],
    ["co_occurs_with", "Appear in the same videos or posts", "Medium"],
    ["shared brand", "Both promoted the same brand", "Weaker (could be the brand, not the link)"],
    ["mentions", "One names the other", "Medium"],
], [36, 100, 42])
P("A <b>training pair</b> is one (sponsorship event, neighbour) combination where the neighbour has activity both before and after the event. Without a before and an after, the effect cannot be measured. This is the single agreed definition of 'pair' used everywhere (scripts/ingestion/pair_count.py):")
CODE("""1. EVENT     a dated sponsored post by creator A, on any platform
2. EDGE      A and neighbour B are linked by a collaboration edge to a DIFFERENT creator we track
3. STRADDLE  B has activity strictly BEFORE and strictly AFTER the event date (all platforms)""")
P("<b>Exposed</b> means the neighbour had a sponsorship in the window just before the observation; <b>comparison (control)</b> means no linked creator was sponsored. The aim is to compare the two groups, after removing differences we can see.")
B([
    "<b>Schema</b> (node and edge types, what a creator node carries): ml/schema.py and GRAPH_SCHEMA.md.",
    "<b>Edges in the database:</b> scripts/ingestion/collab_edges.py and populate_edges.py write the creator-to-creator links.",
    "<b>Link evidence:</b> ml/link_evidence.py and scripts/audit_creator_links.py check which links are supported before risk or effects travel along them.",
    "<b>Inside the model:</b> ml/multi_relation_exposure.py gives each relation its own exposure and its own slope.",
    "<b>In the app:</b> frontend/src/components/CreatorGraph.tsx draws the graph with a force layout.",
])
WHO("Akshat (schema and edges in the database); Shimona (link evidence and audit); Eesha (graph inside the model); Abhyudyay (graph in the app and its checks).")

# ---- 6 ---------------------------------------------------------------------------------------------------------------------------------------
H1("6. The big question: spillover, and how we test it")
H2("6.1 Engagement lift (the thing we measure)")
P("<b>Lift</b> is how much a creator's engagement changed around a date: the median engagement after divided by the median before, on a log scale (so +0.69 is about double, 0 is no change). "
  "We use medians so one viral post does not decide the answer.")
H2("6.2 Why we cannot just compare")
P("If creators near a sponsored neighbour grew faster, that does not prove spillover: they might simply have been growing already, or share a season, a trend, or an audience. "
  "So every test below has a way to check that the method does not invent an effect.")
H2("6.3 The tests, from simplest to strongest")
T(["Test", "In simple words", "Result"], [
    ["Matched difference-in-differences (DiD)", "Match each exposed creator to a similar unexposed one. Compare the change in the exposed with the change in the matched. Category-matched: match within the same kind of creator.", f"category-matched {f2(t8['category_matched_did']['estimate'])} (SE {t8['category_matched_did']['se']:.2f}); plain {f2(t8['matched_did']['estimate'])}"],
    ["Placebo pre-trend DiD", "Run the same test on the period BEFORE the sponsorship, where there cannot be an effect. If it finds one, the groups were already diverging.", f"{f2(t8['placebo_pre_trend_did']['estimate'])} (SE {t8['placebo_pre_trend_did']['se']:.2f}): the plain method is confounded"],
    ["Event study on hourly readings", "Look at views hour by hour around a sponsored video of the neighbour, against a same-hour placebo and a known-to-work positive control.", f"{detected_event} of {len(evs['results'])} detected after correction"],
    ["Lag tests (Granger style)", "Does an Instagram post predict YouTube views in the next 0 to 12 or 12 to 24 hours?", f"smallest p {ig_up['smallest_p_after_event']} against the 0.0125 bar: not detected; the control is"],
    ["Held-out creators", "Does adding the spillover term help predict creators the model never saw?", f"median gain {100 * hold['gain_median']:.1f}% against {100 * hold['null_gain_median']:.1f}% for a wrong-window control: no help"],
    ["Power analysis", "Plant a fake effect into the real data and see how large it must be for us to notice it.", f"with {exposed} exposed, about 80% detection at roughly 1.5 times; with 19 only about 2.7 times"],
    ["Label-noise check", "Pretend some of the comparison group was really exposed and see if the answer moves.", "even at 30% mislabelled, the upper end stays below a 1.3 times effect"],
], [38, 82, 58])
P("<b>Bonferroni 0.0125</b> is a stricter bar for p-values (0.05 divided by 4 tests) so that running several tests does not give a lucky 'detection'.")
P("<b>Placebo, once more, because it is the key idea.</b> A sponsorship cannot cause something that happened before it. So we move the event date back by one full window and run the same test. "
  "Any 'effect' found there is fake. We use that in two ways: as a check on the real data, and as a penalty during training (part 7).")
CODE("""def placebo_anchor(event_date, window_days):
    # event moved back so both windows end the day before the event
    return event_date - timedelta(days=window_days + 1)""")
P("<b>How to say the result.</b> Large spillover is ruled out. A small spillover cannot be seen with this many exposed observations. This is a bounded null, and it is a real, honest finding.")
WHO("Eesha (causal inference, real-data causal and placebo fixes, spillover modelling); Shimona (spillover analyses: event study, lag, power); Akshat (placebo implementation).")

# ---- 7 ---------------------------------------------------------------------------------------------------------------------------------------
H1("7. GAIL v1 and GAIL-R (the models)")
H2("7.1 GAIL v1")
P("GAIL v1 is a graph neural network. For each creator it looks at the sponsored neighbours around them, weights those neighbours with <b>attention</b> (the network learns which links matter), "
  "turns that into an <b>exposure</b> number, and a small network (MLP) predicts the change in engagement from the exposure and the creator's own features. It is trained for 100 epochs with a loss that includes a causal-regularisation term.")
P(f"Run 8 (1 Nov, corrected labels): {t8['training']['epochs']} epochs on {t8['training']['observations']} observations; error {t8['training']['mse_trained']:.4f} against {t8['training']['mse_baseline_always_zero']:.4f} for always predicting zero ({t8['training']['improvement_percent']}% better). "
  "This is <i>in-sample</i> (on the data it trained on), so it does not prove it will work on new creators.")
H2("7.2 GAIL-R, the improved version")
P("GAIL-R fixes a weakness of v1: a flexible network can fit patterns that are not causal. It works in two stages, like a careful experiment:")
B([
    "<b>Stage 1: predict the normal.</b> Predict each creator's engagement without spillover, and predict how exposed they would normally be. Done on one part of the data and applied to another (<b>cross-fitting</b>), so the model cannot memorise.",
    "<b>Stage 2: explain what is left.</b> Take the leftover engagement (actual minus predicted) and ask whether it rises when exposure is higher than expected. One slope for each relation says how much effect travels along that kind of link.",
    "<b>Attention is shrunk towards equal weights</b>, so the model cannot tell a story from noise.",
    "<b>Placebo penalty:</b> the model is punished if its 'effect' also explains engagement change <i>before</i> the sponsorship.",
    "<b>Bootstrap over creators:</b> to get the 95% range we resample whole creators, so repeated observations of one creator do not make the answer look more certain.",
])
CODE("""y_res = obs.y - m_hat                  # engagement minus what we expected anyway
...
loss = (y_res - ((E - e_hat) * model.slopes).sum(1)).pow(2).mean()   # R-learner loss
loss = loss + shrink * (E - U).pow(2).mean()                         # keep attention near uniform
loss = loss + placebo_weight * placebo_penalty(gap[has_pre], obs.pre[has_pre])  # no 'effect' before the event""")
P(f"<b>Real-data result:</b> single fit {f2(t8['gail_r']['effect_on_exposed'])} (95% {f2(t8['gail_r']['ci95'][0])} to {f2(t8['gail_r']['ci95'][1])}); the average over ten random starts is {f2(mrow['att_mean'])} (the ten starts range {f2(min(mrow['att_by_seed']))} to {f2(max(mrow['att_by_seed']))}). Both mean no detectable effect.")
H2("7.3 How do we know GAIL-R works? A simulation with a known answer")
P("We take our real graph and plant a spillover effect we choose (or none), and optionally a trend that was already there. Then each method tries to recover it. The table is the average error, so lower is better.")
cols = [("effect 1.0, clean", b1["clean"]), ("effect 1.0, trend", b1["pretrend"]), ("no effect, clean", b0["clean"]), ("no effect, trend", b0["pretrend"])]
meth = [("Naive difference", "Naive difference"), ("GNN predictor (no causal training)", "GNN predictor (no causal training)"), ("Doubly robust, no graph", "DR, no graph"), ("GAIL v1", "GAIL v1 (current)"), ("GAIL-R", "GAIL-R"), ("GAIL-R + placebo", "GAIL-R + placebo")]
T(["Method"] + [c for c, _ in cols], [[m] + [f"{ate(b, k):.3f}" for _, b in cols] for m, k in meth], [56, 30, 30, 30, 32])
B([
    f"GAIL-R with the placebo penalty keeps its error at or below {placebo_worst:.3f} in all four settings. Without the penalty a pre-existing trend fools it (0.16). So the penalty is essential.",
    "A GNN with no causal training looks fine when there is no effect only because it predicts roughly nothing; it fails when there is one.",
    "<b>Honest limit:</b> this is a simulation on our graph. It shows the method behaves well when the truth is known, not that real influencers behave that way.",
])
H2("7.4 Published models we compared against")
T(["Method", "No trend", "Planted trend"], [[r["method"], f"{r['no_trend']:.3f}", f"{r['pre_trend']:.3f}"] for r in base["rows"]], [90, 40, 48])
N("Run by Eesha from the authors' code on the 390-creator graph, 3 replicates, per-creator error. Table B above used 10 replicates, so do not mix the two. Published figures from other papers are context only: different tasks and data.")
H2("7.5 Extensions E4 and E5 (simulated)")
B([
    "<b>E4, causal supervision for attention:</b> train the attention with the causal loss instead of plain prediction. In simulation it protects against confounding; learned attention itself is no better than equal weights.",
    "<b>E5, missed-label correction (MC-SIMEX):</b> some real sponsorships are missed by our rules. We deliberately drop more labels, watch the estimate drift, and extrapolate back to a world with no missed labels. On real data the average stays near zero after correction.",
])
H2("7.6 Training in practice")
B([
    "Training is slow on the laptop CPU (about 22 minutes in run 8). After the line 'Canonical computable pairs' it prints nothing for about 20 minutes, because it is running thousands of database queries. It is not stuck.",
    "Run heavy jobs one at a time. Running Docker's virtual machine and several jobs together once crashed the machine overnight.",
    "A GPU package (exports/gpu_package_31oct.zip) is ready for a longer run with 20 or more seeds and 1,000 bootstrap draws.",
    "The checkpoint currently installed in the app is Eesha's; the run-8 checkpoint is kept separately and not installed.",
])
WHO("Eesha (GAIL building: v1, GAIL-R, E1 to E10; training; published baselines and comparison); Akshat (GAIL implementation, spillover training); Shimona (v1 training and testing on the new data, run 8); Abhyudyay (GAIL tests).")
N("About the name: we found no published paper called GAIL. Do not cite one. The closest prior work is Wu and Yuan (2025); say 'our model, inspired by'.")

# ---- 8 ---------------------------------------------------------------------------------------------------------------------------------------
H1("8. The mood branch: comments, sentiment, Hinglish")
P("Each comment gets a probability of being positive, neutral or negative from a language model. A creator's <b>mood score</b> is the average of P(positive) + 0.5 x P(neutral), from 0 (hostile) to 1 (warm).")
B([
    "English comments: <font name='Mono'>cardiffnlp/twitter-roberta-base-sentiment-latest</font>. Hindi in Devanagari script: <font name='Mono'>cardiffnlp/twitter-xlm-roberta-base-sentiment</font> (it matched our labels much better: correlation +0.76 against +0.33).",
    f"<b>Hinglish</b> (Hindi written in English letters) is hard for these models. On 24 hand labels the check gave AUC {hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['auc_pos_vs_neg']:.2f}, correlation {hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['spearman']:.2f}. That is a rough check by one labeller. Say so.",
    "The other sentiment checks (40 comments per language) were labelled by an AI model, not a person. Say 'AI-labelled'.",
    "<b>Shrinkage:</b> a creator with few comments is pulled towards 0.5, so a handful of comments cannot make someone look very safe or very risky.",
    "<b>Risk propagation</b> (ml/temporal/propagation.py): if a creator's comments turn sharply negative, part of that risk is passed along <i>supported</i> links to neighbours. Only supported links carry risk.",
    "<b>Risk penalty in the score:</b> if the mood score is below 0.3, 10 points are subtracted from the final score.",
])
WHO("Shimona (sentiment, temporal branch, Hinglish check).")

# ---- 9 ---------------------------------------------------------------------------------------------------------------------------------------
H1("9. Creator features and the fusion score")
H2("9.1 Creator features (does the creator fit the brief?)")
P("Each creator has an image summary (CLIP) and text summaries (CLIP text and BERT). The brief is turned into the same kind of summary. The closer the two are (cosine similarity), the better the fit. "
  "We measured this fit: ranking quality (AUC) 0.85 for a fitness brief and 0.57 for a cricket brief, mean 0.71. That is useful but not strong, and the app says so by giving a wide range.")
H2("9.2 The fusion score (the final number)")
P("Fusion is a weighted average of three branches, each on a 0 to 1 scale, then multiplied by 100:")
CODE("""raw   = w1 * spillover + w2 * sentiment_risk + w3 * creator_feature
final = 100 * raw  (minus 10 if sentiment_risk < 0.3), kept between 0 and 100
weights now:  w1 = 0.0   w2 = 0.5   w3 = 0.5""")
B([
    "<b>Why spillover has weight 0.</b> It is a null on real data. A branch with no signal should not move the score. A simulation with a planted value confirmed that taking it out leaves the ranking unchanged when spillover carries no signal.",
    "<b>Weights are priors, not fitted.</b> No outcome data (sales) exists to fit them. We say so.",
    "<b>A branch that knows nothing is left out</b> and the others rescaled (effective_weights): a creator with no comments is not given a neutral 0.5 that pretends to be information.",
    "<b>The range:</b> each branch has its own 95% half-width and they combine in quadrature (square root of the sum of squares), assuming independent errors.",
    "<b>Evidence grade A to D:</b> points for how many branches have real data (spillover capped at one point). It tells a brand how well we know this creator, separately from the score.",
    "A local file <font name='Mono'>backend/.env</font> with old FUSION_WEIGHT values once overrode the config. Environment variables beat config.py, so check this on every laptop.",
])
WHO("Shimona (fusion score and weights); Akshat (fusion layer weights in the backend config); Abhyudyay (fusion tests).")

# ---- 10 --------------------------------------------------------------------------------------------------------------------------------------
H1("10. The novelties (what is new in our work)")
P("These are the parts that are ours. Each is stated with its strength and its limit so that a panel cannot catch us over-claiming.")
T(["Novelty", "In simple words", "Result", "Limit"], [
    ["Same creator on YouTube vs Instagram within 24 h", "Compare one creator's engagement on the two platforms for posts close in time, so the creator and moment are the same", f"{pairs['pairs']} pairs, {pairs['creators_with_pairs']} creators; raw gap {f2(pairs['median_difference'])}, placebo alone {f2(pairs['placebo']['median_difference_placebo'])}, adjusted {f2(pairs['median_difference_adjusted'])}", "Instagram is thin"],
    ["Lag between platforms", "Does a post on one platform predict views on the other soon after?", f"Instagram post to YouTube upload in 0 to 12 h (p {ig_up['smallest_p_after_event']}); 12 to 24 h not supported", "Prediction, not cause"],
    ["Sponsored response by platform", "Compare a sponsored post with the same creator's organic posts of the same format nearby in time", f"YouTube views {sr['youtube_views'].get('approx_percent', 0):+.1f}% ({sr['youtube_views'].get('ci95_percent', [0, 0])[0]:+.1f} to {sr['youtube_views'].get('ci95_percent', [0, 0])[1]:+.1f}), no clear penalty", "Few Instagram creators"],
    ["Missing-platform estimate", "Guess a creator's Instagram level from their YouTube features, with a range", f"rank agreement {ps['prediction']['spearman_full']:.2f} against {ps['prediction']['spearman_size_only']:.2f} for size alone ({ps['prediction']['n']} creators)", "About 3.4 times typical error; shown as a range"],
    ["Mood gap", "Is the audience warmer on one platform? Flagged only when it beats the worst-case error", f"{ps['mood_gap']['flagged']} of {ps['mood_gap']['creators_with_both']} flagged; {ps['mood_gap']['warmer_on_instagram']} warmer on Instagram", "Conservative on purpose"],
    ["Attention speed", "Share of the first week's views that arrive in the first 24 hours", f"median {100 * ps['speed']['median_share_first_24h']:.0f}% ({ps['speed']['videos']:,} videos)", "YouTube only"],
    ["Ad fatigue", "Do sponsored posts get weaker as a creator does more of them?", f"slope {fat['results'][0]['median_slope']:+.3f}: not detected", "Descriptive"],
    ["Disclosure and buying signals", "How many detected sponsored videos say so, and do comments show buying words more?", f"{100 * promo['disclosure']['share_disclosed_overall']:.0f}% disclosed; buying comments {promo['response']['median_ratio']:.1f} times higher on sponsored", "Buying signal is a keyword proxy"],
    ["Competitor-clash flag", "Warn if the creator promoted a competing brand recently", f"{ps['clash']['creators_with_recent_brand_posts']} creators promoted a brand in {ps['clash']['window_days']} days", "Idea is known; ours is an automatic warning"],
    ["Creator Passport and evidence grade", "One record per creator that gathers all of the above and states how well we know them", "Built and served by the API and shown in the app", "Descriptive"],
    ["Validation on the real graph", "Planted effect on the real graph with the placebo penalty, plus power analysis", "Part 7.3 and 6.3", "Simulation"],
], [34, 54, 54, 36])
H2("The Creator Passport in a little more detail")
B([
    "<b>Mood gap:</b> Instagram mood minus YouTube mood, flagged only if the gap is at least 0.10 and also larger than 1.96 times the worst-case error (0.5 divided by the square root of the comment count).",
    "<b>Sponsored response:</b> per creator, the median log difference between a sponsored post and organic posts of the same format within 45 days (YouTube) or 90 days (Instagram). Pooled over creators with a bootstrap. A fake-sponsored placebo shows what the method gives when nothing is going on.",
    "<b>Missing-platform estimate:</b> leave-one-out ridge regression, scored against a subscriber-only baseline.",
])
CODE("""def mood_gap(yt, n_yt, ig, n_ig):
    gap = ig - yt
    se = math.sqrt(0.25 / max(n_yt, 1) + 0.25 / max(n_ig, 1))   # worst case
    significant = abs(gap) >= MIN_GAP and abs(gap / se) >= 1.96""")
WHO("Shimona (cross-platform pairs, lag, mood gap, missing-platform estimate, attention speed, clash flag, fusion layer); Akshat (Creator Passport); Abhyudyay (ad fatigue and disclosure).")

# ---- 11 --------------------------------------------------------------------------------------------------------------------------------------
H1("11. Backend, Docker, tests")
H2("11.1 Backend (FastAPI)")
T(["Route group", "What it does"], [
    ["/health", "Is the server and database alive"],
    ["/ingestion/...", "Write creators, YouTube, Instagram and Reddit data (needs an API key)"],
    ["/labeling/run", "Run the sponsorship labeller"],
    ["/influencers/recommendations", "A brief in, a ranked creator list out (the main route)"],
    ["/scores/compute and /scores/{creator}", "Fusion score for a creator"],
    ["/spillover", "The what-if spillover tool (an assumption, labelled as one)"],
    ["/feature-store/...", "Creators, summary and the edge lists (collaborations, sponsorships, co-occurrence, shared brand, mentions)"],
    ["/passport/summary, /insights, /strip, /creators, /clash, /{creator}", "Creator Passport and the Insights page's data"],
    ["/platform-profiles, /alerts, /analysis", "Platform profiles, risk alerts, the Analysis tab"],
], [74, 104])
B([
    "Result files such as models/*.json are read by the backend with a modification-time cache, so a rerun shows up without a restart.",
    "<font name='Mono'>pool_pre_ping</font> and <font name='Mono'>pool_recycle</font> in database.py stop the first request after a quiet period from failing with a dead database connection.",
    "Write routes need an API key; the key is never shown in logs or documents.",
])
H2("11.2 Docker")
B([
    "One image for the backend (slim; ml/ and the checkpoint are not baked in, five result JSONs are copied) and one for the frontend, started with docker-compose.",
    "The backend has a health check. We fixed three problems: numpy was missing from requirements, the Python version, and a comment on a FROM line.",
    "Docker needs WSL 2 on Windows. Do not run it together with heavy training on this laptop.",
])
H2("11.3 Tests and the gate")
B([
    "At the last full run (1 Nov, after merging the branches): machine-learning tests 340, backend 142, ingestion 126, all passing, and the frontend production build passes.",
    "A gate script runs the tests, the build and 'canary' checks (the pair-count canary, a short-query canary) before a review.",
    "A test pins the fusion weights so a stale environment variable cannot silently change the score.",
    "Rule for results: a claim in the paper or deck must trace to a file in models/ or a database count.",
])
WHO("Shimona (backend endpoints, Docker setup); Akshat (backend API, Docker, health checks, build gate); Abhyudyay (all testing, re-runs).")

# ---- 12 --------------------------------------------------------------------------------------------------------------------------------------
H1("12. The app (frontend)")
P("Next.js 16 with Tailwind. It is a dark 'analytics console' style. All colours come from tokens in <font name='Mono'>globals.css</font>, so a new template is a change to one file. Charts are hand-drawn SVG, so they work offline and need no library.")
T(["Page", "What a visitor does"], [
    ["Home", "Plays with a small network: click a creator to 'sponsor' them and watch an assumed effect fade over three hops (labelled as an illustration)"],
    ["Brief (brand-input)", "Enters product and budget"],
    ["Ranked creators (dashboard)", "Sees the score, range, evidence grade, clash warning and Passport strip for each creator"],
    ["Creator Passport", "One creator across both platforms: mood gap, response, speed, estimate, ad load, clash"],
    ["Evidence room (insights)", "Six interactive charts: the journey of the result, benchmark, power, passport findings, fusion simulation, extensions"],
    ["Graph and scores (explainability)", "The creator graph and how each score is built"],
    ["Analysis", "The analysis tabs (S1 to S8)"],
    ["Monitoring", "Alerts"],
], [46, 132])
B([
    "The spillover value is shown as <b>context, not scored</b>, in the app, so nobody mistakes it for part of the number.",
    "Everything simulated is labelled as simulated.",
])
WHO("Shimona (redesign, Insights page); Abhyudyay (frontend redesign and testing, graph implementation in the app); Akshat (backend API the app reads).")

# ---- 13 --------------------------------------------------------------------------------------------------------------------------------------
H1("13. Results on one page, and what we do not claim")
T(["Area", "Result"], [
    ["Data", f"{n['creators']} creators · {n['videos']:,} videos · {n['comments']:,} comments · {n['ig_posts']:,} Instagram posts · {n['sponsored']:,} sponsored videos"],
    ["Spillover, real data", f"GAIL-R {f2(t8['gail_r']['effect_on_exposed'])} (95% {f2(t8['gail_r']['ci95'][0])} to {f2(t8['gail_r']['ci95'][1])}), ten-seed mean {f2(mrow['att_mean'])}; category-matched DiD {f2(t8['category_matched_did']['estimate'])}; placebo DiD {f2(t8['placebo_pre_trend_did']['estimate'])}"],
    ["Interpretation", "Large spillover ruled out; small spillover cannot be seen with 74 exposed observations"],
    ["GAIL training (run 8)", f"error {t8['training']['mse_trained']:.4f} against {t8['training']['mse_baseline_always_zero']:.4f} for always-zero (in-sample)"],
    ["Method validation", f"GAIL-R with placebo penalty error at most {placebo_worst:.3f} in the simulation; naive and plain GNN fail"],
    ["Score", "Weights 0 / 0.5 / 0.5, with a range and grade A to D"],
], [40, 138])
H2("What we do not claim")
B([
    "That our ranking predicts brand outcomes better than any published system. No sales data exists.",
    "That our numbers beat any published figure. Different tasks and data; published figures are context.",
    "That GAIL-R is a brand-new estimator. The new parts are the placebo penalty, the validation on the real graph, the power analysis and the application.",
    "That spillover exists. We find none, and rule out large effects only.",
    "That the simulations hold for real influencers, or that the clash flag is a new idea.",
    "That the Hinglish check is strong: it is 24 labels by one person.",
])
H2("Known weak spots (say them before the panel does)")
B([
    "Instagram is thin because of the daily page-load cap.",
    "Sponsorship labels are rules, not ground truth; weak tiers can be wrong (the standing-code fix removed 470).",
    "The model is trained on few exposed observations, so the interval is wide.",
    "Table B (10 replicates) and Table B2 (3 replicates, other models) are on the 390-creator graph and should not be mixed.",
    "The source of the name GAIL is unknown; the 'forty percent better' figure has no source and must not be quoted.",
])

# ---- 14 --------------------------------------------------------------------------------------------------------------------------------------
H1("14. Who did what (final split)")
T(["Shimona", "Eesha", "Akshat", "Abhyudyay"], [[
    "• Data fixing, re-collection and sponsorship labels<br/>• Link evidence and graph view (cross-platform link audit, mined collaborator links, creator graph in the app)<br/>• Spillover analyses (event study, lag, power)<br/>• Temporal and cross-platform novelties: pairs, lag, mood gap, missing-platform estimate, attention speed, clash flag and fusion layer<br/>• Frontend: redesign and Insights page<br/>• Backend endpoints<br/>• Docker setup<br/>• GAIL v1 training and testing on the new data",
    "• GAIL building: GAIL v1, GAIL-R, E1 to E10<br/>• Graph inside the model: multi-relation exposure, per-relation attention<br/>• GAIL training<br/>• Causal inference: real-data causal and placebo fixes<br/>• Spillover modelling<br/>• Published baselines (TNet, DeepInf, INFLECT-DGNN) and the comparison study between models and our model's performance<br/>• Paper",
    "• Graph schema and creator-to-creator edges: implementation of graph edges in the database<br/>• GAIL implementation and spillover training<br/>• Placebo implementation<br/>• Data collection: Instagram scraping through OpenCLI, ingestion, database<br/>• Backend API<br/>• Docker, health checks, build gate<br/>• Novelty: Creator Passport<br/>• Fusion layer weights",
    "• All testing: GAIL, API, fusion, Passport<br/>• Graph checks: edge counts, link audit re-runs, graph view testing<br/>• Re-runs of results to check they match<br/>• Frontend redesign and testing<br/>• Novelty: ad fatigue and disclosure<br/>• Graph implementation in the app",
]], [44, 44, 46, 44], zebra=False)
P("<b>If a panel member asks you about someone else's part,</b> answer in one sentence from this guide and say who built it. Everyone should be able to say what each part is and why it exists; the owner answers the details.")

# ---- 15 --------------------------------------------------------------------------------------------------------------------------------------
H1("15. Questions the panel may ask, with answers")
H2("The idea and the result")
QA([
    ("What is the project in one sentence?", "A system that ranks influencers for a brand with a score, an honest range and an evidence grade, and tests whether a sponsorship spills over to linked creators."),
    ("What is spillover?", "The change in engagement of creators linked to a sponsored creator, caused by that sponsorship."),
    ("Did you find spillover?", "No. GAIL-R gives about zero with a range of -0.55 to +0.33 on 74 exposed observations. Large effects are ruled out; small ones cannot be seen with this data."),
    ("Isn't a null result a failure?", "No. We show why it is a bounded null: the power analysis says what size we could have seen, several independent tests agree, and our method recovers planted effects in simulation. A tested null is a finding."),
    ("Why not make the spillover look positive, since that is what a brand wants?", "Because it would be false, and the score would then rank creators on noise. We removed spillover from the score instead and show it as context."),
    ("So what does your system actually add?", "Honest ranking with ranges and grades; a cross-platform Creator Passport; a clash warning; and a validated test for spillover that other work can reuse."),
])
H2("Data and labels")
QA([
    ("How do you know a post is sponsored?", "Rules in six tiers: official labels, spoken sponsors, creator comments, hashtags, brand and code, brand name. We checked samples by hand. Organic means not detected as sponsored."),
    ("Isn't a rule-based label noisy?", "Yes, especially the weak tiers. We found and fixed the standing-affiliate-code case (470 videos) and tested how sensitive the result is to label noise (E5 and the noise table): the answer does not change."),
    ("Why is Instagram thin?", "A page-load cap of about 130 a day through the browser tool. Instagram results are reported with that warning."),
    ("Why not buy a data feed?", "Not available within the project; we used public data only."),
])
H2("Models and method")
QA([
    ("What is GAIL?", "Our graph model for spillover. The network learns which neighbours matter (attention), turns neighbour sponsorships into an exposure number, and predicts the engagement change. We found no published paper under this name; the closest is Wu and Yuan (2025)."),
    ("What is GAIL-R and why a second version?", "A two-stage, cross-fitted R-learner. It predicts the normal, then explains only the leftover with one slope per relation, with attention held close to equal and a placebo penalty. It fixes v1's tendency to fit non-causal patterns."),
    ("What is the placebo?", "A test on the period before the sponsorship, where no effect is possible. If the method finds an effect there, it is fooled by trends. We use it as a check and as a training penalty."),
    ("How do you know GAIL-R works?", f"We plant a known effect in the real graph. GAIL-R with the placebo penalty keeps its error at or below {placebo_worst:.3f} in all four settings, while the naive comparison and a plain GNN fail."),
    ("Why does your model's training error not prove anything?", "It is measured on the data it trained on. The held-out creator test shows the spillover term does not help on unseen creators."),
    ("What does 'cross-fitting' mean?", "Predict one part of the data using a model trained on the other part, so the model cannot just memorise answers."),
    ("What is difference-in-differences?", "Compare the change over time in exposed creators with the change in similar unexposed creators. The difference of the two changes is the effect."),
    ("Why a log ratio of medians for lift?", "Log ratios make a doubling and a halving symmetric, and medians stop one viral post deciding the answer."),
    ("Why bootstrap over creators and not observations?", "One creator appears in several observations. Resampling observations would make the answer look more certain than it is."),
    ("What is Bonferroni 0.0125?", "0.05 divided by 4 tests, so running several tests does not produce a lucky detection."),
])
H2("Score and product")
QA([
    ("How is the final score computed?", "0.5 times mood plus 0.5 times creator-fit, each on 0 to 1, times 100, minus 10 if mood is below 0.3. Spillover has weight 0. Each branch has its own range and they combine in quadrature."),
    ("Where do the weights come from?", "They are documented priors. No outcome data exists to fit them. A script shows how much the ranking moves if they change."),
    ("What does the evidence grade mean?", "How many branches have real data for this creator, from A (most) to D (least). It is separate from the score."),
    ("How accurate is the creator-fit part?", "Ranking quality (AUC) of 0.85 for a fitness brief and 0.57 for a cricket brief; the app shows a wide range for that reason."),
    ("What about Hindi and Hinglish?", "Devanagari goes to a multilingual model. Hinglish is checked on 24 hand labels (a rough check) and reported as a limit."),
    ("What is the clash flag? Is it new?", "It warns when a creator promoted a competing brand in the last 120 days. The idea is known in the literature; our contribution is the automatic warning in the ranking."),
])
H2("Engineering")
QA([
    ("How do you know the code works?", "Tests: machine learning 340, backend 142, ingestion 126, plus a gate script with canary checks and a production build for the frontend."),
    ("Can someone else run it?", "Yes: docker-compose starts the backend and frontend; the database address and API key come from a local .env file that is never committed."),
    ("What would you do with more time or data?", "More Instagram coverage, a longer window (more exposed observations), real brand outcomes to fit the weights, a GPU run with more seeds, and ranking by expected engagement per rupee."),
    ("What did the team do?", "See part 14. In one line: Akshat the data pipeline and backend, Eesha the models and the paper, Shimona the analyses, novelties and app, Abhyudyay testing and the graph view."),
])

# ---- 16 --------------------------------------------------------------------------------------------------------------------------------------
H1("16. Glossary")
T(["Term", "Meaning in plain words"], [
    ["Spillover", "A sponsorship on one creator changing engagement of linked creators"],
    ["Exposed / comparison (control)", "A creator whose linked neighbour was just sponsored / one with no sponsored neighbour"],
    ["Engagement lift", "Log of the median engagement after divided by before"],
    ["Graph, node, edge, relation", "Dots (creators), lines (links), and the kind of line"],
    ["Attention", "The weight the network gives each neighbour"],
    ["Exposure", "How much of a creator's neighbourhood was just sponsored"],
    ["GNN", "Graph neural network: a model that passes information along edges"],
    ["MLP", "A small standard neural network"],
    ["R-learner", "Two-stage method: remove what is predictable, then explain what is left"],
    ["Cross-fitting", "Predict each part of the data with a model trained on the other part"],
    ["Placebo", "A test where no effect is possible, to check the method is not fooled"],
    ["Pre-trend", "A change that was already happening before the event"],
    ["DiD (difference-in-differences)", "Change in the treated minus change in the comparison"],
    ["Event study", "Look at the series around the event, hour by hour"],
    ["Granger / lag test", "Does one series help predict another a little later?"],
    ["Power", "The chance of noticing an effect of a given size if it exists"],
    ["Bootstrap", "Resample the data many times to get a range"],
    ["Confidence interval (95%)", "A range that would contain the true value 95 times in 100 if the method is right"],
    ["Bonferroni", "A stricter bar when running several tests"],
    ["MC-SIMEX", "Add more error on purpose, watch the estimate drift, and extrapolate back to no error"],
    ["Bounded null", "No effect found, with a limit on how large an effect could have gone unseen"],
    ["Fusion score", "The weighted combination of the branches into 0 to 100"],
    ["Evidence grade", "A to D: how much real data stands behind a creator's score"],
    ["Creator Passport", "One page per creator, both platforms, with mood, speed, estimate and clash"],
    ["CLIP / BERT", "Models that turn images and text into numbers so they can be compared"],
    ["Sentiment", "How positive or negative a comment is"],
    ["Hinglish", "Hindi written in English letters"],
    ["Canary", "A small automatic check that fails loudly if a key number changes"],
], [52, 126])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Body", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "The whole project in simple words · Project 011 · 1 November 2026")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


SimpleDocTemplate(OUT, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=18 * mm, title="The whole project in simple words", author="Team Project 011").build(story, onFirstPage=footer, onLaterPages=footer)
print("saved", OUT)
