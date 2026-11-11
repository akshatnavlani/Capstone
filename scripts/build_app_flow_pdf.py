"""Builds the "how the app works" PDF (1 Nov 2026): the pipeline from raw data to the screen, what each piece of code does, and how control passes from one part to the next.
Every code snippet is quoted from the repository; file names and function names are checked against the code on the day it is built (see CHECKS below).

    python scripts/build_app_flow_pdf.py [--out exports/how_the_app_works_1nov.pdf]
"""
import argparse
import html
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "exports" / "how_the_app_works_1nov.pdf"))
OUT = ap.parse_args().out

# Everything named in this document must exist; the build stops if a file or a function name has moved.
CHECKS = {
    "backend/app/main.py": ["on_startup", "include_router"],
    "backend/app/routers/influencers.py": ["get_recommendations", "_to_recommendation", "_keyword_overlap", "_build"],
    "backend/app/spillover.py": ["get_spillover_batch", "unit_rank", "_fallback"],
    "backend/app/temporal.py": ["compute_temporal", "get_temporal_batch"],
    "backend/app/creator_features.py": ["get_feature_scores", "warm_up", "score_query"],
    "backend/app/fusion.py": ["compute_fusion_score", "effective_weights"],
    "backend/app/evidence.py": ["grade_evidence"],
    "backend/app/passport.py": ["clash", "strip", "get_creator"],
    "backend/app/insights.py": ["def build"],
    "backend/app/database.py": ["init_db", "pool_pre_ping"],
    "backend/app/auth.py": ["require_api_key"],
    "ml/inference.py": ["load_predict_batch", "_ensure_loaded", "IsolatedCreatorError"],
    "ml/temporal/propagation.py": ["propagate"],
    "frontend/src/lib/api.ts": ["postRecommendations", "getPassport", "getClash"],
    "frontend/src/lib/useStoredRecommendationResult.ts": ["sessionStorage"],
    "frontend/src/app/brand-input/page.tsx": ["postRecommendations", "sessionStorage.setItem"],
    "scripts/refresh_analyses.py": ["STEPS"],
    "scripts/build_creator_passport.py": ["creator_passport.json"],
    "scripts/compute_creator_embeddings.py": [""],
    "scripts/train_prod_model.py": [""],
    "scripts/build_real_hetero_data.py": [""],
    "scripts/ingestion/instagram_daily.py": [""],
    "scripts/ingestion/label_new_videos.py": [""],
    "scripts/score_creator_sentiment.py": ["temporal_sentiment.json"],
    "scripts/run_power_analysis.py": [""],
    "scripts/run_e4_e5.py": [""],
    "scripts/run_label_noise_sensitivity.py": [""],
    "scripts/run_promotion_behaviour.py": [""],
    "scripts/run_ad_fatigue.py": [""],
    "scripts/run_platform_pairs.py": [""],
    "scripts/passport_stats.py": ["mood_gap", "loo_ridge", "matched_differences"],
    "backend/app/spillover_scenario.py": [""],
    "ml/gail_r_ext.py": [""],
    "ml/semi_synthetic.py": [""],
    "ml/placebo.py": ["placebo_penalty"],
    "scripts/calibrate_fusion.py": [""],
}
for f, names in CHECKS.items():
    text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
    for nm in names:
        if nm not in text:
            sys.exit(f"{f} no longer contains {nm!r}: update this document before building")

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
    "file": ParagraphStyle("file", fontName="Mono", fontSize=8.6, leading=11, textColor=TEAL, spaceAfter=2),
}
story: list = []


def H1(t, new_page=True):
    if new_page:
        story.append(PageBreak())
    story.append(Paragraph(t, S["h1"]))


def H2(t): story.append(Paragraph(t, S["h2"]))
def P(t): story.append(Paragraph(t, S["p"]))
def N(t): story.append(Paragraph(t, S["note"]))
def FILE(t): story.append(Paragraph(html.escape(t), S["file"]))
def B(items): [story.append(Paragraph(i, S["b"], bulletText="•")) for i in items]
def CODE(t): story.append(Paragraph(html.escape(t).replace("\n", "<br/>").replace(" ", "&nbsp;"), S["code"]))


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


class Flow(Flowable):
    """Rows of labelled boxes. Arrows run left to right inside a row and from the last box of a row down to the first box of the next."""

    def __init__(self, rows, width=178 * mm, box_h=15 * mm, gap_y=9 * mm):
        super().__init__()
        self.rows, self.w, self.bh, self.gy = rows, width, box_h, gap_y
        self.height = len(rows) * box_h + (len(rows) - 1) * gap_y

    def wrap(self, aw, ah):
        return self.w, self.height

    def _arrow(self, c, x1, y1, x2, y2):
        c.setStrokeColor(MUTED)
        c.setFillColor(MUTED)
        c.setLineWidth(1)
        c.line(x1, y1, x2, y2)
        if x1 == x2:  # down
            p = c.beginPath()
            p.moveTo(x2, y2)
            p.lineTo(x2 - 1.4 * mm, y2 + 2.4 * mm)
            p.lineTo(x2 + 1.4 * mm, y2 + 2.4 * mm)
        else:  # right
            p = c.beginPath()
            p.moveTo(x2, y2)
            p.lineTo(x2 - 2.4 * mm, y2 + 1.4 * mm)
            p.lineTo(x2 - 2.4 * mm, y2 - 1.4 * mm)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    def draw(self):
        c = self.canv
        centres = []
        for r, row in enumerate(self.rows):
            k = len(row)
            gap = 7 * mm
            bw = (self.w - gap * (k - 1)) / k
            y = self.height - (r + 1) * self.bh - r * self.gy
            row_c = []
            for i, (title, sub) in enumerate(row):
                x = i * (bw + gap)
                c.setFillColor(colors.HexColor("#f6f8fa"))
                c.setStrokeColor(AMBER if r % 2 == 0 else TEAL)
                c.setLineWidth(1.2)
                c.roundRect(x, y, bw, self.bh, 3 * mm, fill=1, stroke=1)
                c.setFillColor(INK)
                c.setFont("Body-Bold", 8.6)
                c.drawCentredString(x + bw / 2, y + self.bh - 5.6 * mm, title)
                c.setFont("Body", 7.2)
                c.setFillColor(MUTED)
                for j, line in enumerate(sub.split("|")):
                    c.drawCentredString(x + bw / 2, y + self.bh - 9.4 * mm - j * 3 * mm, line)
                row_c.append((x, y, bw))
            for i in range(k - 1):
                x, yy, bw_ = row_c[i]
                self._arrow(c, x + bw_, yy + self.bh / 2, row_c[i + 1][0], yy + self.bh / 2)
            centres.append(row_c)
        for r in range(len(self.rows) - 1):  # elbow from the last box of a row to the first box of the next
            x, y, bw = centres[r][-1]
            nx, ny, nbw = centres[r + 1][0]
            mid = y - self.gy / 2
            c.setStrokeColor(MUTED)
            c.setLineWidth(1)
            c.line(x + bw / 2, y, x + bw / 2, mid)
            c.line(x + bw / 2, mid, nx + nbw / 2, mid)
            self._arrow(c, nx + nbw / 2, mid, nx + nbw / 2, ny + self.bh)


# ================================================================================================================================================
story.append(Spacer(1, 26 * mm))
story.append(Paragraph("How the app works", S["title"]))
story.append(Paragraph("The pipeline from raw posts to the screen: what each piece of code does, and how control passes from one part to the next · Project 011 · 1 November 2026", S["sub"]))
story.append(Spacer(1, 4 * mm))
T(["Part", "Question it answers"], [
    ["1", "What is the whole picture, in one page?"],
    ["2", "Offline: how do posts become files the app can use? (collect, label, graph, train, analyse)"],
    ["3", "Online: what happens when the server starts?"],
    ["4", "Online: what happens, step by step, when a brand sends a brief?"],
    ["5", "What does each of the three branches and the fusion do, line by line?"],
    ["6", "What does the browser do with the answer? (dashboard, Passport, Insights, graph)"],
    ["7", "What if something is missing? (fallbacks: the app must never crash)"],
    ["8", "Which file feeds which page? Settings and environment variables"],
    ["9", "How to run it, rerun it, and find the cause when something looks wrong"],
    ["10", "Validation and performance: every check, its code, its result and what it proves"],
    ["11", "The novelties: where each one lives in the pipeline, from script to screen"],
], [18, 150])
N("Every file and function named here was checked to exist when this PDF was built. Code snippets are copied from the repository, shortened only where marked with '...'.")

# ---- 1 ---------------------------------------------------------------------------------------------------------------------------------------
H1("1. The whole picture in one page")
P("The system has <b>two halves</b> that meet at a handful of files and one database.")
B([
    "<b>Offline half (slow, run by us):</b> scripts collect and label data, build the graph, train the models and run the analyses. They <i>write</i> to the database and to files in <font name='Mono'>models/</font>.",
    "<b>Online half (fast, runs when someone uses the app):</b> the backend <i>reads</i> the database and those files and answers requests in a second or two. The website calls the backend.",
])
story.append(Spacer(1, 3 * mm))
H2("Offline half")
story.append(Flow([
    [("Collect", "YouTube, Instagram,|Reddit jobs"), ("Database", "Supabase Postgres"), ("Label", "sponsored? which|brand? (rules)")],
    [("Graph edges", "collab / co-occur /|shared brand"), ("Training inputs", "pairs, features,|outcomes"), ("Train", "GAIL checkpoint|(.pt file)")],
    [("Analyses", "run_*.py: pairs, lag,|event study, power"), ("models/*.json", "result files"), ("Passport build", "creator_passport.json")],
]))
story.append(Spacer(1, 4 * mm))
H2("Online half")
story.append(Flow([
    [("Browser", "brief form"), ("api.ts", "POST /recommendations"), ("FastAPI", "get_recommendations")],
    [("Filters", "budget, platform,|region, product"), ("3 branches", "spillover, mood,|creator fit"), ("Fusion", "score, range,|evidence grade")],
    [("JSON answer", "ranked list"), ("sessionStorage", "kept in the browser"), ("/dashboard", "cards + Passport strip")],
]))
story.append(Spacer(1, 4 * mm))
P("<b>The one rule that holds it together:</b> the online half never trains and never scrapes. It only reads. That is why a request is fast and why a failed training run or a broken scraper cannot break the website.")

# ---- 2 ---------------------------------------------------------------------------------------------------------------------------------------
H1("2. Offline: how posts become something the app can use")
P("Each step below has the same shape: <b>input, what the code does, output</b>. The output of one step is the input of the next, which is what 'control flow' means in this half: a chain of scripts, each leaving files or rows for the next.")
H2("2.1 Collect")
FILE("scripts/ingestion/  (orchestrator.py, instagram_daily.py, reddit_collect.py, youtube_backfill_history.py, ...)")
B([
    "<b>Input:</b> the creator list and API keys from <font name='Mono'>.env</font>.",
    "<b>What it does:</b> YouTube jobs call the YouTube Data API for videos, comments and view counts; a timer reads growth counts every 2 hours; the Instagram job opens each profile page in Chrome through the OpenCLI tool (capped at about 130 page loads a day); Reddit has its own collector. A retry wrapper (db_retry.py) survives a dropped connection.",
    "<b>Output:</b> rows in the database: creators, youtube_videos, youtube_comments, instagram_posts, reddit posts, growth snapshots.",
])
H2("2.2 Label")
FILE("backend/app/labeling.py, scripts/ingestion/label_new_videos.py, known_brands.py, apply_spoken_verdicts.py")
B([
    "<b>Input:</b> raw posts with their descriptions, titles, hashtags, official labels.",
    "<b>What it does:</b> applies the six evidence tiers (official label, spoken sponsor, creator comment, disclosure tag, brand and code, brand name) and writes <font name='Mono'>is_sponsored</font>, the evidence tier and the brand on each post. The 1 Nov fix (standing_code_unflag) runs after this and removes standing affiliate codes.",
    "<b>Output:</b> labelled posts, and the <font name='Mono'>creator_sponsorship_events</font> view that every analysis counts from.",
])
H2("2.3 Build the graph")
FILE("scripts/ingestion/collab_edges.py, populate_edges.py; backend/app/feature_store.py; ml/link_evidence.py")
B([
    "<b>What it does:</b> finds which creators are linked (related accounts, mentions, shared sponsors, co-appearance) and writes them as edges. <font name='Mono'>feature_store.py</font> turns the rows into edge lists with weights, one list per relation.",
    "<b>Output:</b> the edge tables. These feed both the model's graph and the risk-travelling step of the mood branch.",
])
H2("2.4 Features and embeddings (the creator-fit branch)")
FILE("scripts/compute_creator_embeddings.py -> models/creator_embeddings.npz")
P("For every creator it computes CLIP (image and text) and BERT (text) vectors from their thumbnails, bios and captions, and stores them with engagement and reach in one array file. The backend only has to embed the <i>brief</i> and compare.")
H2("2.5 Training inputs and training")
FILE("scripts/build_real_hetero_data.py, scripts/compute_training_pair_deltas.py, scripts/train_prod_model.py, ml/gail_model.py, ml/training.py")
B([
    "<b>Input:</b> graph, creator features and, for each training pair, the engagement before and after a neighbour's sponsorship (the lift).",
    "<b>What it does:</b> builds one graph object (creators as nodes, relations as edge types), then trains GAIL for 100 epochs. The loss has the prediction term plus the causal terms (placebo). It prints nothing for about 20 minutes while it queries the database; that is normal.",
    "<b>Output:</b> a checkpoint file with the weights, the graph, the creator id order and the list of 'trained' creators. The backend loads it through <font name='Mono'>ml/inference.py</font>.",
])
H2("2.6 Sentiment scores")
FILE("scripts/score_creator_sentiment.py (uses ml/temporal/sentiment.py) -> models/temporal_sentiment.json")
P("Each comment gets positive, neutral and negative probabilities (English model, plus a multilingual model for Devanagari). A creator's <b>safety score</b> and comment count are saved to <font name='Mono'>temporal_sentiment.json</font>. The backend reads this file; it does not score comments live.")
H2("2.7 The analyses and the Passport")
FILE("scripts/refresh_analyses.py")
P("One script runs the analyses one after the other and stops if any step fails:")
CODE("""STEPS = [["run_platform_pairs.py"], ["run_ad_fatigue.py"], ["run_long_lag.py", "--placebo", "300"],
         ["run_snapshot_lag.py"], ["run_spillover_event_study.py", "--placebo", "300"],
         ["run_label_noise_sensitivity.py"], ["run_promotion_behaviour.py"],
         ["build_creator_passport.py"], ["export_analysis_dashboard.py"]]""")
P("Each <font name='Mono'>run_*.py</font> reads the database and writes a JSON result into <font name='Mono'>models/</font>. <font name='Mono'>build_creator_passport.py</font> uses the maths in <font name='Mono'>passport_stats.py</font> to write <font name='Mono'>creator_passport.json</font> (one record per creator). "
  "<font name='Mono'>export_analysis_dashboard.py</font> collects the headline numbers for the Analysis tab. The planted-effect simulations (Table B), the power analysis and E4/E5 are run separately and write their own files.")
H2("What the offline half leaves behind")
T(["Output", "Written by", "Read by (online half)"], [
    ["Database tables (creators, posts, events, edges)", "ingestion jobs, labeller", "routers: recommendations, feature-store, platform-profiles, alerts"],
    ["GAIL checkpoint (.pt)", "train_prod_model.py", "ml/inference.py via app/spillover.py"],
    ["models/creator_embeddings.npz", "compute_creator_embeddings.py", "app/creator_features.py"],
    ["models/temporal_sentiment.json", "score_creator_sentiment.py", "app/temporal.py"],
    ["models/creator_passport.json", "build_creator_passport.py", "app/passport.py, app/insights.py"],
    ["models/gail_real_results.json, power_analysis.json, semisynth_*.json, ...", "run_* scripts and simulations", "app/insights.py (Insights page), routers/analysis.py"],
], [60, 52, 66])

# ---- 3 ---------------------------------------------------------------------------------------------------------------------------------------
H1("3. Online: what happens when the server starts")
FILE("backend/app/main.py")
P("Starting the backend (<font name='Mono'>uvicorn app.main:app</font>, or the Docker container) runs this once:")
CODE("""@app.on_event("startup")
def on_startup() -> None:
    init_db()
    from app import creator_features, platform_profile
    creator_features.warm_up()
    platform_profile.warm_up()""")
T(["Step", "What happens", "Why"], [
    ["1", "<b>init_db()</b> creates only our own tables (FusionScore, RiskAlert) on Postgres. On the local SQLite fallback it creates everything", "Tables owned by the ingestion side must never be changed by the API"],
    ["2", "<b>creator_features.warm_up()</b> starts a background thread that loads CLIP and BERT (about a minute)", "Without it the first brief after a restart got the neutral 0.5 for everyone"],
    ["3", "<b>platform_profile.warm_up()</b> prepares the platform-profile data", "Same reason"],
    ["4", "Routers are attached: health, recommendations, ingestion, scores, alerts, feature-store, labeling, analysis, platform-profiles, scenario, passport", "Each router is one group of URLs"],
    ["5", "CORS middleware lets the website (another address) call the API", "Browsers block cross-address calls without it"],
], [14, 100, 64])
P("The GAIL checkpoint is loaded <b>lazily</b>: <font name='Mono'>ml/inference.py</font> keeps it in a module-level cache (<font name='Mono'>_ensure_loaded</font>) and loads it on first use, so a missing checkpoint cannot stop the server from starting.")
CODE("""# app/database.py
pool_kwargs = {} if IS_SQLITE else {"pool_pre_ping": True, "pool_recycle": 300}""")
N("pre-ping tests a connection before using it, and recycle replaces connections older than 5 minutes. Without these, the first request after a quiet period failed with a dead-connection error.")

# ---- 4 ---------------------------------------------------------------------------------------------------------------------------------------
H1("4. Online: a brief travels through the system")
P("This is the main path. Follow the numbers.")
H2("Step 1: the browser sends the brief")
FILE("frontend/src/app/brand-input/page.tsx -> frontend/src/lib/api.ts")
CODE("""const response = await postRecommendations({ ... });          // brand-input/page.tsx
sessionStorage.setItem("recommendationResult", JSON.stringify(response));
router.push("/dashboard");""")
P("<font name='Mono'>postRecommendations</font> does a <font name='Mono'>fetch</font> POST to <font name='Mono'>API_BASE_URL/recommendations</font> (default http://127.0.0.1:8000, set by NEXT_PUBLIC_API_BASE_URL). The page has no shared state with the dashboard, so the answer is parked in the browser's sessionStorage and the page moves on.")
H2("Step 2: FastAPI checks the request")
P("The body is validated against <font name='Mono'>BrandRecommendationRequest</font> (budget, product category, region, demographic, platform preference, max results, include-broader flag). A bad request returns a 422 error; a custom handler makes sure even a NaN in the input cannot crash the error message.")
H2("Step 3: load the candidates")
FILE("backend/app/routers/influencers.py :: get_recommendations")
B([
    "Read up to 1,000 creators plus their YouTube channel and Instagram profile rows.",
    "Work out which creators have any collected posts (<font name='Mono'>data_coverage</font>: youtube+instagram, youtube, instagram, none).",
    "If the database has no creators at all, switch to three built-in demo creators and set <font name='Mono'>is_mock_data</font>, so the screen is never empty in a demo.",
])
H2("Step 4: ask the three branches once, for everyone")
CODE("""spillover_map = get_spillover_batch([c.creator_id for c in creators])   # one GAIL pass, cached
temporal_map  = get_temporal_batch(session)                            # one cached pass
feature_map   = get_feature_scores(request.product_category)           # None until models load""")
P("These are asked <b>once for the whole list</b>, not once per creator. That is why 400 creators answer in about a second.")
H2("Step 5: filter")
T(["Filter", "Kind", "Rule"], [
    ["Budget", "Hard", "estimated cost = reach x 0.5 rupee per follower (a crude placeholder, no real rate cards exist); dropped if above budget. Unknown reach is kept"],
    ["Platform preference", "Hard", "the creator must have a handle on a requested platform (a directly known fact)"],
    ["Region, demographic", "Soft", "dropped only if we HAVE text for the creator and none of the words match. No text means the creator is kept"],
    ["Product category", "Soft", "same rule against category, channel description and bio; failures can be added later as 'broader' matches"],
], [38, 18, 122])
P("<b>Why soft filters?</b> Most creators have little text. A hard rule would return an empty list for almost every query. Matching uses whole words with light stemming (so 'athletic' finds 'athlete'), and long words (6+ letters) may match inside a longer word.")
CODE("""def _stem(word):               # strip one common suffix, twice
    for _ in range(2):
        for suffix in _SUFFIXES:           # ing, ers, er, ies, es, ic, ed, s, e
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[: -len(suffix)]; break
        else: break
    return word""")
H2("Step 6: score each surviving creator")
P("For each creator that passes, <font name='Mono'>_build</font> collects the three branch answers, calls <font name='Mono'>_to_recommendation</font>, and then adds the data coverage and the evidence grade. Part 5 explains what happens inside.")
H2("Step 7: sort, top up, trim")
CODE("""eligible.sort(key=lambda r: (r.data_coverage != "none", r.final_score), reverse=True)
# too few exact matches? top up from creators that failed ONLY the product words,
# ranked by creator-fit relevance, marked product_match="broader"
results = eligible[: request.max_results]""")
P("Creators with no collected data stay in the list but rank below those with data. The response has the query, the results and <font name='Mono'>is_mock_data</font>.")
H2("Step 8: the answer comes back")
P("The JSON goes back to the browser (Step 1), is stored, and the dashboard reads it. The next parts follow it.")

# ---- 5 ---------------------------------------------------------------------------------------------------------------------------------------
H1("5. Inside the scoring: three branches and the fusion")
H2("5.1 Spillover branch (context only)")
FILE("backend/app/spillover.py -> ml/inference.py")
B([
    "<b>get_spillover_batch</b> asks <font name='Mono'>ml.inference.load_predict_batch</font> for every creator in one forward pass of the checkpoint.",
    "Each answer has a <b>basis</b>: <i>trained</i> (the creator was in training), <i>inferred</i> (graph links, but not in training; wider interval), <i>isolated</i> (no links), or <i>placeholder</i> (model not available).",
    "The raw prediction is an unbounded lift, so it is turned into a 0 to 1 <b>percentile</b> among all linked creators (<font name='Mono'>unit_rank</font>): that is what fusion could use.",
    "Since 1 Nov the weight of this branch is 0, so it is shown as context and cannot move the score.",
])
CODE("""def _fallback(creator_id, basis="placeholder"):
    return {"spillover_score": 0.5, "basis": basis,
            "confidence_low": 0.25, "confidence_high": 0.75,
            "spillover_unit": 0.5, "unit_low": 0.025, "unit_high": 0.975}""")
H2("5.2 Mood branch (sentiment, with risk that travels)")
FILE("backend/app/temporal.py :: compute_temporal -> ml/temporal/propagation.py")
B([
    "Load each creator's <b>safety score</b> from <font name='Mono'>temporal_sentiment.json</font> (0 hostile, 1 warm).",
    "The least safe 20% of creators start a <b>risk shock</b>.",
    "The shock <b>spreads along supported links</b> (collaboration, and co-occurrence backed by a post naming both creators), weakening by half each hop, for two hops.",
    "A creator's final mood score is their own safety, lowered by the risk that reached them (strength 0.5). The creator who sent the most risk is recorded as <font name='Mono'>source_creator_id</font>.",
    "Creators with no scored comments get the neutral 0.5 and basis 'placeholder'.",
])
CODE("""A = normalized_adjacency(len(ids), typed_edges, RELATION_WEIGHTS)
M = propagation_matrix(A, alpha=PROPAGATION_ALPHA, hops=PROPAGATION_HOPS)   # 0.5 per hop, 2 hops
propagated = propagate(shock, M)
adjusted = apply_propagated_risk(safety, propagated, beta=PROPAGATION_BETA)  # safety - 0.5 x risk""")
H2("5.3 Creator-fit branch")
FILE("backend/app/creator_features.py :: get_feature_scores")
B([
    "Embed the brief's product text with CLIP and BERT, and compare it (cosine similarity) with every creator's stored image and text vectors, together with engagement and reach.",
    "Results are cached by query text (last 32), so repeating a brief is instant.",
    "If the models are still loading, a request waits up to 60 seconds instead of silently returning 0.5. If the models or file are missing, it returns None and the creator gets the neutral score with basis 'neutral'.",
])
H2("5.4 Fusion")
FILE("backend/app/fusion.py :: compute_fusion_score")
CODE("""w1, w2, w3 = effective_weights(spillover_basis, sentiment_half_width, feature_half_width)
raw_score = w1 * spillover_score + w2 * sentiment_risk_score + w3 * creator_feature_score
base_score = raw_score * 100
risk_adjustment = -10 if sentiment_risk_score < 0.3 else 0.0
final_score = max(0.0, min(100.0, base_score + risk_adjustment))
margin = 100 * sqrt((w1*hw1)**2 + (w2*hw2)**2 + (w3*hw3)**2)    # ranges combined in quadrature""")
B([
    "<b>effective_weights:</b> a branch that knows nothing about this creator (isolated or placeholder spillover, no scored comments, no feature evidence) is left out and the others are scaled up, so nobody is credited with a neutral score that no data supports.",
    "<b>Weights today:</b> spillover 0.0, mood 0.5, creator-fit 0.5 (config.py; overridable with FUSION_WEIGHT_* environment variables, which beat the file).",
    "<b>Range:</b> each branch has its own 95% half-width (the mood one shrinks with more comments: 1.96 x 0.5 / sqrt(n + 20)); the final range is clamped to 0 to 100.",
])
H2("5.5 Evidence grade")
FILE("backend/app/evidence.py :: grade_evidence")
T(["Points", "Condition"], [
    ["Mood 0 to 2", "2 if 200+ scored comments, 1 if 20 to 199, else 0"],
    ["Creator-fit 0 or 2", "2 if scored against the brief with real posts"],
    ["Platforms 0 to 2", "2 for YouTube and Instagram data, 1 for one, 0 for none"],
    ["Spillover 0 or 1", "1 if the creator has graph links (capped at 1 on purpose: no effect was found)"],
    ["Grade", "A at 6 or more, B at 4 to 5, C at 2 to 3, D at 0 to 1. Reasons are returned as plain-language notes"],
], [38, 140])

# ---- 6 ---------------------------------------------------------------------------------------------------------------------------------------
H1("6. What the browser does with the answer")
T(["Page", "Where it gets data", "What it does"], [
    ["/dashboard", "sessionStorage via useStoredRecommendationResult(); then /passport/strip and /passport/clash", "Shows a card per creator: score, range, evidence grade, spillover badge ('context, not scored'), Passport strip; a clash warning if the creator promoted a competing brand recently"],
    ["/passport", "/passport/creators, then /passport/{creator_id}", "One creator across both platforms: mood gap, sponsored response, speed, missing-platform estimate, ad load, clash flag"],
    ["/insights", "/passport/insights (backend/app/insights.py)", "Six interactive charts built from result JSON files. Each block carries its source file name and whether it is simulated"],
    ["/explainability", "/feature-store/edges/*, creators, the stored result", "Draws the creator graph (d3-force) and explains each score"],
    ["/analysis", "/analysis", "The analysis tabs (S1 to S8) read from exported results"],
    ["/monitoring", "/alerts", "Risk alerts raised by the mood branch"],
    ["Home", "none (local)", "The playground: click a creator and an assumed effect fades over three hops. An illustration, labelled so"],
], [30, 62, 86])
H2("A closer look: the Passport strip and the clash warning")
FILE("backend/app/passport.py :: strip, clash;  routers/passport.py")
B([
    "The dashboard sends the ids of the listed creators; <font name='Mono'>strip</font> returns a small summary for each from the cached <font name='Mono'>creator_passport.json</font>.",
    "<font name='Mono'>clash(product)</font> guesses the product's category (<font name='Mono'>infer_category</font>) and lists creators who promoted a brand in that category within 120 days.",
    "The file is cached with its modification time, so rebuilding the Passport shows up without restarting the server.",
    "In the router, the fixed paths (/summary, /insights, /strip, /creators, /clash) are declared <b>before</b> /{creator_id}; otherwise the word 'summary' would be read as a creator id.",
])
H2("A closer look: the Insights page")
P("<font name='Mono'>insights.build()</font> opens several result files (<font name='Mono'>gail_real_results.json</font>, the two <font name='Mono'>semisynth_new_graph_effect*.json</font>, <font name='Mono'>power_analysis.json</font>, <font name='Mono'>creator_passport.json</font>, <font name='Mono'>fusion_simulation.json</font>, the extension results), "
  "reshapes them into chart-sized pieces and returns one JSON. A missing file gives an empty block, not an error. The page then draws the charts as SVG with no chart library.")
H2("How the app avoids confusing a simulation with a finding")
B([
    "Simulation blocks carry <font name='Mono'>simulated: true</font> and the page prints a 'simulation' badge.",
    "The home playground says 'illustration' and 'assumed'.",
    "Spillover appears on cards as 'context, not scored'.",
])

# ---- 7 ---------------------------------------------------------------------------------------------------------------------------------------
H1("7. What if something is missing? Fallbacks")
P("The design rule is: <b>never crash and never fabricate</b>. When a part is missing, the answer gets a neutral value, a wide range, and a label that says why.")
T(["What is missing", "What the code does", "What the user sees"], [
    ["GAIL checkpoint or torch not installed", "spillover.py catches the import error; every creator gets basis 'placeholder', 0.5, wide range", "Spillover marked placeholder; the score is unaffected (weight 0)"],
    ["Creator has no graph links", "IsolatedCreatorError becomes basis 'isolated'", "Isolated badge; the evidence grade gets no spillover point"],
    ["Unknown creator id", "KeyError is also mapped to 'isolated'", "Same"],
    ["CLIP/BERT not loaded or file missing", "get_feature_scores returns None; neutral 0.5; the branch is left out of the weights", "Creator-fit shown as neutral; lower evidence grade"],
    ["temporal_sentiment.json missing", "compute_temporal returns {}; stored score or 0.5", "Mood shown as placeholder"],
    ["No comments for a creator", "Wide range 0.27; the branch is dropped from the weights", "Wider range; note 'no scored comments'"],
    ["Database has no creators", "Three built-in demo creators", "is_mock_data true: the screen says it is demo data"],
    ["Result JSON missing (Insights, Passport)", "Loader returns None; block is empty", "Chart shows an empty state, no error page"],
    ["Dead database connection", "pool_pre_ping, pool_recycle", "No error on the first request after a pause"],
    ["Invalid input (NaN, wrong type)", "422 with a sanitised error body", "A clear validation message"],
    ["Write route without the key", "require_api_key compares the X-API-Key header (off when API_KEY is unset)", "401 error"],
], [48, 74, 56])

# ---- 8 ---------------------------------------------------------------------------------------------------------------------------------------
H1("8. Which file feeds which page, and the settings")
H2("Environment variables and settings")
T(["Setting", "Where", "Effect"], [
    ["DATABASE_URL", "repo-root .env (never printed or committed)", "Postgres address; if unset the backend uses a local SQLite file"],
    ["API_KEY", ".env", "Turns on the X-API-Key check for write routes"],
    ["FUSION_WEIGHT_SPILLOVER / _SENTIMENT_RISK / _CREATOR_FEATURE", ".env or backend/.env", "Override config.py. A stale value there once changed the score; a test pins the defaults"],
    ["CREATOR_FEATURES_DISABLED=1", "environment", "Turns the creator-fit branch off (tests use it)"],
    ["CORS_ALLOW_ORIGINS", ".env", "Which website addresses may call the API"],
    ["NEXT_PUBLIC_API_BASE_URL", "frontend env", "Where the website finds the API (default http://127.0.0.1:8000)"],
], [60, 50, 68])
H2("Chain from a data change to a screen change")
T(["If this changes...", "...rerun this...", "...and this page changes"], [
    ["New posts or labels in the database", "nothing (read live); then refresh_analyses.py for analyses", "dashboard ranking at once; Insights after the rerun"],
    ["Label rules or the standing-code fix", "refresh_analyses.py (and retrain if training data changes)", "Passport, Insights, Analysis"],
    ["Comments re-scored", "score_creator_sentiment.py", "mood score, risk alerts, grade"],
    ["Creator images or text", "compute_creator_embeddings.py", "creator-fit score"],
    ["New GAIL checkpoint", "replace the checkpoint file; restart the backend", "spillover context on cards"],
    ["Fusion weights", "config.py or the FUSION_WEIGHT_* variables; restart", "every score"],
    ["Passport rebuilt", "build_creator_passport.py", "Passport and Insights, no restart (cached by modified time)"],
], [58, 66, 54])

# ---- 9 ---------------------------------------------------------------------------------------------------------------------------------------
H1("9. How to run it, rerun it, and find a problem")
H2("Run")
CODE("""# backend (from the repo root, venv active)
cd backend
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm run dev                 # http://localhost:3000

# or both in containers
docker compose up --build""")
H2("Rerun the analyses and rebuild")
CODE("""python scripts/refresh_analyses.py            # every analysis, the Passport and the dashboard export
python scripts/build_creator_passport.py      # just the Passport
python scripts/simulate_fusion.py             # the fusion design simulation
python scripts/build_paper_comparison.py      # the results pack, from the result files
python scripts/build_team_pdf.py              # the team guide
python scripts/build_app_flow_pdf.py          # this document""")
H2("Where to look when something is wrong")
T(["Symptom", "Most likely cause", "Look here"], [
    ["Every score is the same or looks neutral", "Creator-fit models not loaded yet, or the file is missing", "backend log 'creator feature score ready'; models/creator_embeddings.npz"],
    ["Scores differ from yesterday with no data change", "A FUSION_WEIGHT_* environment variable overrides config.py", ".env and backend/.env; tests/test_fusion_calibration.py"],
    ["Spillover shows 'placeholder' for everyone", "Checkpoint or torch missing", "backend log 'GAIL inference unavailable'; ml/inference.py"],
    ["First request after a pause returns 500", "Dead database connection", "app/database.py pool settings"],
    ["Browser shows a network or CORS error", "Backend not running, or the site address is not allowed", "CORS_ALLOW_ORIGINS; NEXT_PUBLIC_API_BASE_URL"],
    ["Dashboard says there is no result", "sessionStorage was cleared (new tab or window)", "Submit the brief again"],
    ["Insights chart empty", "A result file is missing", "models/*.json named in /passport/insights 'source' fields"],
    ["Training seems stuck", "It prints nothing for about 20 minutes while querying the database", "wait; check the process is still running"],
    ["Analysis rerun stopped", "A step failed; later steps are skipped by design", "the last line printed by refresh_analyses.py"],
    ["Everything freezes while running jobs", "Docker's virtual machine plus heavy jobs exhaust memory", "run heavy jobs one at a time; stop Docker first"],
], [56, 62, 60])
H2("The one-minute story to tell a panel")
P("<i>Scripts collect and label public data and train the models offline. Those steps write rows and files. When a brand submits a brief, the backend reads them, asks three branches for a score, fuses them with documented weights into a score with a range and an evidence grade, and sends back a ranked list. "
  "The website keeps that answer in the browser and draws the cards, the Passport and the evidence charts. If a part is missing the system gives a neutral value with a label instead of failing.</i>")


# ---- 10 --------------------------------------------------------------------------------------------------------------------------------------
import json as _json
import statistics as _st

_J = lambda n: _json.loads((ROOT / "models" / n).read_text(encoding="utf-8"))  # noqa: E731
_t8, _multi, _hold, _pow = _J("gail_training_summary_1nov.json"), _J("gail_r_multiseed.json"), _J("gail_r_holdout.json"), _J("power_analysis.json")
_b1, _b0 = _J("semisynth_new_graph_effect1.json"), _J("semisynth_new_graph_effect0.json")
_rank, _sent, _xlm = _J("ranking_test.json"), _J("sentiment_check_claude_labels.json"), _J("sentiment_check_claude_labels_twitter-xlm-roberta-base-sentiment.json")
_noise, _fcal, _hing, _link = _J("label_noise_sensitivity.json"), _J("fusion_calibration.json"), _J("hinglish_check.json"), _J("link_audit.json")
_ps, _evs, _snap, _e45, _base = _J("creator_passport.json")["summary"], _J("spillover_event_study.json"), _J("snapshot_lag.json"), _J("e4_e5_results.json"), _J("published_baselines_eesha.json")
_pairs, _fat, _promo, _lag = _J("platform_pairs.json"), _J("ad_fatigue.json"), _J("promotion_behaviour.json"), _J("long_lag.json")
_mrow = _multi["runs"]["with placebo penalty (30)"]
_ate = lambda block, key: _st.mean(r["ate_error"] for r in block[key] if isinstance(r, dict) and r.get("ate_error") is not None)  # noqa: E731
_f2 = lambda v: f"{v:+.2f}"  # noqa: E731
_noise30 = next((r for r in _noise["rows"] if abs(r["share_of_comparison_group_truly_exposed"] - 0.30) < 1e-9), None)
_sr = _ps["sponsored_response"]
_ig_up = next(r for r in _lag["results"] if r["name"].startswith("ig_to_uploads"))
_detected = sum(1 for r in _evs["results"] if r.get("detected_after_correction"))

H1("10. Validation and performance: how we check each part works")
P("A system that gives a number needs a second system that checks the number. This part lists every check, where its code lives, what it returned, and what that does and does not prove. "
  "Every figure is read from the result file named in the last column.")
H2("The metrics, in plain words")
T(["Metric", "Meaning", "How to read it"], [
    ["Error / MSE", "Average (squared) distance between prediction and truth", "Lower is better. Meaningful only against a baseline such as 'always predict zero'"],
    ["AUC", "Chance that the model puts a random positive case above a random negative one", "0.5 is a coin flip, 1.0 is perfect"],
    ["Spearman correlation", "Do two rankings agree? (-1 to +1)", "0 means unrelated; sign tells direction"],
    ["95% interval", "Range that would hold the true value 95 times in 100 if the method is right", "If it contains 0, the effect cannot be told apart from nothing"],
    ["Precision at 10", "Share of the top 10 picks that are truly good", "Compare with the 'random' value, not with 1.0"],
    ["nDCG at 10", "Like precision, but a good pick at rank 1 counts more than at rank 10", "Compare with random"],
    ["Power", "Chance of noticing an effect of a given size when it exists", "Tells you what a null result can rule out"],
    ["Placebo error", "What the method 'finds' where nothing can exist", "Should be near zero; it is the false-alarm test"],
], [34, 74, 70])

H2("10.1 The spillover model and its tests")
T(["Check", "Code", "Result", "Reading", "File"], [
    ["GAIL v1 training error", "scripts/train_prod_model.py", f"{_t8['training']['mse_trained']:.4f} vs {_t8['training']['mse_baseline_always_zero']:.4f} for always-zero ({_t8['training']['improvement_percent']}% better), {_t8['training']['observations']} observations", "In-sample only: shows it learned, not that it generalises", "gail_training_summary_1nov.json"],
    ["GAIL-R on real data", "scripts/gail_r_multiseed.py; ml/gail_r.py", f"single fit {_f2(_t8['gail_r']['effect_on_exposed'])} ({_f2(_t8['gail_r']['ci95'][0])} to {_f2(_t8['gail_r']['ci95'][1])}); ten seeds average {_f2(_mrow['att_mean'])}", "No detectable spillover", "gail_r_multiseed.json"],
    ["Held-out creators", "scripts/gail_r_holdout.py", f"{_hold['folds']} folds x {_hold['repeats']} repeats on {_hold['creators']} creators: median gain {100 * _hold['gain_median']:.1f}% (wrong-window control {100 * _hold['null_gain_median']:.1f}%)", "The spillover term does not help on unseen creators", "gail_r_holdout.json"],
    ["Category-matched DiD", "scripts/run_spillover_*.py", f"{_f2(_t8['category_matched_did']['estimate'])} (SE {_t8['category_matched_did']['se']:.2f})", "Null", "gail_training_summary_1nov.json"],
    ["Placebo pre-trend DiD", "ml/placebo.py", f"{_f2(_t8['placebo_pre_trend_did']['estimate'])} (SE {_t8['placebo_pre_trend_did']['se']:.2f})", "Plain comparison is confounded; this is why GAIL-R has the penalty", "gail_training_summary_1nov.json"],
    ["Event study (hourly readings and comments)", "scripts/run_spillover_event_study.py", f"{_detected} of {len(_evs['results'])} tests detected after correction", "Null; each test has a placebo and a positive control", "spillover_event_study.json"],
    ["Lag test Instagram to YouTube views", "scripts/run_snapshot_lag.py", f"smallest p = {next(r for r in _snap['results'] if r['name'].startswith('ig_to_yt:'))['smallest_p_after_event']} vs bar 0.0125", "Not detected; control upload-to-views is", "snapshot_lag.json"],
    ["Label noise", "scripts/run_label_noise_sensitivity.py", (f"if 30% of the comparison group were truly exposed, the upper end is about {_noise30['upper_bound_as_engagement_ratio']}x engagement" if _noise30 else "see file"), "Answer does not depend on a few wrong labels", "label_noise_sensitivity.json"],
], [32, 38, 52, 38, 36])
H2("Power: what a null can rule out")
P("We keep the real outcomes and plant an effect of a chosen size, then count how often the test finds it. Each row is a number of exposed observations; each column a planted effect size.")
_eff = _pow["deltas"] if isinstance(_pow.get("deltas"), list) and len(_pow["deltas"]) == 6 else [0.0, 0.25, 0.5, 0.75, 1.0, 1.5]
T(["Exposed observations"] + [f"effect {e:g}" for e in _eff], [[k] + [f"{100 * v:.0f}%" for v in vals] for k, vals in _pow["real_structure"]["share_detected"].items()], [40, 23, 23, 23, 23, 23, 23])
N(f"The real data has {_pow['real_exposed']} exposed observations. The 'effect 0' column is the false-alarm rate and should be about 5% or less.")

H2("10.2 Is the method itself trustworthy? (planted effect, known truth)")
_cols = [("effect 1.0, clean", _b1["clean"]), ("effect 1.0, trend", _b1["pretrend"]), ("no effect, clean", _b0["clean"]), ("no effect, trend", _b0["pretrend"])]
_meth = [("Naive difference", "Naive difference"), ("GNN predictor (no causal training)", "GNN predictor (no causal training)"), ("Doubly robust, no graph", "DR, no graph"), ("GAIL v1", "GAIL v1 (current)"), ("GAIL-R", "GAIL-R"), ("GAIL-R + placebo", "GAIL-R + placebo")]
T(["Method (average error, lower is better)"] + [c for c, _ in _cols], [[m] + [f"{_ate(b, k):.3f}" for _, b in _cols] for m, k in _meth], [58, 30, 30, 30, 30])
P("Reading: only GAIL-R with the placebo penalty stays accurate in all four settings. Table B2 (published models Eesha ran, 390-creator graph, 3 replicates) is separate:")
T(["Method", "No trend", "Planted trend"], [[r["method"], f"{r['no_trend']:.3f}", f"{r['pre_trend']:.3f}"] for r in _base["rows"]], [90, 40, 48])
P(f"<b>E4 and E5 (simulated):</b> E4's causal supervision gives per-creator error {_e45['e4_simulated']['clean, causal supervision, shrink 100']['pehe']['mean']:.2f} against {_e45['e4_simulated']['clean, plain supervision, shrink 100']['pehe']['mean']:.2f} for plain supervision; E5 recovers the effect when labels are missed. Both are simulations.")

H2("10.3 The ranking: does it predict anything?")
P(f"We tested whether simple predictors, measured before 1 Jan 2026, rank {_rank['creators']} creators by what a sponsored video later did to their views. None is distinguishable from chance:")
T(["Predictor", "Spearman", "95% interval", "Precision at 10", "Random"], [[k, f"{v['spearman']:+.2f}", f"{v['spearman_ci95'][0]:+.2f} to {v['spearman_ci95'][1]:+.2f}", f"{v['precision_at_10']:.2f}", f"{v['precision_at_10_random']:.2f}"] for k, v in _rank["methods"].items()], [60, 22, 40, 28, 28])
N("Every interval contains zero. This is why we never claim the ranking predicts campaign results: no sales data exists and no simple predictor beats chance on the outcome we can measure.")
_lab = _fcal["labelled_outcomes"]
P(f"<b>Fusion calibration.</b> Only {_lab} creators have a labelled outcome, so the fusion weights cannot be fitted; scripts/calibrate_fusion.py instead measures how much the ranking moves when weights change, and the typical range on a 0 to 100 score is about {_fcal['ci_width_points']['median']:.0f} points wide (between {_fcal['ci_width_points']['min']:.0f} and {_fcal['ci_width_points']['max']:.0f} across {_fcal['creators']} creators). "
  "That wide range is the honest statement of how little a score can say.")

H2("10.4 The mood branch and the creator-fit branch")
_rows = []
for lang in ("english", "hinglish", "devanagari"):
    _rows.append([lang.capitalize(), f"{_sent[lang]['n']}", f"AUC {_sent[lang]['auc_positive_vs_rest']:.2f}, Spearman {_sent[lang]['spearman_with_label_value']:+.2f}", f"AUC {_xlm[lang]['auc_positive_vs_rest']:.2f}, Spearman {_xlm[lang]['spearman_with_label_value']:+.2f}"])
T(["Comment language", "Comments", "English model (roberta)", "Multilingual model (XLM-R)"], _rows, [40, 24, 58, 58])
B([
    "These 120 labels were written by an AI model, not a person: say 'AI-labelled'. The routing rule (Devanagari goes to XLM-R) comes from this table.",
    f"A separate human check of 24 Hinglish comments gave AUC {_hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['auc_pos_vs_neg']:.2f}, Spearman {_hing['models']['cardiffnlp/twitter-roberta-base-sentiment-latest']['spearman']:.2f}. Rough: one labeller.",
    "Creator fit: ranking quality (AUC) 0.85 for a fitness brief and 0.57 for a cricket brief, mean 0.71 (the S2 measurement quoted in app/fusion.py). It is used with a wide range.",
])
H2("10.5 Links and filters")
B([
    f"<b>Cross-platform links (S8 audit):</b> {_link['youtube']['links']} YouTube-to-Instagram links; {_link['youtube']['evidence']['corroborated (Instagram handle in channel description)']} corroborated by the channel description, {_link['youtube']['evidence']['name match']} by name, "
    f"{_link['youtube']['evidence']['same handle text on both platforms (weak: fan accounts reuse handles)']} weak, {_link['youtube']['evidence']['NO AUTOMATIC EVIDENCE']} with no automatic evidence (flagged for hand check).",
    "<b>Filters (S7 audit):</b> measured how many creators each filter removes under several cost assumptions; fixed the region and product-word matching (whole words, light stemming, Indian country codes). Only the demo query's counts are in the file (models/filter_cost_audit.json).",
])
H2("10.6 Engineering checks")
B([
    "Tests at the last full run (1 Nov): machine learning 340, backend 142, ingestion 126, plus the frontend production build. A test pins the fusion weights; another pins that spillover cannot move the score.",
    "Canary checks (pair-count canary, short-query canary) run in the gate script and fail loudly if a key number changes.",
    "The standing-affiliate-code script reports before it changes anything, backs up first, and has an undo.",
])

# ---- 11 --------------------------------------------------------------------------------------------------------------------------------------
H1("11. The novelties: where each one lives in the pipeline")
P("For each novelty: the script that computes it (offline), the file it leaves behind, how the backend serves it, where the app shows it, and how we validated it. This is the same chain as in parts 2 to 6, followed for one idea at a time.")
T(["Novelty", "Computed by (offline)", "Left behind", "Served by (online)", "Shown in the app", "Checked by / result"], [
    ["Same creator YouTube vs Instagram within 24 h", "scripts/run_platform_pairs.py", "models/platform_pairs.json", "routers/analysis.py (through analysis_dashboard.json, written by export_analysis_dashboard.py)", "Analysis tab", f"{_pairs['pairs']} pairs; placebo alone {_f2(_pairs['placebo']['median_difference_placebo'])}; adjusted gap {_f2(_pairs['median_difference_adjusted'])}"],
    ["Lag between platforms", "run_long_lag.py, run_snapshot_lag.py", "long_lag.json, snapshot_lag.json", "routers/analysis.py (through analysis_dashboard.json)", "Analysis tab", f"Instagram to upload p {_ig_up['smallest_p_after_event']}; control detected; Bonferroni 0.0125"],
    ["Sponsored response by platform", "scripts/build_creator_passport.py using passport_stats.matched_differences", "creator_passport.json", "app/passport.py (strip, get_creator)", "Passport page", f"YouTube views {_sr['youtube_views'].get('approx_percent', 0):+.1f}%; fake-sponsored placebo as control"],
    ["Missing-platform estimate", "passport_stats.loo_ridge", "creator_passport.json", "app/passport.py", "Passport page (as a range)", f"rank agreement {_ps['prediction']['spearman_full']:.2f} vs {_ps['prediction']['spearman_size_only']:.2f} size-only ({_ps['prediction']['n']} creators)"],
    ["Mood gap", "passport_stats.mood_gap (worst-case error)", "creator_passport.json", "app/passport.py", "Passport page", f"{_ps['mood_gap']['flagged']} of {_ps['mood_gap']['creators_with_both']} flagged"],
    ["Attention speed", "build_creator_passport.py", "creator_passport.json", "app/passport.py", "Passport page; Insights (passport block)", f"median {100 * _ps['speed']['median_share_first_24h']:.0f}% of week-one views in 24 h"],
    ["Ad fatigue", "scripts/run_ad_fatigue.py", "ad_fatigue.json", "routers/analysis.py (through analysis_dashboard.json)", "Analysis tab", f"slope {_fat['results'][0]['median_slope']:+.3f}: not detected"],
    ["Disclosure and buying signals", "scripts/run_promotion_behaviour.py (uses purchase_intent.py)", "promotion_behaviour.json", "routers/analysis.py (through analysis_dashboard.json)", "Analysis tab", f"{100 * _promo['disclosure']['share_disclosed_overall']:.0f}% disclosed; buying comments {_promo['response']['median_ratio']:.1f}x on sponsored (keyword proxy)"],
    ["Competitor-clash flag", "build_creator_passport.py (brands and dates per creator)", "creator_passport.json", "app/passport.py :: clash; GET /passport/clash", "Dashboard cards", f"{_ps['clash']['creators_with_recent_brand_posts']} creators promoted a brand in {_ps['clash']['window_days']} days (a warning, not a finding)"],
    ["Creator Passport", "build_creator_passport.py", "creator_passport.json", "routers/passport.py", "Passport page, Passport strip on cards", "tests/test_passport.py, test_passport_stats.py"],
    ["Evidence grade A to D", "(none: computed per request)", "(none)", "app/evidence.py :: grade_evidence, called in /recommendations", "Cards: grade badge and reasons", "Rule-based; thresholds are judgement"],
    ["Evidence-weighted fusion", "(none: per request)", "(none)", "app/fusion.py :: effective_weights", "Score breakdown", "Test: a branch with no data is left out"],
    ["What-if spillover tool", "(none: per request)", "(none)", "app/spillover_scenario.py, GET /scenario/spillover", "Dashboard (what-if control)", "Labelled as an assumption; the home playground is a separate illustration"],
    ["Placebo penalty and planted-effect validation", "ml/placebo.py, ml/semi_synthetic.py, scripts/run_*", "semisynth_new_graph_effect*.json", "app/insights.py", "Insights page (benchmark chart)", f"GAIL-R + placebo error at most {max(_ate(s, 'GAIL-R + placebo') for s in (_b1['clean'], _b1['pretrend'], _b0['clean'], _b0['pretrend'])):.3f} in all four settings"],
    ["Power analysis", "scripts/run_power_analysis.py", "power_analysis.json", "app/insights.py", "Insights page (power chart)", "Part 10.1"],
    ["E4 causal attention, E5 missed-label correction", "ml/gail_r_ext.py, scripts/run_e4_e5.py", "e4_e5_results.json", "app/insights.py", "Insights page", "Simulation only"],
    ["Standing-affiliate-code fix", "scripts/ingestion/standing_code_unflag_20261101.py", "database (backup tables, --undo)", "(changes what every route reads)", "Everything downstream", "470 videos of 17 creators; report-only mode before applying"],
    ["Hinglish check", "scripts/make_hinglish_sample.py, score_hinglish_sample.py", "hinglish_check.json", "(not served: used in the documents)", "Not in the app", "24 hand labels; rough"],
    ["One definition of a training pair", "scripts/ingestion/pair_count.py", "pair_count_snapshot.json", "(used by training and the canary)", "None directly", "Canary fails if the count moves"],
], [26, 30, 24, 28, 26, 44])
P("<b>How to explain this in one breath.</b> Every novelty follows the same path: a script computes it from the database, leaves a JSON file, a small backend module reads that file (cached), and a page shows it with its limit next to it. "
  "That is why a rerun of <font name='Mono'>refresh_analyses.py</font> is enough to refresh every novelty in the app without restarting anything.")


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Body", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "How the app works · Project 011 · 1 November 2026")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


SimpleDocTemplate(OUT, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=18 * mm, title="How the app works", author="Team Project 011").build(story, onFirstPage=footer, onLaterPages=footer)
print("saved", OUT)
