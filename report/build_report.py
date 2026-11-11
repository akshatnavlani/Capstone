r"""Builds the Phase-3 report from the team's draft (ESA_Report_Capstone_final.docx) in the UE23CS441A template order (12 Nov 2026).

Keeps the draft's title page, certificate, declaration, acknowledgement and images; fixes them to the Phase-3 template wording;
rebuilds the body as Chapters 1-11 + References + Appendix with current numbers (database, 12 Nov 2026; result files in models/).

    python report\build_report.py      (system Python 3.12: python-docx)  then  report\finish_report.ps1 (Word: fields, PDF)
"""
import copy
import shutil
import sys
from pathlib import Path

import docx
import docx.table
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_lib import FONT, TEXT_W, Report, add_field, font  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"C:\Users\Shimona\Downloads\ESA_Report_Capstone_final.docx")
OUT = Path(r"C:\Users\Shimona\Downloads\ESA_Report_Capstone_updated.docx")
FIG = ROOT / "report" / "figures"
MEDIA = FIG / "from_draft"
ASSETS = ROOT / "presentation" / "assets"
TITLE = "Influencer-Brand Matching via GAIL & Graph Spillover"

# ------------------------------------------------------------------ images from the draft
MEDIA.mkdir(parents=True, exist_ok=True)
import zipfile  # noqa: E402

with zipfile.ZipFile(SRC) as z:
    for name, out in {"word/media/image15.jpg": "pes_logo.jpg", "word/media/image6.png": "schema_1.png", "word/media/image2.png": "schema_2.png",
                      "word/media/image8.png": "architecture_detailed.png", "word/media/image3.png": "degree_distribution.png",
                      "word/media/image16.png": "correlation_heatmap.png", "word/media/image13.png": "lag_plots.png",
                      "word/media/image1.png": "brand_safety_hist.png"}.items():
        (MEDIA / out).write_bytes(z.read(name))

doc = docx.Document(SRC)
body = doc.element.body
R = Report(doc)


def set_text(p, text):
    runs = p.runs
    if not runs:
        p.add_run(text)
        return
    runs[0].text = text
    for r in runs[1:]:
        r._r.getparent().remove(r._r)


def find_par(start):
    for p in doc.paragraphs:
        if p.text.strip().startswith(start):
            return p
    raise SystemExit(f"paragraph not found: {start!r}")


# ------------------------------------------------------------------ front matter (template Page 1-8 wording)
set_text(find_par("UE23CS320A"), "UE23CS441A – Capstone Project Phase - 3")
set_text(find_par("Aug-Dec 2025"), "Aug - Nov 2026")
set_text(find_par("‘Predictive Influencer-Brand Matching’"), f"‘{TITLE}’")
set_text(find_par("In partial fulfillment for the completion of"),
         "In partial fulfilment for the completion of seventh semester Capstone Project Phase - 3 (UE23CS441A) in the Program of Study - "
         "Bachelor of Technology in Computer Science and Engineering under rules and regulations of PES University, Bengaluru during the period "
         "Aug 2026 – Nov. 2026. It is certified that all corrections / suggestions indicated for internal assessment have been incorporated in the "
         "report. The dissertation has been approved as it satisfies the 7th semester academic requirements in respect of project work.")
set_text(find_par("We hereby declare"),
         f"We hereby declare that the Capstone Project Phase - 3 entitled “{TITLE}” has been carried out by us under the guidance of "
         "Dr. Vishnu S Tiwari, Professor and submitted in partial fulfilment of the course requirements for the award of degree of Bachelor of "
         "Technology in Computer Science and Engineering of PES University, Bengaluru during the academic semester Aug – Nov. 2026. The matter "
         "embodied in this report has not been submitted to any other university or institution for the award of any degree.")
ack = [find_par("I would like to express my gratitude"), find_par("I am grateful to all Capstone"), find_par("I take this opportunity"),
       find_par("I am deeply grateful")]
set_text(ack[0], "We would like to express our gratitude to Dr. Vishnu S Tiwari, Professor, Department of Computer Science and Engineering, PES "
                 "University, for the continuous guidance, assistance, and encouragement throughout the development of this UE23CS441A Capstone "
                 "Project Phase-3.")
set_text(ack[1], "We are grateful to the Capstone Project Coordinator, Dr. Vandana M. Ladwani, Associate Professor, Department of Computer Science "
                 "and Engineering, PES University for organizing, managing, and helping with the entire process.")
set_text(ack[2], "We take this opportunity to thank Dr. Sandesh B J, Chairperson, Department of Computer Science and Engineering, PES University, "
                 "for all the knowledge and support we have received from the department. We would like to thank Dr. Sridhar K S, Registrar, "
                 "PES University for his help.")
set_text(ack[3], "We are deeply grateful to Late Dr. M. R. Doreswamy, Founder, PES University, whose vision and dedication continue to inspire "
                 "generations of learners. We would like to express our sincere gratitude to Prof. Jawahar Doreswamy, Chancellor, PES University, "
                 "Dr. Suryaprasad J, Vice-Chancellor, PES University and Dr. Nagarjuna Sadineni, Pro Vice-Chancellor, PES University for providing "
                 "us various opportunities and enlightenment every step of the way. Finally, this project could not have been completed without "
                 "the continual support and encouragement we have received from our families and friends.")
abstract = find_par("Today, brands generally choose")
set_text(abstract,
         "Brands usually choose influencers by follower count, without measuring whether a sponsorship also reaches the audiences of connected "
         "creators or of the same creator on another platform. This project builds an end-to-end influencer–brand matching system for Indian "
         "fitness and health creators. Public YouTube, Instagram and Reddit data for 651 creators, including 184,251 videos and 2.3 million "
         "comments, is collected daily into a PostgreSQL database and modelled as a multi-relational creator graph. GAIL-R, a graph-based, "
         "cross-fitted causal learner with a placebo penalty, estimates spillover and achieved the lowest error on a planted-effect benchmark "
         "against DeepInf, TNet and INFLECT-DGNN. A mood branch scores comment sentiment in English and Hindi, and a creator-fit branch matches "
         "CLIP and BERT embeddings to the brand brief. A fusion layer returns a ranked 0–100 score with a range and an evidence grade through a "
         "FastAPI service and a Next.js dashboard. Pre-registered tests detected cross-platform audience spillover within creators (p = 0.002).")
for r in abstract.runs:
    r.font.size = Pt(14)
abstract.paragraph_format.line_spacing = 1.5
abstract.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

# names: one spelling everywhere (as on the Review-3 deck)
for t in doc.tables:
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    for wrong in ("Abhyuday Aggarwal", "Abhyudyay Agarwal", "Abhyuday Agarwal"):
                        if wrong in r.text:
                            r.text = r.text.replace(wrong, "Abhyudyay Agrawal")
# certificate: third signature (Registrar), copied from the Chairperson cell
for t in doc.tables:
    if len(t.columns) == 3 and "Dr. Sandesh B J" in t.cell(0, 1).text and "Sridhar" not in t.cell(0, 2).text:
        src, dst = t.cell(0, 1)._tc, t.cell(0, 2)._tc
        for p in dst.findall(qn("w:p")):
            dst.remove(p)
        for p in src.findall(qn("w:p")):
            dst.append(copy.deepcopy(p))
        for p in t.cell(0, 2).paragraphs:
            for r in p.runs:
                r.text = r.text.replace("Dr. Sandesh B J", "Dr. Sridhar K S").replace("Chairperson", "Registrar")

# front pages: each starts on a new page (the draft spaced them with blank lines for US Letter, which drift on A4)
def has_drawing(p):
    return bool(p._p.findall(".//" + qn("w:drawing")))


paras = doc.paragraphs
idx = {p.text.strip(): i for i, p in enumerate(paras) if p.text.strip() in ("CERTIFICATE", "DECLARATION", "ACKNOWLEDGEMENT", "ABSTRACT")}
anchors = []
cert = idx["CERTIFICATE"]
while not has_drawing(paras[cert]):
    cert -= 1
anchors.append(cert)
anchors += [idx["DECLARATION"], idx["ACKNOWLEDGEMENT"], idx["ABSTRACT"]]
for a in anchors:
    k = a - 1
    while k >= 0 and not paras[k].text.strip() and not has_drawing(paras[k]):
        paras[k]._p.getparent().remove(paras[k]._p)
        k -= 1
    paras[a].paragraph_format.page_break_before = True
    paras[a].paragraph_format.space_before = Pt(24)

# keep two draft tables (literature comparison, research gap); remove everything after the abstract
keep = {}
for t in doc.tables:
    first = t.cell(0, 0).text.strip()
    if first.startswith("Paper / Author"):
        keep["lit"] = t._tbl
    elif first.startswith("Research") and len(t.columns) == 6:
        keep["gap"] = t._tbl
after = False
for el in list(body.iterchildren()):
    if el is abstract._p:
        after = True
        continue
    if after and el.tag != qn("w:sectPr"):
        body.remove(el)

# page set-up (A4, 2 cm) and no header/footer on the front pages (template: they start from Chapter 1)
sec0 = doc.sections[0]
sec0.page_width, sec0.page_height = Cm(21.0), Cm(29.7)
sec0.left_margin = sec0.right_margin = sec0.top_margin = sec0.bottom_margin = Cm(2.0)
sec0.header_distance = sec0.footer_distance = Cm(1.0)
for ref in sec0._sectPr.findall(qn("w:headerReference")) + sec0._sectPr.findall(qn("w:footerReference")):
    sec0._sectPr.remove(ref)
tp = sec0._sectPr.find(qn("w:titlePg"))
if tp is not None:
    sec0._sectPr.remove(tp)


def front_title(text):
    p = doc.add_paragraph()
    p.paragraph_format.alignment, p.paragraph_format.space_after = WD_ALIGN_PARAGRAPH.CENTER, Pt(18)
    font(p.add_run(text), 16, bold=True)


R.page_break()
front_title("TABLE OF CONTENTS")
add_field(doc.add_paragraph(), 'TOC \\o "1-3" \\h \\z \\u', "Table of contents: update the field (Word: right-click > Update Field).")
R.page_break()
front_title("LIST OF FIGURES")
add_field(doc.add_paragraph(), 'TOC \\h \\z \\t "Figure Caption,1"', "List of figures: update the field.")
R.page_break()
front_title("LIST OF TABLES")
add_field(doc.add_paragraph(), 'TOC \\h \\z \\t "Table Caption,1"', "List of tables: update the field.")


def put_kept(name, size=9.5):
    p = doc.add_paragraph()
    p._p.addprevious(keep[name])
    p._p.getparent().remove(p._p)
    normal = next(s for s in doc.styles if s.style_id == "Normal")
    for row in docx.table.Table(keep[name], doc).rows:
        for cell in row.cells:
            for q in cell.paragraphs:
                q.style = normal   # the draft's cells used heading styles, which filled the table of contents
                q.paragraph_format.line_spacing, q.paragraph_format.space_after = 1.0, Pt(2)
                for r in q.runs:
                    font(r, size, color=None)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


# =========================================================================== CHAPTER 1
R.chapter("Introduction")
R.section("Background")
R.P("In the last ten years influencer marketing has grown rapidly, and the market is expected to be worth about $32.6 billion in 2026. "
    "Measuring the return a brand actually gets from its influencer partnerships is still difficult. A key reason is the way influencers are "
    "chosen: businesses rely on simple indicators such as the number of followers, the level of interaction and an overall sense of brand fit. "
    "None of these indicators show how a creator is positioned within the wider web of collaborators, communities and platforms around them.",
    "Attribution practice makes the problem worse. Single-touch attribution credits a sale to the last post a customer saw, and so it ignores "
    "indirect and delayed effects: a sponsorship can reach the audience of the creator's collaborators, or the creator's own audience on a "
    "second platform, days after the original post. This project moves from treating each creator as a single, independent entity to treating "
    "the creator ecosystem as a graph, in which creators are nodes and their collaborations, shared communities, mentions and sponsoring brands "
    "are typed edges. This mirrors the progress of many disciplines from simple heuristics to learned graph models that explain relationships "
    "better than the features of each node alone.")
R.section("Spillover in Creator Networks")
R.P("Spillover is the effect of an action on units other than the one that received it. In influencer marketing it appears in two forms. "
    "Between creators, a sponsorship of creator A may change the engagement of creator B because the two share an audience. Within a creator, "
    "a post on one platform may raise activity on the same creator's other platform, because followers move across platforms. Estimating "
    "spillover is a causal question, because brands do not choose creators at random: popular creators are sponsored more often and would "
    "receive more engagement anyway.",
    "Table 1.1 lists the three platforms used in this project and what each contributes to the graph, and Table 1.2 lists the relation types.")
R.table("Data sources and their role in graph construction", ["Platform", "Content collected", "Role in this project"], [
    ["YouTube", "Channels, long and short videos, comments with exact timestamps, subscriber readings", "Main engagement signal; collaborations and @mentions; sponsorship events; comment sentiment"],
    ["Instagram", "Profiles, posts and reels, captions, comments", "Cross-platform comparison of the same creator; @tags for collaborations; sponsorship labels"],
    ["Reddit", "Posts and comments that discuss creators", "Co-occurrence edges (creators discussed together); additional text for sentiment"]],
    [2.6, 6.6, 7.8])
R.table("Relation types in the creator graph", ["Relation", "Direction", "Meaning", "Source"], [
    ["collaborates_with", "creator - creator", "Creators who appeared in or tagged each other in content", "YouTube titles and descriptions, Instagram captions"],
    ["co_occurs_with", "creator - creator", "Creators discussed together in the same thread", "Reddit posts"],
    ["mentions", "creator -> creator", "@handle of another tracked creator", "YouTube and Instagram text"],
    ["shares_brand", "creator - creator", "Creators sponsored by the same brand", "Sponsorship events"],
    ["sponsors", "brand -> creator", "A disclosed or detected sponsorship", "Sponsorship detector (Chapter 8)"]],
    [3.2, 3.0, 5.8, 5.0])
R.section("Scope of the Project")
R.P("The project targets **Indian fitness and health creators** (fitness, sport, yoga, meditation, nutrition and health) on YouTube, "
    "Instagram and Reddit. On 12 November 2026 the database tracked 651 creators, of whom 512 are in this scope; 437 of the 512 have a "
    "verified Instagram handle. Only public data is read, collection is read-only, and every data change keeps a backup. The output is a "
    "ranked, explained list of creators for a brand brief (product, budget, region, audience and platform), served by a REST API and a web "
    "application. Real sales data is not available to the project, so effects are measured on public engagement: comments, views, likes and "
    "subscriber counts.")
R.section("Contributions")
R.bullets([
    "**A daily, multi-platform data pipeline** that has collected 184,251 YouTube videos, 2,296,861 YouTube comments, 3,286 Instagram posts, "
    "3,308 Reddit posts and 573,368 engagement readings into a PostgreSQL database on Azure.",
    "**A sponsorship detector with six evidence tiers**, from the platform's paid-partnership label to a brand mention, with an owner check and "
    "a standing-code correction; strong tiers were correct in 73 of 75 hand-checked events.",
    "**GAIL and GAIL-R**, graph models for spillover. GAIL-R, a cross-fitted R-learner with one effect per relation and a placebo penalty, had "
    "the lowest per-creator error on a planted-effect benchmark, ahead of DeepInf, TNet and INFLECT-DGNN.",
    "**A pre-registered spillover study**: every test was written down before the data was examined and run once. Cross-platform audience "
    "spillover within creators was detected (p = 0.002 and p = 0.014 for the two directions, 105 creators).",
    "**A complete application**: mood and creator-fit branches, a fusion layer with ranges and evidence grades, the Creator Passport, a graph "
    "explorer, monitoring alerts, and a tested FastAPI and Next.js code base with 642 automated tests."])
R.section("Organisation of the Report")
R.P("Chapter 2 defines the problem and objectives. Chapter 3 reviews related work and states the research gap. Chapter 4 gives the "
    "requirements specification, Chapters 5 and 6 the high-level and low-level designs, and Chapter 7 the detailed system design with its "
    "equations. Chapter 8 describes the methodology, Chapter 9 the implementation with pseudocode, and Chapter 10 the experiments and results. "
    "Chapter 11 concludes and outlines future work. A short user manual is given in Appendix A.")

# =========================================================================== CHAPTER 2
R.chapter("Problem Definition")
R.section("Problem Statement")
R.P("Develop an end-to-end system for influencer-brand matching that is not biased toward follower count or engagement volume as a proxy "
    "for influence, since these metrics mix popularity with genuine effect and ignore the network a creator sits within. The system should "
    "use a multi-relational graph of real collaboration, co-occurrence, mention and sponsorship data to estimate the spillover a sponsorship "
    "produces for a creator's network neighbours, corrected for selection bias so that the estimate reflects genuine influence rather than "
    "pre-existing popularity. It should account for the time-lagged and cross-platform nature of engagement, comparing a creator's YouTube and "
    "Instagram activity rather than treating each platform alone, and it should include brand-safety sentiment. The recommendation should be "
    "delivered through a complete application, from data collection to a queryable API and dashboard, as a ranked list of creators for a given "
    "product, budget and audience, each with an explicit range and a statement of how much evidence stands behind it.")
R.section("Objectives")
R.P("A review of the literature (Chapter 3) shows that no existing system combines a multi-relational spillover graph, causal correction, "
    "cross-platform temporal analysis and a ranked recommendation. The objectives of this project are:")
R.numbered([
    "Build GAIL (Graph-Adaptive Interference Learning), a graph attention model that learns creator-specific spillover from real "
    "collaboration and co-occurrence data instead of a fixed rule such as inverse network distance, and its successor GAIL-R, which estimates "
    "one effect per relation with cross-fitting and a placebo penalty.",
    "Develop a causal correction layer (propensity scores, inverse-propensity weighting and the doubly robust idea) so that the spillover "
    "estimate reflects genuine influence rather than pre-existing popularity.",
    "Develop a cross-platform temporal component that scores audience sentiment as a brand-safety signal and tests, with Granger causality and "
    "placebo timings, whether activity on one platform predicts activity on another.",
    "Develop a fusion layer that combines the signals into one 0–100 recommendation score with a range and an evidence grade (A to D).",
    "Deliver an end-to-end application — data collection, graph construction, model inference, a REST API and a brand-facing dashboard with "
    "explanations — so that the system can be evaluated as a whole.",
    "Carry out all implementation and evaluation on real, actively collected creator, collaboration and sponsorship data, and fix every "
    "hypothesis test in a written plan before running it."])
R.section("Research Questions")
R.bullets(["**RQ1.** When a creator is sponsored or posts, does engagement rise for the creators linked to them in the graph?",
           "**RQ2.** Does a creator's activity on one platform predict their audience's activity on the other platform?",
           "**RQ3.** Can a graph-based causal model recover a known spillover effect better than published graph models?",
           "**RQ4.** Can these signals be combined into a ranking that a brand can use, with an honest range for each score?"])
R.section("Assumptions and Constraints")
R.bullets(["Only public data is used; no private messages, sales or advertising-account data are available.",
           "The YouTube Data API key allows 10,000 quota units a day, shared by all collection jobs.",
           "Instagram is read through a browser extension at no more than about 130 page loads a day per account, to stay within safe use.",
           "Engagement (comments, views, likes, subscribers) is used as the outcome because conversions are not observable.",
           "The creator scope is fixed in advance (Indian fitness and health creators) and recorded in data/creator_scope_overrides.csv."])

# =========================================================================== CHAPTER 3
R.chapter("Literature Review")
R.section("Overview")
R.P("Several strands of prior research inform this project, from classical influence maximisation to recent graph neural network (GNN) "
    "approaches for popularity and influencer prediction, and causal inference under interference. Table 3.1 summarises the methodology, key "
    "results and limitations of twenty reviewed works [1]–[20], followed by a discussion organised by theme.")
R.tab += 1
c = doc.add_paragraph(style="Table Caption")
font(c.add_run(f"Table {R.ch}.{R.tab}: Literature comparison: methodology, results and limitations"), 11, bold=True)
put_kept("lit")
R.section("Influence Maximisation")
R.P("Classical influence-maximisation work by Kempe, Kleinberg and Tardos [1], made computationally efficient by Chen, Wang and Yang [2] "
    "and extended with centrality-based heuristics by Kundu, Murthy and Pal [3], established influence spread as a seed-selection optimisation "
    "problem over a static graph. Zareie and Sakellariou's survey [4] catalogued behaviour-aware methods that add user behaviour to structure. "
    "These works optimise structure; they do not model the causal effect of a specific treatment on a specific neighbour.")
R.section("Graph Neural Networks for Popularity and Cascades")
R.P("A second cluster applies GNNs to popularity and cascade prediction. Cao et al. [5] coupled a diffusion graph with a social graph; Jin, "
    "Liu and Murata [6] added multi-layer temporal modelling with discrete-time snapshots; Ji et al. [7] modelled dynamics at the community "
    "level; a 2025 study [8] combined macro- and micro-level features; and Rossi et al. [9] introduced Temporal Graph Networks for "
    "continuous-time graphs. Wu, Mei, Cheng and Zhang [13] decomposed popularity signals by time scale without a graph. Across this cluster, "
    "popularity is predicted as a correlational target: none of these methods separates causal lift from pre-existing popularity.")
R.section("Text and Graph Fusion")
R.P("A third cluster combines text with graph structure for social-media tasks: Benslimane, Azé and Bringay [10] for controversy detection "
    "and NAH-GNN [11] for multi-behaviour recommendation. Both show that text-graph fusion is effective; neither targets continuous causal "
    "spillover.")
R.section("Industry-Style Baselines")
R.P("A fourth cluster represents current industry practice that ignores network structure: the XGBoost model of Nisa et al. [12] on video "
    "features, and the purely textual brand-celebrity matcher of Yang, Yang and Zhang [14]. These are fast and practical, but they cannot "
    "represent the effect of one creator on another.")
R.section("Graph-Based Influencer Marketing")
R.P("The most directly relevant cluster is graph-based influencer marketing. GNN-IR [15] performs link prediction on a bipartite "
    "advertiser-influencer graph; INFLECT-DGNN [16] applies dynamic GNNs to referral marketing; Kim et al. [17] and Gan et al. [18] profile "
    "influencers using multimodal content features; and a 2026 spatio-temporal GNN [19] models influence propagation in marketing networks. "
    "None of these represents third-party spillover to a creator's collaborators, and none applies causal correction to the estimated effect. "
    "DeepInf [23] and InfluencerRank [24] learn influence from graph structure and are used later in this report as baselines.")
R.section("Causal Inference on Networks")
R.P("Causal inference with interference was formalised by Hudgens and Halloran [25]. Propensity scores [26], doubly robust estimation [27] "
    "and double/debiased machine learning [28] correct for selection bias, and the R-learner of Nie and Wager [35] estimates heterogeneous "
    "effects with cross-fitting. Wu and Yuan [29] extended orthogonal learning to networks. DCHGNN [20], applied to education, is the closest "
    "methodological precedent: it combines a dynamic heterogeneous GNN with a doubly robust estimator, confirming that this combination is an "
    "established technique that had not been applied to influencer-brand spillover.")
R.section("Research Gap")
R.P("Every reviewed study addresses at most two or three of the five properties this problem requires, and none addresses all five together. "
    "Table 3.2 compares the closest recent works on these five properties, distinguishing temporal modelling within one platform from genuine "
    "cross-platform fusion, since the two are often conflated.")
R.tab += 1
c = doc.add_paragraph(style="Table Caption")
font(c.add_run(f"Table {R.ch}.{R.tab}: Closest recent related work against the five required properties"), 11, bold=True)
put_kept("gap", 10)
R.P("No reviewed work combines a ranking output, a multi-relational graph that can represent third-party spillover, causal correction, "
    "temporal lag modelling and cross-platform fusion in one system. GNN-IR comes closest on recommendation in the marketing domain but cannot "
    "represent spillover to collaborators because its graph is bipartite, and it uses one platform. DCHGNN comes closest on the causal and "
    "temporal side but has not been applied outside education and produces no ranking. Works that use several platforms test each platform "
    "as a separate experiment rather than combining the platforms of the same creator.",
    "This project's contribution is to combine all five properties in a system built for influencer-brand matching: a multi-relational "
    "creator graph, a causal correction layer with placebo checks, a temporal component that tests lags with Granger causality, a comparison of "
    "the same creator's YouTube and Instagram activity, and a fused recommendation with an explicit range. Temporal modelling alone is not the "
    "gap — seven of the twenty works model time — but none of them tests a specific lag between two platforms of the same creator; the "
    "cross-platform temporal component of this project does exactly that.")

# =========================================================================== CHAPTER 4
R.chapter("Project Requirements Specification")
R.section("Purpose")
R.P("This chapter specifies what the influencer-brand matching system must do and the qualities it must have. It is written for the project "
    "team, the guide and the evaluators, and it is the reference against which the design (Chapters 5–7) and the tests (Chapter 9) were made.")
R.section("Product Perspective")
R.P("The system is a self-contained web application backed by a data pipeline. Collection jobs read public data from YouTube, Instagram and "
    "Reddit into a PostgreSQL database; analysis and model scripts build the graph and train the models; a FastAPI backend serves scores and "
    "a Next.js frontend presents them. It depends on three external services: the YouTube Data API v3, a browser extension for Instagram "
    "(OpenCLI), and the hosted database.")
R.section("User Classes")
R.table("User classes", ["User", "Needs", "Main pages"], [
    ["Brand manager", "Find creators for a product, budget and audience; understand why each was ranked", "Brief form, ranked dashboard, explainability, Creator Passport"],
    ["Analyst / researcher", "Check the evidence behind the spillover claims; inspect the graph", "Insights, Analysis tab, graph explorer"],
    ["Operations / team member", "Keep data collection running; watch risk alerts", "Monitoring page, collection logs"]], [3.6, 7.4, 6.0])
R.section("Functional Requirements")
R.table("Functional requirements", ["ID", "Requirement"], [
    ["FR-01", "Collect channels, videos, comments and subscriber counts from YouTube through the official API on a schedule."],
    ["FR-02", "Collect Instagram profiles, posts and comments read-only within a daily page-load limit; collect Reddit posts that discuss creators."],
    ["FR-03", "Link each creator's accounts across platforms and verify ownership before data is used."],
    ["FR-04", "Detect sponsorship events with an evidence tier, and remove standing affiliate codes that repeat under every video."],
    ["FR-05", "Build a heterogeneous creator graph with collaboration, co-occurrence, mention, shared-brand and sponsorship relations."],
    ["FR-06", "Estimate spillover with GAIL / GAIL-R, with a placebo check and a bootstrap range."],
    ["FR-07", "Score comment sentiment (English and Hindi script) as a brand-safety signal and raise risk alerts."],
    ["FR-08", "Score creator fit to a brief with CLIP image and BERT text embeddings."],
    ["FR-09", "Fuse the branch outputs into a 0–100 score with a range, a basis label and an evidence grade A–D."],
    ["FR-10", "Accept a brief (product category, budget, region, audience, platform) and return a ranked list through POST /recommendations."],
    ["FR-11", "Show a Creator Passport comparing a creator's YouTube and Instagram behaviour."],
    ["FR-12", "Show an interactive graph with a Ripple view of how an effect could travel along links."],
    ["FR-13", "Show monitoring alerts and the evidence for every analysis result (Insights and Analysis pages)."],
    ["FR-14", "Provide health checks and run in Docker containers."]], [2.2, 14.8])
R.section("Non-Functional Requirements")
R.table("Non-functional requirements", ["Quality", "Requirement"], [
    ["Performance", "A recommendation request returns in a few seconds for the full creator set on a laptop-class server."],
    ["Reliability", "Collection jobs resume after a failure, never retry blindly, and stop at the first sign of rate limiting."],
    ["Data integrity", "Every change to stored data first writes a backup table and can be undone."],
    ["Security", "Database credentials are kept in environment variables and never committed; team logins without delete rights."],
    ["Ethics and privacy", "Public data only; read-only collection; no likes, follows or comments are made; results reported at creator level."],
    ["Statistical honesty", "Each hypothesis test is fixed in a written plan before the data is examined and is run once."],
    ["Maintainability", "Typed Python and TypeScript; 642 automated tests run before every push."],
    ["Usability", "Every score shows its basis, range and evidence grade in plain words."],
    ["Portability", "Backend and frontend are packaged as Docker images; the database is a managed PostgreSQL service."]], [3.6, 13.4])
R.section("External Interface Requirements")
R.bullets(["**User interface:** a browser-based dashboard (Next.js, responsive layout).",
           "**Software interfaces:** YouTube Data API v3 (REST, JSON); PostgreSQL over TLS; OpenCLI browser extension for Instagram; Reddit page JSON.",
           "**Communication interfaces:** HTTPS REST endpoints returning JSON; CORS restricted to the frontend's address."])
R.section("Hardware and Software Requirements")
R.table("Hardware and software requirements", ["Component", "Requirement"], [
    ["Development machine", "Windows 11 laptop, 8 GB RAM or more; Python 3.12; Node.js 24; Docker Desktop"],
    ["Database", "Azure Database for PostgreSQL (flexible server); earlier phases used Supabase PostgreSQL"],
    ["ML libraries", "PyTorch 2.6 (CPU), PyTorch Geometric 2.8, transformers 5.14 (RoBERTa, XLM-R, CLIP, BERT), numpy, scipy, pandas"],
    ["Backend", "FastAPI 0.141, Uvicorn, SQLModel, Pydantic 2, psycopg2"],
    ["Frontend", "Next.js 16, React 19, TypeScript 5, Tailwind CSS 4, d3-force"],
    ["Scheduling", "GitHub Actions timers (every 2 h and every 30 min); laptop collectors for Instagram and comment backfill"],
    ["Testing", "pytest, ESLint, TypeScript compiler, Next.js production build"]], [4.2, 12.8])

# =========================================================================== CHAPTER 5
R.chapter("High Level Design")
R.section("Design Goals")
R.bullets(["Keep each branch independently testable, and fuse them late.",
           "Make every number traceable: each score carries its basis, range and evidence grade.",
           "Separate collection from analysis, so that the data can grow daily without changing the models.",
           "Fix the statistical plan before the data, so that results cannot be tuned after the fact."])
R.section("System Architecture")
R.P("The system has five modules (Figure 5.1 and Figure 5.2). The data collection module reads YouTube, Instagram and Reddit into the "
    "database. The features and graph module turns raw records into feature vectors and a heterogeneous graph. The model branches estimate "
    "spillover (GAIL-R), audience mood (sentiment and risk) and creator fit (CLIP and BERT). The fusion module combines them into a score with "
    "a range and an evidence grade, and the API and application module serves the ranked list to the brand.")
R.figure(MEDIA / "architecture_detailed.png", "High-level architecture of the system, from data sources to the application", 16.5)
R.figure(ASSETS / "architecture_modules_v3.png", "The five modules: role, input, output and the module each feeds", 15)
R.section("Module Overview")
R.table("Modules of the system", ["Module", "Role", "Input", "Output"], [
    ["1 Data collection", "Entry point of the system", "YouTube API, Instagram (OpenCLI), Reddit", "Creators, videos, posts, comments, readings, sponsorship tiers"],
    ["2 Features and graph", "Turn raw data into model inputs", "Posts, comments, thumbnails, links", "CLIP/BERT features; graph with five relations"],
    ["3 Model branches", "Spillover context and audience mood", "Graph and features", "GAIL-R effect; mood score and risk; creator fit"],
    ["4 Fusion", "One score with an honest range", "Branch outputs", "Score 0–100, range, basis, evidence grade"],
    ["5 API and app", "Serve the shortlist", "Brief: product, budget, region, audience", "Ranked creators, Creator Passport, Insights, alerts"]],
    [3.4, 3.8, 4.6, 5.2])
R.section("Three-Branch Model Design")
R.P("The three branches work on the same creator graph and are fused late (Figure 5.3). Late fusion lets each branch be validated on its own, "
    "and a missing input falls back to a labelled neutral value instead of silently distorting the score.")
R.figure(ASSETS / "dual_framework_v4.png", "Three branches on one creator graph, fused into one score", 16)
R.section("Data Flow")
R.numbered(["Timers read new YouTube uploads, statistics and subscriber counts every 2 hours (subscribers every 30 minutes) and write them, with a timestamp, to the database.",
            "A daily Instagram job refreshes known creators and collects new ones within the page-load limit; a daily comment job fills in comments.",
            "The sponsorship detector labels new posts; the owner audit detaches posts that do not belong to the creator.",
            "Graph and feature scripts rebuild the relations and embeddings; models are retrained offline and saved as checkpoints.",
            "On a request, the API filters creators by the brief, reads branch outputs, fuses them and returns the ranked list."])
R.section("Deployment Architecture")
R.table("Deployment view", ["Component", "Runs on", "Notes"], [
    ["Database", "Azure Database for PostgreSQL", "Moved from Supabase on 6 Nov 2026; admin and per-member logins"],
    ["Scheduled collection", "GitHub Actions on the main branch", "2-hourly statistics, 30-minute subscriber readings"],
    ["Instagram and comment backfill", "Team laptops", "Read-only browser extension; daily quota-aware runs"],
    ["Backend API", "Docker image (Azure Container Apps)", "FastAPI on port 8000; /health reports database status"],
    ["Frontend", "Docker image / Vercel", "Next.js production build; API address set by NEXT_PUBLIC_API_BASE_URL"]],
    [4.2, 5.4, 7.4])
R.section("Design Decisions")
R.bullets(["**Late fusion** rather than one end-to-end network: each branch has different data coverage and can be checked alone.",
           "**Spillover shown as context, not scored**: the fused score uses mood and fit, and the spillover estimate is displayed next to it with its range.",
           "**Pre-registered tests**: each spillover test has a plan file in the repository, committed before the test is run.",
           "**Read-only, rate-limited collection** keeps the project within platform rules and protects the accounts used."])

# =========================================================================== CHAPTER 6
R.chapter("Low Level Design")
R.section("Database Schema")
R.P("The database has 29 tables. Table 6.1 lists the main ones and Figures 6.1 and 6.2 show the schema. Every creator has one row in "
    "creators; platform tables reference it by creator_id, and post_snapshots stores repeated engagement readings of the same post over time.")
R.table("Main database tables", ["Table", "Content"], [
    ["creators", "One row per creator: name, category, YouTube and Instagram handles"],
    ["creator_verification", "Confidence that the accounts belong to the creator (confirmed / probable)"],
    ["creator_related_accounts", "Links between creators and their other accounts (1,166 rows)"],
    ["youtube_channels / youtube_videos / youtube_comments", "Channel statistics, 184,251 videos, 2,296,861 comments with timestamps"],
    ["instagram_profiles / instagram_posts / instagram_comments", "Profiles, 3,286 posts, 34,444 comments"],
    ["reddit_posts / reddit_comments / reddit_post_creators", "3,308 posts; the junction table gives co-occurrence edges"],
    ["brands / creator_brand_links", "126 brands and the creators linked to them"],
    ["post_snapshots / profile_snapshots", "573,368 time-stamped engagement readings; subscriber readings"],
    ["sponsorship_event_scores / sponsorship_review", "Detector tiers and human checks of sponsorship labels"],
    ["fusionscore / riskalert", "Stored scores and brand-safety alerts served by the API"]], [6.6, 10.4])
R.figure(MEDIA / "schema_1.png", "Database schema (part 1): creators and platform content", 16)
R.figure(MEDIA / "schema_2.png", "Database schema (part 2): Instagram, Reddit, brands and scores", 16)
R.section("Data Collection Components")
R.table("Collection components", ["Component (file)", "Responsibility"], [
    ["orchestrator.py", "Shared settings, rate limiter, YouTube API client (youtube_api_get), database access"],
    ["snapshot jobs (GitHub Actions)", "Every 2 h: new uploads and statistics; every 30 min: subscriber counts"],
    ["youtube_comments_backfill.py", "Comments for listed videos, up to 3 pages of 100, within a daily unit cap"],
    ["subscriber_loop.py", "Laptop backup for 30-minute subscriber readings"],
    ["instagram_daily.py / snapshot_instagram.py", "Daily Instagram refresh and new-creator collection within 130 page loads"],
    ["sponsorship detector", "Six-tier sponsorship labelling, negation handling and standing-code correction"],
    ["ownership audit", "Matches each Instagram post to the account that posted it; detaches foreign posts with a backup"]], [6.0, 11.0])
R.section("Graph Construction")
R.P("Creators are nodes with a feature vector (log subscribers, engagement rate, category encoding and embeddings). The two symmetric "
    "creator relations are stored in both directions and weighted by the number of supporting observations: matched collaborations for "
    "collaborates_with and distinct Reddit threads for co_occurs_with. Mentions are directed. Brands are separate nodes joined to creators by "
    "sponsors edges, and shares_brand links two creators sponsored by the same brand.")
R.section("Model Classes")
R.table("Model classes (ml/gail_model.py, ml/gail_r.py)", ["Class", "Purpose"], [
    ["HeteroGATBackbone", "One graph attention convolution per relation; messages summed; produces creator embeddings"],
    ["ExposureModule", "Learned attention over collaborates_with neighbours; exposure = weighted sum of neighbours' sponsorship"],
    ["MultiRelationExposureModule", "Exposure computed separately for each relation (used by GAIL-R)"],
    ["SpilloverPredictionHead", "MLP on [embedding; exposure] giving the predicted spillover"],
    ["PropensityScoreModel", "MLP with sigmoid giving the probability that a creator is sponsored"],
    ["GAILModel", "Combines backbone, exposure, head and propensity; trained with the causal loss (ml/gail_loss.py)"],
    ["GAILR", "Two-stage cross-fitted R-learner with one slope per relation and the placebo penalty"]], [5.4, 11.6])
R.section("Backend API")
R.table("REST endpoints (FastAPI)", ["Endpoint", "Purpose"], [
    ["POST /recommendations", "Ranked creators for a brief, with score, range, basis and evidence grade"],
    ["GET /feature-store/creators, /feature-store/creators/summary", "Creator feature records"],
    ["GET /feature-store/edges/{collaborations, co-occurrence, mentions, shared-brand, sponsorships}", "Graph edges for the graph explorer"],
    ["GET /passport/{creator_id}, /passport/strip", "Creator Passport: YouTube vs Instagram behaviour"],
    ["GET /platform-profiles", "Platform status for each creator"],
    ["GET /alerts, POST /alerts/compute", "Brand-safety risk alerts"],
    ["GET /analysis/insights, /analysis/spillover, /analysis/clash", "Evidence for the Insights and Analysis pages; competitor-clash flags"],
    ["POST /scenario", "What-if scenario for a brief"],
    ["POST /ingestion/...", "Load creators, channels, videos, posts and profiles"],
    ["GET /health", "Service and database status"]], [8.2, 8.8], size=10)
R.section("Frontend Pages")
R.table("Frontend pages (Next.js)", ["Page", "Content"], [
    ["Home", "Project overview and navigation"],
    ["Brand input", "Brief form: product category, budget, region, audience, platform"],
    ["Dashboard", "Ranked creators with score, range, basis badge, evidence grade and clash warning"],
    ["Explainability", "How each score is built from its branches"],
    ["Creator Passport", "One record per creator comparing YouTube and Instagram"],
    ["Insights", "Spillover results, method checks and evidence room; graph with Ripple view"],
    ["Analysis", "Charts of the analyses behind the claims"],
    ["Monitoring", "Risk alerts with creator names"]], [4.0, 13.0])
R.section("Sequence of a Recommendation Request")
R.numbered(["The brand submits the brief on the Brand input page; the frontend sends POST /recommendations.",
            "Hard filters remove creators outside the budget or without a handle on the requested platform.",
            "Soft filters remove a creator only when text evidence exists and does not match the region, audience or product.",
            "For each remaining creator the backend reads the mood, fit and spillover outputs and their bases.",
            "The fusion layer computes the score, the range and the evidence grade; creators with data rank above those without.",
            "The sorted list is returned as JSON and shown on the Dashboard, with links to the Passport and Explainability pages."])

# =========================================================================== CHAPTER 7
R.chapter("System Design (Detailed)")
R.section("Graph Definition")
R.P("The creator ecosystem is a heterogeneous graph G = (V, E). The node set V contains creators and brands, and each edge has a relation "
    "type r from a fixed set R:")
R.equation("e = (u, v, r),   r ∈ R = {collaborates_with, co_occurs_with, mentions, shares_brand, sponsors}")
R.P("Each creator node i carries a feature vector x_i and a treatment indicator T_i = 1 when it has a sponsorship event in the window studied.")
R.section("GAIL Branch")
R.P("The backbone is a heterogeneous graph attention layer [21] implemented in PyTorch Geometric [22]. For each relation a graph attention "
    "convolution computes coefficients over a node's neighbours, the messages from all relations are summed, and a ReLU is applied:")
R.equation("h_i = ReLU( Σ_r Σ_{j ∈ N_r(i)} α_ij^r W^r x_j )")
R.equation("α_ij = softmax_j( LeakyReLU( aᵀ [ W x_i ‖ W x_j ] ) )")
R.P("The model uses a hidden width of 16 and two averaged attention heads. Exposure measures how much sponsorship a creator's neighbours "
    "carry, with a learned coefficient for each neighbour instead of a fixed rule such as one over network distance:")
R.equation("e_i = Σ_{j ∈ N(i)} α_ij T_j")
R.P("The predicted spillover is a small network applied to the embedding and the exposure:")
R.equation("ŷ_i = MLP( [ h_i ; e_i ] )")
R.section("Causal Correction")
R.P("Brands do not sponsor creators at random, so naive training would learn selection bias. A propensity model [26] estimates the "
    "probability that a creator is sponsored given its features:")
R.equation("π_i = σ( MLP( x_i ) )")
R.P("Inverse-propensity weights correct for the fact that popular creators are sponsored more often, with propensities clipped to [ε, 1 − ε] "
    "and ε = 0.05:")
R.equation("w_i = T_i / π_i + (1 − T_i) / (1 − π_i)")
R.equation("L_pred = Σ_i w_i ( ŷ_i − y_i )² / Σ_i w_i")
R.P("Three penalties are added: the overlap penalty keeps propensities away from 0 and 1, the smoothness penalty asks linked creators to "
    "have similar predictions, and the consistency penalty asks that a creator with no sponsored neighbour has zero predicted spillover:")
R.equation("L_overlap = mean( max(0, ε − π_i)² + max(0, π_i − (1 − ε))² )")
R.equation("L_smooth = mean_{(u,v)} w_uv ( ŷ_u − ŷ_v )²,    L_cons = mean_{i: e_i = 0} ŷ_i²")
R.equation("L = 1.0 L_pred + 0.1 L_overlap + 0.1 L_smooth + 0.1 L_cons")
R.P("The doubly robust estimator [27] adds an outcome model μ to the weighting, so that the estimate stays valid if either the propensity "
    "model or the outcome model is correct:")
R.equation("τ̂ = μ(e, X) + [ T / π(X) ] · [ Y − μ(e, X) ]")
R.section("GAIL-R: Graph R-Learner with Placebo Penalty")
R.P("GAIL-R builds on the R-learner [35] and orthogonal learning on networks [29]. Stage 1 predicts, with cross-fitting, the normal "
    "engagement m̂(x) = E[Y | X] and the normal exposure ê_r(x) = E[E_r | X] for each relation r. Stage 2 explains what is left with one slope "
    "β_r per relation:")
R.equation("Ỹ_i = Y_i − m̂(x_i),     Ẽ_ir = E_ir − ê_r(x_i)")
R.equation("L_R = Σ_i ( Ỹ_i − Σ_r β_r Ẽ_ir )² + λ ‖α − α_uniform‖² + w_p · P_placebo")
R.P("The attention term keeps attention near uniform unless the data supports otherwise, and the placebo penalty P_placebo penalises any "
    "'effect' measured before the event, where none can exist. The reported effect is the average effect on exposed creators (ATT), with a "
    "95% interval from a bootstrap [36] that resamples whole creators.")
R.section("Mood Branch")
R.P("Each comment is scored by RoBERTa [33] for English and by the multilingual XLM-R model [32] for Hindi-script comments. A creator's "
    "brand-safety score is the mean over comments of:")
R.equation("s = P(positive) + 0.5 · P(neutral)")
R.P("For creators with few comments the score is pulled toward the neutral value 0.5. A creator whose score falls below the 20th "
    "percentile is a shock source, and its risk is spread along supported links for two hops with a decay of 0.5 per hop:")
R.equation("risk_j = Σ_{h = 1, 2} 0.5^h · Σ_{i: d(i, j) = h} shock_i")
R.section("Creator-Fit Branch")
R.P("Thumbnails are embedded with CLIP [30] (512 dimensions) and titles, descriptions and captions with BERT [31] (768 dimensions). The "
    "brand brief is embedded the same way, and the fit score is the cosine similarity between the brief and the creator's recent content, "
    "rescaled to [0, 1]:")
R.equation("fit_i = ( 1 + cos( z_brief , z̄_i ) ) / 2")
R.section("Fusion Layer")
R.P("The fusion layer combines the branch outputs into the final score on a 0–100 scale. Spillover is shown next to the score as context "
    "with its own range, and has weight 0 in the score:")
R.equation("score = clip( 100 × ( 0.5 · mood + 0.5 · fit ) + adj , 0 , 100 ),   adj = −10 if mood < 0.3")
R.P("The range combines each branch's half-width u_k with its weight w_k in quadrature:")
R.equation("half-width = sqrt( Σ_k ( w_k · u_k )² ),     range = score ± 100 × half-width")
R.P("Every score also carries a basis label for each branch (trained, inferred, scored, placeholder or isolated) and an evidence grade "
    "that states how much real data stands behind it (Table 7.1).")
R.table("Evidence grade (backend/app/evidence.py)", ["Evidence", "Points"], [
    ["Sentiment from 200 or more scored comments / 20–199 comments", "2 / 1"],
    ["Content match scored from real posts (CLIP / BERT)", "2"],
    ["YouTube and Instagram data / one platform", "2 / 1"],
    ["Creator has graph links (spillover trained or inferred)", "1"],
    ["Grade: A ≥ 6 points, B 4–5, C 2–3, D 0–1", ""]], [13.0, 4.0])
R.section("Creator Passport")
R.P("The Creator Passport is one record per creator that compares the two platforms: the mood gap (Instagram minus YouTube comment mood, "
    "with a worst-case error bound), attention speed (share of week-one views in the first 24 hours), the response to sponsored posts "
    "against the creator's own organic posts, an estimate for a missing platform, and a competitor-clash flag when the creator promoted a "
    "rival brand in the last 120 days.")
R.section("Cross-Platform Temporal Analysis")
R.P("For each creator, daily series are built for posts on one platform (X) and audience activity on the other (Y). To isolate the "
    "audience's response from new uploads, Y counts comments on videos older than 72 hours. A pooled Granger test [34] with lags 1–3 days, "
    "after removing each creator's mean, compares a model of Y on its own past with a model that adds the past of X:")
R.equation("F = [ (RSS_restricted − RSS_full) / q ] / [ RSS_full / (n − k) ]")
R.P("The p-value is not taken from the F table. Instead each creator's X series is shifted circularly by a random 10–300 days, 500 "
    "times, which keeps every series' own pattern but breaks the timing between them:")
R.equation("p = ( 1 + #{ F_shifted ≥ F_real } ) / ( 1 + 500 )")

# =========================================================================== CHAPTER 8
R.chapter("Proposed Methodology")
R.section("Overview")
R.P("The methodology has five stages: (1) collect public data daily; (2) clean it, verify ownership and label sponsorships; (3) build "
    "features and the graph; (4) estimate the branch outputs and fuse them; and (5) evaluate with pre-registered tests and simulation "
    "benchmarks. Stages 1–3 run continuously; stages 4 and 5 run on fixed snapshots so that results can be reproduced.")
R.section("Data Collection")
R.subsection("Source of Data")
R.P("Data is collected directly from three platforms: YouTube through the official YouTube Data API v3, Instagram through a read-only "
    "browser extension, and Reddit through its public page JSON. It is not drawn from a public benchmark, because the project depends on real "
    "collaboration and sponsorship relationships that no public dataset contains. Data is stored in PostgreSQL, which was hosted on Supabase "
    "until 6 November 2026 and on Azure Database for PostgreSQL since then.")
R.subsection("Collection Technology")
R.P("A central Python orchestrator coordinates ingestion. YouTube jobs run on GitHub Actions every 2 hours (statistics and new uploads) and "
    "every 30 minutes (subscriber counts), and a laptop job fills in comments within the daily quota. Instagram is collected in a Chrome "
    "session through the OpenCLI extension, reading profiles, posts and comments within about 130 page loads a day, refreshing known "
    "creators first. Records are written with psycopg2 and SQLModel, so every row is checked against the schema before it is stored.")
R.subsection("Data Description")
R.P("Table 8.1 gives the size of the dataset on 12 November 2026 and Figure 8.1 shows it on a log scale. Compared with the first phase "
    "(259 creators, 1,770 videos and about 148,000 comments), the dataset has grown more than a hundredfold in videos and fifteenfold in "
    "comments.")
R.table("Dataset size (12 November 2026)", ["Item", "Count"], [
    ["Creators tracked / in scope (Indian fitness and health)", "651 / 512"],
    ["In-scope creators with a verified Instagram handle", "437"],
    ["YouTube videos / comments", "184,251 / 2,296,861"],
    ["Instagram posts / comments", "3,286 / 34,444"],
    ["Reddit posts", "3,308"],
    ["Time-stamped engagement readings (post_snapshots)", "573,368"],
    ["Sponsored posts detected (YouTube / Instagram)", "3,319 / 127"],
    ["Brands", "126"],
    ["Cross-platform and related-account links", "1,166"]], [11.0, 6.0])
R.figure(FIG / "fig_data_volume.png", "Size of the collected dataset (log scale), 12 November 2026", 14.5)
R.subsection("Why Reddit Was Included")
R.P("Reddit serves two purposes that YouTube and Instagram cannot. It is the main source of co-occurrence edges, because communities often "
    "discuss several creators in the same thread even when no direct collaboration exists. It also adds an independent pool of audience text "
    "for the sentiment signal.")
R.section("Preprocessing")
R.subsection("Sponsorship Detection")
R.P("Sponsorship events are identified from evidence in the content itself and graded in six tiers (Table 8.2). A post takes the highest "
    "tier it matches, and negations such as 'not sponsored' are ignored. Spoken sponsorships are read from video captions.")
R.table("Sponsorship evidence tiers (strongest first)", ["Tier", "Evidence"], [
    ["1 Official label", "Platform paid-partnership label"],
    ["2 Spoken", "Sponsor named in the video's spoken captions"],
    ["3 Creator comment", "Creator's own pinned or reply comment discloses the sponsor"],
    ["4 Disclosure tag", "#ad, #sponsored, #collab and similar tags"],
    ["5 Brand and code", "Brand name together with a discount code or affiliate link"],
    ["6 Brand mention", "Brand name only"]], [4.6, 12.4])
R.P("Many creators keep the same discount code under every video for months. Such a standing code is not a new sponsorship: when a weak "
    "tier repeats the same brand in at least half of a creator's videos within 30 days, the label is removed. This correction un-flagged 470 "
    "videos of 17 creators, with a backup and an undo.")
R.subsection("Ownership Audit and Deduplication")
R.P("Every Instagram post is matched to the account that actually posted it, using the page's own metadata; posts that belong to another "
    "account are detached with a backup. Creator records are deduplicated by platform handle, falling back to name matching only when no "
    "handle exists, with guards against merging two different people. Instagram post dates that were missing were recovered from the post "
    "shortcode. Instagram handles for 157 in-scope creators were added on 11 November 2026, taken only from the creators' own YouTube "
    "descriptions and About pages and checked by hand.")
R.section("Feature Extraction")
R.P("A feature store converts cleaned rows into one record per creator: log subscriber count, engagement rate, a content-category "
    "encoding, and the raw text and thumbnail addresses used for embeddings. CLIP produces 512-dimensional image embeddings and BERT "
    "768-dimensional text embeddings, which the creator-fit branch compares with the brief.")
R.section("Exploratory Data Analysis")
R.subsection("Network Structure")
R.P("The collaboration graph has a heavy-tailed degree distribution (Figure 8.2, first-phase snapshot of 259 creators): a small number of "
    "hub creators hold a large share of all edges, the scale-free pattern seen in real social networks. This directly motivates a graph model "
    "rather than treating creators as independent units.")
R.figure(MEDIA / "degree_distribution.png", "Degree distribution of the creator graph, linear and log-log scale (phase-1 snapshot)", 15.5)
R.subsection("Popularity Proxies and Learned Spillover")
R.P("Among model-scored, connected creators, the usual popularity proxies — log subscribers, engagement rate and network degree — have "
    "only weak Spearman correlations (between +0.12 and +0.26) with the learned spillover score (Figure 8.3). Follower count and engagement "
    "alone do not capture network-driven influence, which supports the project's premise.")
R.figure(MEDIA / "correlation_heatmap.png", "Spearman correlation between popularity proxies and the learned spillover score", 11)
R.subsection("Audience Mood")
R.P("Brand-safety scores are spread between about 0.3 and 0.9 with a median near 0.56 (Figure 8.4). The 20th percentile marks the shock "
    "threshold used by the risk propagation.")
R.figure(MEDIA / "brand_safety_hist.png", "Distribution of creator brand-safety (mood) scores", 13)
R.subsection("Lag Profiles")
R.P("Lag profiles between platforms (Figure 8.5) show the strongest association at short lags, with YouTube uploads lifting the same "
    "channel's comments as a positive control. This exploratory view motivated the formal Granger test of Section 7.9.")
R.figure(MEDIA / "lag_plots.png", "Lag correlation profiles between platform activity series", 15.5)
R.section("Spillover Evaluation Protocol")
R.P("Spillover claims are easy to produce by accident, so every test follows the same protocol:")
R.numbered(["**Plan first.** A plan file stating the events, outcome, window, placebo and decision rule is committed to the repository "
            "before any outcome is computed.",
            "**Placebo.** The same statistic is computed at random times or for unlinked pairs, where no effect can exist.",
            "**Decision rule.** An effect is reported as detected only if its 95% bootstrap interval lies above zero and the placebo interval "
            "contains zero (or, for Granger tests, if the real F beats the placebo distribution at p < 0.05).",
            "**Minimum size.** With fewer than 20 events a test is reported as early evidence, not as a result.",
            "**Run once.** A test is never re-run to cross the 0.05 threshold; every result is reported."])
R.section("Model Evaluation Protocol")
R.P("Real data contains no ground truth for spillover, so models are also judged on a planted-effect benchmark: a known effect is added to "
    "the real graph and data, and each method must recover it. The error is the precision in estimating heterogeneous effects (PEHE), the "
    "root mean squared difference between the estimated and true per-creator effect:")
R.equation("PEHE = sqrt( (1/n) Σ_i ( τ̂_i − τ_i )² )")
R.P("Two settings are used, without and with a pre-existing trend that can be mistaken for an effect. Published graph models (DeepInf "
    "[23], INFLECT-DGNN [16], TNet) were run from their authors' code on the same benchmark.")

# =========================================================================== CHAPTER 9
R.chapter("Implementation and Pseudocode")
R.section("Technology Stack")
R.table("Technology stack", ["Layer", "Technology"], [
    ["Data and infrastructure", "Python 3.12, PostgreSQL (Azure; earlier Supabase), psycopg2, SQLModel, YouTube Data API v3, OpenCLI + Chrome extension, GitHub Actions"],
    ["Machine learning", "PyTorch 2.6, PyTorch Geometric 2.8, transformers 5.14 (RoBERTa, XLM-R, CLIP, BERT), numpy, scipy, pandas, scikit-learn"],
    ["Backend", "FastAPI 0.141, Uvicorn, Pydantic 2, 11 routers"],
    ["Frontend", "Next.js 16, React 19, TypeScript 5, Tailwind CSS 4, d3-force graph, SVG charts"],
    ["Packaging and quality", "Docker and Docker Compose, pytest, ESLint, tsc, Git and GitHub"]], [4.4, 12.6])
R.section("Repository Structure")
R.table("Main folders of the repository", ["Folder", "Content"], [
    ["scripts/ingestion", "Collectors, sponsorship detector, ownership audit, daily jobs"],
    ["scripts", "Analysis and test scripts (spillover tests, Granger, simulations, benchmarks)"],
    ["ml", "GAIL, GAIL-R, losses, estimators"],
    ["backend/app", "FastAPI application, routers, fusion, evidence grade"],
    ["frontend/src/app", "Next.js pages"],
    ["models", "Checkpoints and result files (JSON) of every analysis"],
    ["tests, backend/tests", "Automated tests"],
    [".github/workflows", "Scheduled collection timers"]], [4.6, 12.4])
R.section("Data Collection")
R.P("Algorithm 9.1 shows the daily comment collection. It spends at most a fixed number of API units, takes the busiest videos first, "
    "skips videos with comments switched off, and stops at the first quota error, so it never competes with the scheduled timers.")
R.code("Algorithm 9.1: Quota-aware comment collection", [
    "input: video list V, pages per video P, unit cap U",
    "todo <- videos in V with no stored comments (or a full first page)",
    "todo <- todo minus videos known to have comments disabled",
    "sort todo by comment_count descending",
    "units <- 0",
    "for v in todo:",
    "    if units >= U: break",
    "    resp <- commentThreads.list(v, maxResults=100); units <- units + 1",
    "    save resp.items",
    "    repeat up to P-1 times while resp.nextPageToken:",
    "        resp <- commentThreads.list(v, pageToken); units <- units + 1; save",
    "    on 'comments disabled': remember v; on quota error: stop",
    "report units used, comments saved, videos still waiting"])
R.section("Sponsorship Detection")
R.code("Algorithm 9.2: Sponsorship tier and standing-code correction", [
    "for post in new_posts:",
    "    owner <- owner_from_page_metadata(post)",
    "    if owner != post.creator: backup(post); detach(post); continue",
    "    tier <- highest of: official_label > spoken > creator_comment",
    "                        > disclosure_tag > brand_and_code > brand_mention",
    "    if tier and not negated(post.text): post.is_sponsored <- True",
    "for creator, brand with weak tiers:",
    "    if brand appears in >= 50% of creator's videos within 30 days:",
    "        backup(); unflag those videos   # standing code, not a new deal"])
R.section("GAIL-R Training")
R.code("Algorithm 9.3: GAIL-R (graph R-learner with placebo penalty)", [
    "split creators into K folds",
    "for each fold k:                      # stage 1, cross-fitted",
    "    fit m_hat on other folds: Y ~ X",
    "    fit e_hat_r on other folds: E_r ~ X   for each relation r",
    "    predict on fold k",
    "Y_res <- Y - m_hat(X);  E_res_r <- E_r - e_hat_r(X)",
    "repeat for epochs:                    # stage 2",
    "    effect <- sum_r beta_r * E_res_r",
    "    loss <- mean((Y_res - effect)^2)",
    "          + lambda * ||attention - uniform||^2",
    "          + w * placebo_penalty(effect, pre_event_lift)",
    "    update beta, attention by gradient descent",
    "ATT <- mean effect on exposed creators",
    "interval <- bootstrap over whole creators (2,000 draws)"])
R.section("Cross-Platform Granger Test")
R.code("Algorithm 9.4: Pooled Granger test with circular-shift placebo", [
    "for creator c in creators with data on both platforms:",
    "    X_c <- daily posts on platform A (365 days)",
    "    Y_c <- log1p(daily comments on platform-B items older than 72 h)",
    "    remove each series' own mean",
    "F_real <- pooled Granger F of Y on its lags 1..3 plus X lags 1..3",
    "for b in 1..500:                       # placebo, seed fixed",
    "    shift every X_c circularly by random 10..300 days",
    "    F_b <- pooled Granger F on shifted series",
    "p <- (1 + count(F_b >= F_real)) / (1 + 500)",
    "detected if p < 0.05 (plan fixed before the run)"])
R.section("Recommendation and Fusion")
R.code("Algorithm 9.5: Serving a recommendation", [
    "input: brief (category, budget, region, audience, platform)",
    "C <- all creators in scope",
    "C <- C minus creators above budget or without the requested platform",
    "C <- C minus creators whose text evidence contradicts region/audience/product",
    "for c in C:",
    "    mood, u_m <- mood branch (or 0.5 placeholder);  fit, u_f <- fit branch",
    "    score <- 100 * (0.5*mood + 0.5*fit);  if mood < 0.3: score -= 10",
    "    half <- sqrt((0.5*u_m)^2 + (0.5*u_f)^2);  range <- score +/- 100*half",
    "    grade <- evidence_grade(comments, fit basis, platforms, links)",
    "    attach spillover estimate and range as context",
    "rank by (has posts, score) descending; return JSON"])
R.section("Backend and Frontend")
R.P("The backend is a FastAPI application with 11 routers (Table 6.4). Responses are validated with Pydantic schemas; the evidence grade "
    "and basis labels are computed on every request so that they always match the data. The frontend is a Next.js application with eight "
    "pages (Table 6.5). The ranked dashboard shows each creator's score, range, basis badge, evidence grade and clash warning; the Creator "
    "Passport compares the two platforms; the Insights page presents the spillover results with their method checks; and the graph explorer "
    "lets the user drag nodes and run a Ripple view that shows how an effect would travel along the links.")
R.placeholder("Brand input page with a filled brief (e.g. whey protein, fitness, budget 3,00,000, India)", "Brand input page")
R.placeholder("Ranked dashboard showing scores, ranges, basis badges and evidence grades", "Ranked recommendation dashboard")
R.section("Deployment and Containerisation")
R.P("The backend and frontend are built as Docker images (backend/Dockerfile, built from the repository root). The backend container "
    "exposes port 8000 and a /health endpoint that reports database connectivity; the frontend reads the API address from "
    "NEXT_PUBLIC_API_BASE_URL. The deployment configuration targets Azure Container Apps for the backend and Vercel for the frontend, with "
    "the database on Azure Database for PostgreSQL.")
R.section("Testing")
R.P("Tests were written with each module and all suites are run before every push. Table 9.3 summarises the test plan; 642 automated "
    "tests are collected across the three suites.")
R.table("Test plan and results", ["Test type", "What is covered", "Tool", "Tests"], [
    ["Unit: ML and analysis", "GAIL, GAIL-R, placebo, estimators, lag and Granger, simulations, Passport maths", "pytest", "368"],
    ["Unit: backend", "Scoring, fusion, filters, feature store, alerts, Passport, evidence grade", "pytest", "146"],
    ["Unit: ingestion", "Detector, standing-code fix, daily jobs, Reddit, snapshots, Instagram planner", "pytest", "128"],
    ["Frontend", "Type check, lint, production build of 8 pages", "tsc, ESLint, Next.js", "pass"],
    ["Integration", "Brief to dashboard to Passport in a browser; Docker build and health check", "Browser, Docker", "checked"],
    ["Data validation", "Owner audit, duplicates, human label checks, backups", "SQL, scripts", "checked"],
    ["Statistical validation", "Placebo tests, planted-effect benchmark, power analysis", "Python, numpy", "Chapter 10"]],
    [3.6, 7.4, 3.6, 2.4], size=10)
R.placeholder("Terminal output of the three pytest suites and the frontend build passing", "Automated test suites passing")

# =========================================================================== CHAPTER 10
R.chapter("Experimentation Results and Discussion")
R.section("Experimental Setup")
R.P("All results use the project's own data, collected as described in Chapter 8, and each analysis writes a result file to the models "
    "folder. Spillover tests follow the protocol of Section 8.6: each has a plan file committed before it was run. Model comparisons use the "
    "planted-effect benchmark of Section 8.7.")
R.section("Data Collection Results")
R.P("The pipeline collected 184,251 YouTube videos and 2,296,861 comments, 3,286 Instagram posts and 34,444 comments, 3,308 Reddit posts "
    "and 573,368 time-stamped engagement readings (Table 8.1). On 11 November 2026 alone, the comment job saved 355,628 comments for the "
    "replication study within the daily quota. The readings every 2 hours (and every 30 minutes for subscribers) make it possible to measure "
    "effects within hours rather than days.")
R.section("Sponsorship Label Quality")
R.P("Strong evidence tiers were correct in 73 of 75 events checked one by one (91–99% with a 95% interval). The standing-code correction "
    "removed 470 repeated affiliate-code videos, so that a sponsorship event marks a new deal rather than a permanent link in the description.")
R.section("Cross-Platform Spillover Within Creators")
R.P("The main spillover finding concerns the same creator across platforms. When a creator posts on Instagram, comments on that creator's "
    "older YouTube videos (more than 72 hours old, so not driven by a new upload) rise over the next one to three days. On 105 creators the "
    "pooled Granger statistic is F = 1.559, against a median of 1.016 for 500 shifted timings, giving p = 0.002. The reverse direction also "
    "holds: YouTube comments predict Instagram posting with F = 1.561 and p = 0.014 (Figure 10.1). The link was first found on 90 creators "
    "and remained detected when the data grew to 105.")
R.figure(FIG / "fig_cross_platform_granger.png", "Cross-platform Granger test: real timing against 500 shifted timings (105 creators)", 14)
R.P("A follow-up test asked whether the link comes from creators who explicitly send followers to the other platform. It does not: the link "
    "is at least as strong for creators who never mention Instagram in their YouTube text (F = 2.08, p = 0.014) as for those who do. The "
    "audience appears to follow creators across platforms on its own. As with all Granger tests, this shows prediction in time rather than "
    "proof of cause.")
R.section("Spillover Between Creators")
R.P("Spillover between different creators was examined with eleven pre-registered designs, from 34 to 3,985 events (Table 10.1). The "
    "strongest design used every day of a year for 238 creator pairs linked by tags: creator A's posting predicted comments on creator B's "
    "older videos better than shuffled timing (p = 0.002), and better than randomly chosen unlinked creators at p = 0.054, just above the "
    "pre-set 0.05 threshold. The other designs placed the between-creator effect within the placebo range, which bounds any spillover between "
    "creators to a small size. Three forward tests with readings every 30 minutes (Table 10.2) measure new collaborations as they happen.")
R.table("Pre-registered spillover tests", ["Test", "Size", "Result"], [
    ["Instagram post -> comments on the same creator's older YouTube videos", "105 creators", "**Detected, p = 0.002**"],
    ["YouTube activity -> the same creator's Instagram posts", "105 creators", "**Detected, p = 0.014**"],
    ["Creator A posts -> comments on tag-linked creator B's older videos", "238 pairs", "p = 0.002 vs timing; p = 0.054 vs unlinked"],
    ["Same, creators who made a video together", "164 pairs", "p = 0.034 vs timing; within placebo vs unlinked"],
    ["A sponsored -> linked creators' engagement (GAIL-R)", "298 exposed", "Within placebo range"],
    ["A tags B -> A's commenters move to B; B's 7-day engagement", "100 / 116 events", "Within placebo range"],
    ["A tags B -> B's comments name A", "100 events", "Within placebo range"],
    ["A sponsors brand X -> B's comments name brand X", "3,985 events", "Within placebo range"],
    ["A and B in one video -> B's engagement", "177 events", "Within placebo range"],
    ["Sponsored post on one app -> same creator's other app", "34 events", "Within placebo range"],
    ["Sponsored video -> brand named on the creator's next videos", "431 events", "Within placebo range"],
    ["A sponsors -> B's older videos' views within 48 h", "63 events", "Within placebo range"]], [9.0, 3.0, 5.0], size=10)
R.table("Forward tests running with 30-minute readings", ["Test", "Result date"], [
    ["Tag retest with up to 300 comments per video (441 events)", "13–14 Nov 2026"],
    ["Large creator -> smaller guest's subscribers within 48 h", "20 Nov 2026"],
    ["New collaborations -> partner's subscribers within 48 h", "20 Nov 2026"]], [12.0, 5.0])
R.section("Model Benchmark Against Published Methods")
R.P("On the planted-effect benchmark (390-creator graph, true mean effect 0.25, three replicates), GAIL-R recovered the per-creator effects "
    "far more accurately than the published graph models (Figure 10.2, Table 10.3). Without a pre-existing trend its PEHE was 0.068, against "
    "0.33 for a doubly robust model without the graph and 0.44–0.45 for DeepInf, INFLECT-DGNN and TNet. With a pre-existing trend, which "
    "misleads the other methods, GAIL-R with the placebo penalty had the lowest error (0.101), showing that the placebo penalty does what it "
    "was designed to do.")
R.figure(FIG / "fig_baselines_pehe.png", "Per-creator error (PEHE) on the planted-effect benchmark; lower is better", 14.5)
R.table("PEHE on the planted-effect benchmark (lower is better)", ["Method", "No pre-trend", "With pre-trend"], [
    ["Doubly robust, no graph", "0.330", "0.382"], ["DeepInf (KDD 2018)", "0.443", "0.442"],
    ["INFLECT-DGNN (IEEE Access 2024)", "0.444", "0.441"], ["TNet (ICML 2024)", "0.446", "0.582"],
    ["**GAIL-R**", "**0.068**", "0.307"], ["**GAIL-R + placebo penalty**", "0.131", "**0.101**"]], [8.0, 4.5, 4.5])
R.section("Same Creator on Both Platforms")
R.P("Comparing each creator's YouTube and Instagram posts made within 24 hours of each other, measured against the creator's own usual "
    "level on each platform and adjusted with a placebo, gives 1,074 post pairs from 65 creators. Instagram performed better in 63% of pairs "
    "(median adjusted difference 0.149 on the log scale), but the direction differs by creator (Figure 10.3), which is why the Creator "
    "Passport reports it per creator.")
R.figure(FIG / "fig_platform_pairs.png", "Instagram minus YouTube response for the same creator, placebo-adjusted, one bar per creator", 14.5)
R.section("Creator Passport and Further Results")
R.table("Results of the Creator Passport features", ["Feature", "What it measures", "Result"], [
    ["Same creator on both platforms", "YouTube vs Instagram posts within 24 h, placebo-adjusted", "1,074 pairs, 65 creators; Instagram better in 63%"],
    ["Mood gap", "Instagram minus YouTube comment mood with an error bound", "14 of 85 creators flagged"],
    ["Sponsored response", "Sponsored post against the creator's organic posts", "YouTube views −5.8%: no clear penalty"],
    ["Missing-platform estimate", "Instagram level estimated from YouTube, as a range", "Rank agreement 0.78 vs 0.52 for size alone"],
    ["Attention speed", "Share of week-one views gained in 24 h", "59% in the first 24 h"],
    ["Competitor-clash flag", "Promoted a rival brand in the last 120 days", "64 creators flagged"],
    ["Bot detection", "Random forest [37] and logistic regression on 218 channels", "Accuracy 0.82, ROC-AUC 0.92"]], [4.2, 6.8, 6.0], size=10)
R.section("Application Results")
R.P("The application was verified end to end against the live database: a brief returns a ranked list in which every creator shows a "
    "score, a range, the basis of each branch and an evidence grade, and every page loads from the same API.")
R.placeholder("Creator Passport page for one creator (YouTube vs Instagram)", "Creator Passport")
R.placeholder("Insights page with the spillover result and method checks", "Insights page")
R.placeholder("Graph explorer with the Ripple view turned on", "Creator graph with the Ripple view")
R.placeholder("Monitoring page with risk alerts", "Monitoring page with brand-safety alerts")
R.section("Discussion")
R.P("The results answer the research questions as follows. For RQ2, a creator's activity on one platform predicts their audience's activity "
    "on the other within one to three days, in both directions, and this cross-platform audience spillover is the main empirical finding. For "
    "RQ1, eleven designs bound spillover between creators to a small size; the strongest design came close to the threshold, and forward "
    "tests with 30-minute readings are measuring new collaborations as they happen. For RQ3, GAIL-R recovered planted effects with a fraction "
    "of the error of published graph models, and its placebo penalty protected it against pre-existing trends. For RQ4, the application "
    "turns these signals into a ranked list in which each score states its range and the evidence behind it.",
    "For brands, the practical message is that a creator's audience should be treated as one audience across platforms: a campaign on "
    "Instagram also reaches the creator's YouTube audience in the following days, so the two platforms should be planned and measured "
    "together.")

# =========================================================================== CHAPTER 11
R.chapter("Conclusion and Future Work")
R.section("Conclusion")
R.P("This project built a complete influencer-brand matching system for Indian fitness and health creators, from daily data collection "
    "to a web application that returns ranked, explained creators for a brand brief. The dataset grew to 651 creators, 184,251 videos, "
    "2.3 million comments and 573,368 time-stamped readings. A six-tier sponsorship detector with an owner check and a standing-code "
    "correction produced reliable labels. GAIL and GAIL-R model spillover on a multi-relational creator graph; GAIL-R, with cross-fitting "
    "and a placebo penalty, recovered planted effects far more accurately than DeepInf, TNet and INFLECT-DGNN. Pre-registered tests detected "
    "cross-platform audience spillover within creators (p = 0.002 and p = 0.014 on 105 creators) and bounded spillover between creators to a "
    "small size. The mood branch, creator-fit branch and fusion layer turn these signals into a 0–100 score with a range and an evidence grade.")
R.section("Utility")
R.bullets(["Brands get a shortlist that is not driven by follower count alone, with the evidence behind each score stated in plain words.",
           "Campaign planners learn that Instagram and YouTube audiences of the same creator respond together within days.",
           "Researchers get a reusable protocol — plan first, placebo, run once — and a benchmark on which the graph models can be compared.",
           "Brand-safety teams get mood scores and alerts that include Hindi-script comments."])
R.section("Work Carried Out Across the Phases")
R.table("Work carried out", ["Phase", "Work"], [
    ["Phases 1 and 2", "Literature review and research gap; problem definition; database schema; first collection (259 creators); GAIL design, "
                       "first training and leave-one-out validation; bot detection; temporal branch with lag tests; fusion layer; first API and dashboard"],
    ["Phase 3 (Aug–Nov 2026)", "Daily collection and 24-month YouTube history; sponsorship tiers and standing-code fix; graph links; GAIL-R and placebo "
                               "penalty; planted-effect benchmark and published baselines; pre-registered spillover study; Creator Passport, Insights, "
                               "graph explorer, redesign and Docker; move to Azure; 642 automated tests"]], [4.0, 13.0])
R.figure(ASSETS / "gantt_v4.png", "Project timeline (Gantt chart)", 16.5)
R.section("Future Work")
R.bullets(["Report the forward collaboration tests with 30-minute readings (20 November 2026) and extend them over a longer period.",
           "Add rate-card data so that creators can be ranked by expected engagement per rupee.",
           "Train GAIL-R on more seeds on a GPU and add the direct effect of sponsored posts as a second target.",
           "Extend Instagram coverage and human label checks, and add load and security testing to the deployment.",
           "Prepare the work as a research paper on cross-platform audience spillover."])

# =========================================================================== REFERENCES
R.unnumbered_chapter("References")
refs = [
    'D. Kempe, J. Kleinberg, and É. Tardos, "Maximizing the spread of influence through a social network," in Proc. ACM SIGKDD, 2003, pp. 137–146.',
    'W. Chen, Y. Wang, and S. Yang, "Efficient influence maximization in social networks," in Proc. ACM SIGKDD, 2009, pp. 199–208, doi: 10.1145/1557019.1557047.',
    'S. Kundu, C. A. Murthy, and S. K. Pal, "A new centrality measure for influence maximization in social networks," in Proc. PReMI, LNCS 6744, 2011, pp. 242–247.',
    'A. Zareie and R. Sakellariou, "Influence maximization in social networks: a survey of behaviour-aware methods," Social Network Analysis and Mining, vol. 13, 2023, doi: 10.1007/s13278-023-01078-9.',
    'Q. Cao, H. Shen, J. Gao, B. Wei, and X. Cheng, "Popularity prediction on social platforms with coupled graph neural networks," in Proc. WSDM, 2020. [Online]. Available: https://arxiv.org/abs/1906.09032',
    'Jin, Liu, and Murata, multi-layer temporal graph neural network for popularity prediction, 2024.',
    'S. Ji et al., "Community-based dynamic graph learning for popularity prediction," in Proc. ACM SIGKDD, 2023, doi: 10.1145/3580305.3599281.',
    'Macro- and micro-level dynamic graph learning for popularity prediction, Springer, 2025.',
    'E. Rossi et al., "Temporal graph networks for deep learning on dynamic graphs," arXiv:2006.10637, 2020.',
    'S. Benslimane, J. Azé, and S. Bringay, text and graph neural network fusion for controversy detection, 2023.',
    'NAH-GNN: a graph-based framework for multi-behavior and high-hop interaction recommendation, 2025. [Online]. Available: https://www.researchgate.net/publication/391278947',
    'Nisa et al., "Optimizing prediction of YouTube video popularity using XGBoost," 2021. [Online]. Available: https://www.researchgate.net/publication/356595714',
    'B. Wu, T. Mei, W.-H. Cheng, and Y. Zhang, "Unfolding temporal dynamics: Predicting social media popularity using multi-scale temporal decomposition," in Proc. AAAI, 2016, doi: 10.5555/3015812.3015852.',
    'Yang, Yang, and Zhang, text summarisation and similarity scoring for brand-celebrity matching, 2022.',
    'GNN-IR: graph neural network link prediction for influencer recommendation, 2024.',
    'L. Tiukhova et al., "INFLECT-DGNN: Influencer prediction with dynamic graph neural networks," IEEE Access, 2024.',
    'S. Kim, J.-Y. Jiang, M. Nakada, J. Han, and W. Wang, "Multimodal post attentive profiling for influencer marketing," in Proc. The Web Conference, 2020, doi: 10.1145/3366423.3380052.',
    'T. Gan et al., "Seeking micro-influencers for brand promotion," in Proc. ACM Multimedia, 2019, doi: 10.1145/3343031.3351080.',
    'ST-GNN: spatio-temporal graph neural network for influence propagation in marketing networks, 2026.',
    'DCHGNN: dynamic heterogeneous graph neural network with a doubly robust estimator for causal effect estimation, 2026.',
    'P. Veličković et al., "Graph attention networks," in Proc. ICLR, 2018.',
    'M. Fey and J. E. Lenssen, "Fast graph representation learning with PyTorch Geometric," in ICLR Workshop on Representation Learning on Graphs and Manifolds, 2019.',
    'J. Qiu, J. Tang, H. Ma, Y. Dong, K. Wang, and J. Tang, "DeepInf: Social influence prediction with deep learning," in Proc. ACM SIGKDD, 2018, pp. 2110–2119.',
    'S. Kim, J.-Y. Jiang, J. Han, and W. Wang, "InfluencerRank: Discovering effective influencers via graph convolutional attentive recurrent neural networks," in Proc. ICWSM, vol. 17, no. 1, 2023, doi: 10.1609/icwsm.v17i1.22162.',
    'M. G. Hudgens and M. E. Halloran, "Toward causal inference with interference," J. Amer. Statist. Assoc., vol. 103, no. 482, pp. 832–842, 2008.',
    'P. R. Rosenbaum and D. B. Rubin, "The central role of the propensity score in observational studies for causal effects," Biometrika, vol. 70, no. 1, pp. 41–55, 1983.',
    'J. M. Robins, A. Rotnitzky, and L. P. Zhao, "Estimation of regression coefficients when some regressors are not always observed," J. Amer. Statist. Assoc., vol. 89, no. 427, pp. 846–866, 1994.',
    'V. Chernozhukov et al., "Double/debiased machine learning for treatment and structural parameters," Econometrics J., vol. 21, no. 1, pp. C1–C68, 2018.',
    'Y. Wu and Y. Yuan, "Estimating heterogeneous causal effect on networks via orthogonal learning," arXiv:2509.18484, 2025.',
    'A. Radford et al., "Learning transferable visual models from natural language supervision," in Proc. ICML, PMLR 139, 2021, pp. 8748–8763.',
    'J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, "BERT: Pre-training of deep bidirectional transformers for language understanding," in Proc. NAACL-HLT, 2019, pp. 4171–4186.',
    'A. Conneau et al., "Unsupervised cross-lingual representation learning at scale," in Proc. ACL, 2020, pp. 8440–8451.',
    'D. Loureiro et al., "TimeLMs: Diachronic language models from Twitter," in Proc. ACL System Demonstrations, 2022.',
    'C. W. J. Granger, "Investigating causal relations by econometric models and cross-spectral methods," Econometrica, vol. 37, no. 3, pp. 424–438, 1969.',
    'X. Nie and S. Wager, "Quasi-oracle estimation of heterogeneous treatment effects," Biometrika, vol. 108, no. 2, pp. 299–319, 2021.',
    'B. Efron and R. J. Tibshirani, An Introduction to the Bootstrap. New York, NY, USA: Chapman & Hall, 1993.',
    'L. Breiman, "Random forests," Machine Learning, vol. 45, no. 1, pp. 5–32, 2001.']
for k, ref in enumerate(refs, 1):
    p = R.para("", align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=4, spacing=1.15)
    pf = p.paragraph_format
    pf.left_indent, pf.first_line_indent = Cm(1.0), Cm(-1.0)
    pf.tab_stops.add_tab_stop(Cm(1.0))
    font(p.add_run(f"[{k}]\t{ref}"), 11)

# =========================================================================== APPENDIX A
R.unnumbered_chapter("Appendix A: User Manual")
R.ch = "A"
R.sec = R.fig = R.tab = 0
R.section("Running the Application")
R.numbered(["Install Docker Desktop, then from the repository root run: docker compose up --build.",
            "Open the frontend address shown by Docker in a browser; the backend health check is at /health.",
            "Without Docker: start the backend with uvicorn app.main:app from the backend folder, and the frontend with npm run dev from the frontend folder."])
R.section("Getting a Recommendation")
R.numbered(["Open Brand input, choose the product category, budget, region, audience and platform, and submit.",
            "Read the ranked list on the Dashboard: the score, its range, the basis badge and the evidence grade (A is best known).",
            "Open a creator's Passport to compare their YouTube and Instagram behaviour; open Explainability to see how the score was built.",
            "Use Insights for the spillover results and the graph explorer; use Monitoring for brand-safety alerts."])
R.placeholder("Home page of the application", "Home page")

# =========================================================================== header / footer from Chapter 1
logo = MEDIA / "pes_logo.jpg"
first = doc.sections[1]
for s in doc.sections[1:]:
    s.different_first_page_header_footer = True
first.header.is_linked_to_previous = False
first.footer.is_linked_to_previous = False
first.first_page_header.is_linked_to_previous = False
first.first_page_footer.is_linked_to_previous = False
for s in doc.sections:   # the draft's section restarted numbering at 1, and every new section copied it
    for old in s._sectPr.findall(qn("w:pgNumType")):
        s._sectPr.remove(old)
pg = OxmlElement("w:pgNumType")
pg.set(qn("w:start"), "1")
first._sectPr.append(pg)

hp = first.header.paragraphs[0]
hp.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
font(hp.add_run(TITLE), 10, italic=True)
hp.add_run("\t")
hp.add_run().add_picture(str(logo), height=Cm(0.9))
bdr = OxmlElement("w:pBdr")
b = OxmlElement("w:bottom")
b.set(qn("w:val"), "single"), b.set(qn("w:sz"), "6"), b.set(qn("w:space"), "1"), b.set(qn("w:color"), "000000")
bdr.append(b)
hp._p.get_or_add_pPr().append(bdr)


def footer(par):
    pf = par.paragraph_format
    pf.tab_stops.add_tab_stop(Cm(TEXT_W / 2), WD_TAB_ALIGNMENT.CENTER)
    pf.tab_stops.add_tab_stop(Cm(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
    font(par.add_run("Dept. of CSE\tAug – Nov 2026\t"), 10)
    run = par.add_run()
    for kind, txt in (("begin", None), (None, " PAGE "), ("separate", None), (None, None), ("end", None)):
        if kind:
            e = OxmlElement("w:fldChar")
            e.set(qn("w:fldCharType"), kind)
            run._r.append(e)
        elif txt:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = txt
            run._r.append(it)
        else:
            t = OxmlElement("w:t")
            t.text = "1"
            run._r.append(t)
    font(run, 10)


footer(first.footer.paragraphs[0])
footer(first.first_page_footer.paragraphs[0])

doc.save(OUT)
print("saved", OUT)
