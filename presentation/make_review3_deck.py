"""Fills the college template (presentation/template_review3.pptx, "Project Progress Review #3") with the project content -> presentation/Review3_Presentation.pptx.

    python presentation/make_review3_deck.py            (needs python-pptx and Pillow)

The template's own slides, titles, teal rule, fonts (Trebuchet MS) and colours (red titles, blue text) are kept. Slides are only added where the template allows more than one:
architecture (max 2), implementation (max 4), test plan (max 2), results (max 2). Numbers come from models/*.json or from figures checked against the live database on 27 Oct 2026.
Fields the repository cannot know are written as [to fill: ...] so they are easy to find.
"""
import copy
import json
import math
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "presentation" / "template_review3.pptx"
OUT = ROOT / "presentation" / "Review3_Presentation.pptx"
ASSETS = ROOT / "presentation" / "assets"
M = ROOT / "models"

BLUE, TEAL, RED, INK, GRAY, TINT, WHITE, AMBER = "0033CC", "33CCCC", "FF0000", "1B1B1B", "5E6C73", "E8EEFB", "FFFFFF", "FF9900"
FONT, MONO = "Trebuchet MS", "Consolas"
WARN = []


def load(name):
    return json.loads((M / name).read_text(encoding="utf-8"))


SEMI, LAGP, QUAL = load("sim_semisynthetic_benchmark.json"), load("sim_lag_power.json"), load("sponsorship_quality.json")
PLACEBO = load("spillover_placebo_test.json")["scopes"]["in_the_150"]["all"]["per_neighbour"]
DIRECT = load("direct_effect.json")["results"]["youtube/views/all_events"]["sponsored_posts"]
DOSE = load("spillover_dose.json")
SENT_EN, SENT_ML = load("sentiment_check_claude_labels.json"), load("sentiment_check_claude_labels_twitter-xlm-roberta-base-sentiment.json")
RANK = load("ranking_test.json")

prs = Presentation(str(TEMPLATE))
BLANK = prs.slide_layouts[6]
S = list(prs.slides)                      # the 13 template slides, by number - 1
order = []                                # final order of slide objects
cur_page = {"n": 0}


def rgb(h):
    return RGBColor.from_string(h)


def rm(shape):
    shape._element.getparent().remove(shape._element)


def est_lines(text, w_in, size, mono=False):
    cpl = max(int(w_in / (size * (0.60 if mono else 0.56) / 72)), 1)       # Trebuchet is wider than Calibri
    return sum(max(math.ceil(len(part) / cpl), 1) for part in text.split("\n"))


def add_text(s, x, y, w, h, items, size=15, color=BLUE, bullets=False, font=FONT, align=PP_ALIGN.LEFT, space=4, anchor=MSO_ANCHOR.TOP, name="text", bold=False, margin=0.0):
    """items: str | list of str | list of runs [(text, {bold, color, size})]. bullets use the template's Wingdings square."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = anchor
    items = [items] if isinstance(items, str) else items
    need = 0.0
    mono = font == MONO
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space)
        runs = [(it, {})] if isinstance(it, str) else it
        plain = "".join(t for t, _ in runs)
        for t, o in runs:
            r = p.add_run()
            r.text = t
            r.font.name = o.get("font", font)
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.color.rgb = rgb(o.get("color", color))
        if bullets:
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(int(Inches(0.3))))
            pPr.set("indent", str(-int(Inches(0.3))))
            bf = etree.SubElement(pPr, qn("a:buFont"))
            bf.set("typeface", "Wingdings")
            bf.set("pitchFamily", "2")
            bf.set("charset", "2")
            bc = etree.SubElement(pPr, qn("a:buChar"))
            bc.set("char", "§")
        need += est_lines(plain, w - (0.3 if bullets else 0), size, mono) * size * 1.2 / 72 + space / 72
    if need > h + 0.05:
        WARN.append(f"slide {cur_page['n']} '{name}': about {need:.2f} in needed, box is {h:.2f} in")
    return tb


def add_box(s, x, y, w, h, fill=TINT, line=None, name="box", radius=0.05):
    r = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    r.name = name
    r.adjustments[0] = radius
    r.fill.solid()
    r.fill.fore_color.rgb = rgb(fill)
    if line:
        r.line.color.rgb = rgb(line)
        r.line.width = Pt(1.25)
    else:
        r.line.fill.background()
    r.shadow.inherit = False
    return r


def code_box(s, x, y, w, h, lines, size=11):
    add_box(s, x, y, w, h, fill="F4F6FA", line="B8C4E0", name="code box", radius=0.03)
    add_text(s, x + 0.15, y + 0.12, w - 0.3, h - 0.2, lines, size=size, color="1B1B1B", font=MONO, space=0, name="pseudocode")


def tag(s, text, x=10.0, y=2.0, w=2.6, color=RED):
    add_box(s, x, y, w, 0.36, fill="FFF1F1" if color == RED else TINT, line=color, name="tag")
    add_text(s, x, y + 0.06, w, 0.26, text, size=12, bold=True, color=color, align=PP_ALIGN.CENTER, name="tag text")


def table(s, x, y, w, rows, col_w, size=12, row_h=0.45, name="table"):
    gf = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
    gf.name = name
    tb = gf.table
    tblPr = tb._tbl.tblPr
    tblPr.set("firstRow", "1")
    tblPr.set("bandRow", "0")
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is not None:
        sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"
    for j, cw in enumerate(col_w):
        tb.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        tb.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = tb.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.08)
            c.margin_top = c.margin_bottom = Inches(0.04)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid()
            c.fill.fore_color.rgb = rgb(BLUE if i == 0 else (TINT if i % 2 else WHITE))
            p = c.text_frame.paragraphs[0]
            c.text_frame.word_wrap = True
            r = p.add_run()
            r.text = str(val)
            r.font.name, r.font.size = FONT, Pt(size)
            r.font.bold = i == 0 or j == 0
            r.font.color.rgb = rgb(WHITE if i == 0 else INK)
            if est_lines(str(val), col_w[j] - 0.16, size) * size * 1.2 / 72 + 0.08 > row_h + 0.03:
                WARN.append(f"slide {cur_page['n']} {name} r{i}c{j}: '{str(val)[:30]}' may not fit a {row_h:.2f} in row")
    return tb


def style_chart(ch, size=11):
    ch.font.size = Pt(size)
    ch.font.name = FONT
    ch.font.color.rgb = rgb(INK)


def bar_chart(s, x, y, w, h, cats, series, colors, number_format="0", maxv=None, title=None, horizontal=False, legend=False, point_colors=None):
    cd = CategoryChartData()
    cd.categories = cats
    for nm, vals in series:
        cd.add_series(nm, vals)
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    gf.name = "chart"
    ch = gf.chart
    style_chart(ch)
    ch.has_title = bool(title)
    if title:
        ch.chart_title.text_frame.text = title
        run = ch.chart_title.text_frame.paragraphs[0].runs[0]
        run.font.size, run.font.bold, run.font.name = Pt(12), True, FONT
        run.font.color.rgb = rgb(BLUE)
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(11)
    plot = ch.plots[0]
    plot.gap_width = 55
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.font.size, dl.font.bold = Pt(11), True
    dl.number_format, dl.number_format_is_linked = number_format, False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    if horizontal:
        ch.category_axis.reverse_order = True
    va = ch.value_axis
    va.major_gridlines.format.line.color.rgb = rgb("DDE3F0")
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(10)
    va.tick_labels.font.color.rgb = rgb(GRAY)
    va.minimum_scale = 0
    if maxv:
        va.maximum_scale = maxv
    ch.category_axis.tick_labels.font.size = Pt(10)
    for i, ser in enumerate(plot.series):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = rgb(colors[i % len(colors)])
        if point_colors and i == 0:
            for j, c in enumerate(point_colors):
                pt = ser.points[j]
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = rgb(c)
    return ch


def line_chart(s, x, y, w, h, cats, series, colors, title=None, label_series=1):
    cd = CategoryChartData()
    cd.categories = cats
    for nm, vals in series:
        cd.add_series(nm, vals)
    gf = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    gf.name = "chart"
    ch = gf.chart
    style_chart(ch)
    ch.has_title = bool(title)
    if title:
        ch.chart_title.text_frame.text = title
        run = ch.chart_title.text_frame.paragraphs[0].runs[0]
        run.font.size, run.font.bold, run.font.name = Pt(12), True, FONT
        run.font.color.rgb = rgb(BLUE)
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(11)
    va = ch.value_axis
    va.maximum_scale, va.minimum_scale = 105, 0
    va.major_gridlines.format.line.color.rgb = rgb("DDE3F0")
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(10)
    ch.category_axis.tick_labels.font.size = Pt(10)
    for i, ser in enumerate(ch.plots[0].series):
        ser.format.line.color.rgb = rgb(colors[i])
        ser.format.line.width = Pt(2.75)
        ser.smooth = False
        ser.marker.format.fill.solid()
        ser.marker.format.fill.fore_color.rgb = rgb(colors[i])
        ser.marker.format.line.color.rgb = rgb(colors[i])
    lab = ch.plots[0].series[label_series].data_labels
    lab.show_value, lab.number_format, lab.number_format_is_linked = True, '0"%"', False
    lab.font.size, lab.font.bold = Pt(11), True
    lab.position = XL_LABEL_POSITION.BELOW
    return ch


def picture(s, path, x, y, w=None, h=None):
    kw = {"width": Inches(w)} if w else {"height": Inches(h)}
    pic = s.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)
    pic.name = "picture"
    pic.line.color.rgb = rgb("B8C4E0")
    pic.line.width = Pt(1)
    return pic


def clear_body(slide, keep_titles):
    """Remove every shape of a template slide except the teal rule and the red title box."""
    for sh in list(slide.shapes):
        is_rule = sh.shape_type == 1 and sh.height < Inches(0.1)
        is_title = sh.has_text_frame and sh.text_frame.text.strip() in keep_titles
        if not (is_rule or is_title):
            rm(sh)


def clone_frame(src, title):
    """A new slide on the template's Blank layout with the same teal rule and a red title box as `src`."""
    s = prs.slides.add_slide(BLANK)
    for sh in list(s.shapes):
        rm(sh)
    for sh in src.shapes:
        if (sh.shape_type == 1 and sh.height < Inches(0.1)) or (sh.has_text_frame and sh.text_frame.paragraphs and sh.text_frame.paragraphs[0].runs
                                                                  and str(sh.text_frame.paragraphs[0].runs[0].font.color.rgb if sh.text_frame.paragraphs[0].runs[0].font.color and sh.text_frame.paragraphs[0].runs[0].font.color.type else "") == RED
                                                                  and sh.top < Inches(1.5)):
            s.shapes._spTree.append(copy.deepcopy(sh._element))
    for sh in s.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            sh.text_frame.paragraphs[0].runs[0].text = title
            for extra in sh.text_frame.paragraphs[0].runs[1:]:
                extra.text = ""
    return s


def set_title(slide, old, new):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip() == old:
            runs = sh.text_frame.paragraphs[0].runs
            runs[0].text = new
            for r in runs[1:]:
                r.text = ""
            return sh
    raise KeyError(old)


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def at(slide, number):
    cur_page["n"] = number
    order.append(slide)
    return slide


# ------------------------------------------------------------------------------------------------------------------------------ 1 title
s1 = at(S[0], 1)
box = [sh for sh in s1.shapes if sh.has_text_frame and "Project Title" in sh.text_frame.text][0]
vals = ["Project Title : Influencer-Brand Matching via GAIL & Graph Spillover", "Project ID : 011", "Project Guide : Dr. Vishnu Tiwari", "Project Team :"]
team = ["Shimona Sinha (PES2UG23CS547)", "Akshat Navlani (PES2UG23AM009)", "Eesha Shah (PES2UG23AM034)", "Abhyudyay Agrawal (PES2UG23AM003)"]
paras = list(box.text_frame.paragraphs)
for p, v in zip(paras[:4], vals):
    r0 = p.runs[0]
    r0.text = v
    for r in p.runs[1:]:
        r.text = ""
    r0.font.size = Pt(18)
for extra in paras[4:]:                              # the template ends with empty paragraphs: drop them
    extra._p.getparent().remove(extra._p)
anchor = paras[3]._p
for line in team:                                    # one paragraph per team member, copied from the template's own 'Project Team' paragraph so the style is identical
    new_p = copy.deepcopy(paras[3]._p)
    anchor.addnext(new_p)
    anchor = new_p
    for i, t in enumerate(new_p.iter(qn("a:t"))):
        t.text = ("      " + line) if i == 0 else ""
    for rpr in new_p.iter(qn("a:rPr")):
        rpr.set("sz", "1600")
box.top, box.height = Inches(3.55), Inches(3.3)
notes(s1, "Opening. We built a complete pipeline from data to a web app, and today we show what is real, what is validated and what is still open. We state the limits ourselves.")

# ------------------------------------------------------------------------------------------------------------------------------ 2 outline
s2 = at(S[1], 2)

# ------------------------------------------------------------------------------------------------------------------------------ 3 abstract
s3 = at(S[2], 3)
clear_body(s3, {"Abstract and Scope"})
add_text(s3, 0.8, 2.0, 11.7, 4.9, [
    [("Problem: ", {"bold": True}), ("brands pick influencers by follower count and gut feel, and miss spillover: when a creator is sponsored, the audiences of the creators connected to them react too.", {})],
    [("What we built: ", {"bold": True}), ("a brand gives a product, budget and region; the system returns ranked creators with a 0 to 100 score, a confidence range and an explanation, in a web app and a REST API.", {})],
    [("Research part: ", {"bold": True}), ("GAIL (Graph-Adaptive Interference Learning), a graph-attention model that learns which linked creators are exposed to a sponsorship; plus a temporal branch (comment sentiment, cross-platform lag), CLIP/BERT creator features, and a fusion layer.", {})],
    [("Scope: ", {"bold": True}), ("150 verified Indian fitness creators on YouTube, Instagram and Reddit, from public data collected daily. Out of scope: real sales ROI (no sales data exists), public deployment.", {})],
    [("Framing: ", {"bold": True}), ("a careful application of known causal-ML methods to a new domain. Results are exploratory and every claim is tested, with the limits stated.", {})]],
    size=16, bullets=True, space=11, name="abstract")
notes(s3, "Keep this to one minute. The key sentence is the last one: we apply known methods carefully and we say what the data can and cannot show.")

# ------------------------------------------------------------------------------------------------------------------------------ 4 suggestions
s4 = at(S[3], 4)
clear_body(s4, {"Suggestions from Review – 1 & 2"})
rows = [["Open item from Review 1 / 2", "Feasibility and progress now"],
        ["GAIL was trained on only 10 labelled examples", "159 independent examples, 95 of 150 creators linked; retraining is the next step (Eesha)"],
        ["Sentiment and CLIP/BERT scores were 0.5 placeholders", "Real for 149 and 150 of 150 creators; Hindi-script comments use a multilingual model"],
        ["Fusion weights not calibrated", "Cannot be fitted (only 10 labelled outcomes): fixed prior 0.4/0.3/0.3, calibration report written"],
        ["No evaluation, baselines or error analysis", "Placebo tests, simulated validation and a held-out ranking test built; GAIL row pending"],
        ["Graph view and Granger insight missing", "Graph view exists; Granger causality not done (planned)"],
        ["Cost model is a flat heuristic", "Still a heuristic (category rate); no rate-card table yet"],
        ["Integration, performance, Docker", "390 automated tests pass, build passes; load test and Docker run still to do"]]
table(s4, 0.7, 1.95, 11.9, rows, [4.6, 7.3], size=12, row_h=0.56, name="review table")
add_text(s4, 0.7, 6.55, 11.9, 0.4, "Items are the open points listed after Review 1 and in the team's Pending Work list. [to fill: add the panel's own remarks if different]", size=11, color=GRAY, name="source note")
notes(s4, "These are the open items we carried out of Review 1 and 2. Be ready to say which are done (the first four), which are partly done, and which are not done: Granger, the rate card, the load test and Docker.")

# ------------------------------------------------------------------------------------------------------------------------------ 5 architecture 1
s5 = at(S[4], 5)
clear_body(s5, {"Complete pipeline/Architecture of Project"})
set_title(s5, "Complete pipeline/Architecture of Project", "Complete pipeline / Architecture of Project (1 of 2)")
picture(s5, ASSETS / "architecture_modules.png", 3.0, 1.9, h=5.0)
notes(s5, "Walk the five modules top to bottom: collection, feature staging, the GNN dual framework, fusion, and the API. The next slide lists what changed in each module since this diagram was drawn.")

# ------------------------------------------------------------------------------------------------------------------------------ 6 architecture 2
s6 = at(clone_frame(s5, "Architecture: what changed since the diagram (2 of 2)"), 6)
rows = [["Module", "Diagram says", "Now (27 Oct 2026)"],
        ["1 Data collection", "YouTube, Instagram, Reddit; historical partnerships", "24 months of YouTube (59,300 videos), growth readings every 2 h, daily Instagram with owner checks"],
        ["2 Feature staging", "raw records to feature vectors, is_stub flag", "CLIP/BERT features real for 150 of 150; sponsorship events with evidence tiers and a score table"],
        ["3 GNN / dual framework", "340 collaboration + 1,414 co-occurrence edges; sentiment 0.5", "adds shared-brand (1,226) and @mention (154) links: 95 of 150 linked; sentiment real; lag test built"],
        ["4 Fusion", "0.4 spillover + 0.3 sentiment + 0.3 features", "same formula; all inputs real except spillover until GAIL is retrained"],
        ["5 API layer", "/recommendations, /alerts", "adds /platform-profiles and /feature-store/edges/mentions; creators with data rank first"]]
table(s6, 0.7, 2.0, 11.9, rows, [2.2, 3.9, 5.8], size=12, row_h=0.78, name="architecture changes")
notes(s6, "This slide keeps the architecture diagram honest: the structure is unchanged, the content of each module is much richer.")

# ------------------------------------------------------------------------------------------------------------------------------ 7-10 implementation
s7 = at(S[5], 7)
clear_body(s7, {"Implementation Details"})
set_title(s7, "Implementation Details", "Implementation: Modules 1-2, data and features")
add_text(s7, 0.7, 2.0, 6.3, 4.9, [
    [("Technology: ", {"bold": True}), ("YouTube Data API v3 read every 2 h by Supabase pg_cron; Instagram via OpenCLI and a Chrome extension (read-only, 130 page loads a day); Reddit page JSON; Supabase Postgres; Python 3.12.", {})],
    [("Owner check: ", {"bold": True}), ("every Instagram post is matched to the account that really posted it; foreign posts are detached (with a backup).", {})],
    [("Sponsorship detector: ", {"bold": True}), ("rules on text, six evidence tiers from official label to brand mention; spoken sponsors read from captions; negations ('not a paid promotion') ignored.", {})],
    [("Label reliability: ", {"bold": True}), ("each event scored by the human-checked precision of its tier.", {})]],
    size=14, bullets=True, space=9, name="module 1-2 text")
code_box(s7, 7.2, 2.0, 5.5, 4.55, ["for post in new_posts:", "    owner = owner_from_og_text(post)", "    if owner != post.creator:", "        backup(post); detach(post)", "", "tier = highest of:", "    official_label > spoken >", "    creator_comment > disclosure_tag >", "    brand_and_code > brand_mention", "", "if tier and not negated(text):", "    is_sponsored = True", "    p_ad = shrunk_precision(tier)"], size=13)
notes(s7, "Modules 1 and 2. The point to land: the data is collected automatically every day, and every correction is backed up so it can be undone.")

s8 = at(clone_frame(s7, "Implementation: Module 3, graph and GAIL"), 8)
add_text(s8, 0.7, 2.0, 6.3, 4.9, [
    [("Technology: ", {"bold": True}), ("PyTorch Geometric: a graph-attention (GAT) backbone, an exposure module, a propensity model and a spillover head (Eesha's GAIL).", {})],
    [("Graph: ", {"bold": True}), ("creators are nodes; links are collaboration, Reddit co-mention, shared brand (1,226) and @mention (154); 95 of 150 creators linked.", {})],
    [("Targets: ", {"bold": True}), ("a neighbour's engagement lift around each sponsored post, lift = (after - before) / (before + 1), median-based, clipped to +/-5, clustered by 30-day windows into 159 independent examples.", {})],
    [("Honesty tests: ", {"bold": True}), ("within-neighbour placebo test, dose-response, direct effect, simulated validation.", {})]],
    size=14, bullets=True, space=9, name="module 3 text")
code_box(s8, 7.2, 2.0, 5.5, 4.55, ["emb  = GAT(features, edges)", "w_ij = softmax(sim(emb_i, emb_j))", "exposure_j = sum_i treated_i * w_ij", "", "e_j  = propensity(features_j)", "y_j  = head(emb_j, exposure_j)", "", "loss = mse(y_hat, lift)", "     + lambda * propensity_regulariser", "", "evaluate on held-out creators only;", "never quote the in-sample effect"], size=13)
notes(s8, "Module 3. GAIL is Eesha's model. Our contribution is the data that feeds it and the tests that check it. Say that the training retrain is next, and that we judge it only on held-out creators.")

s9 = at(clone_frame(s7, "Implementation: temporal branch and features"), 9)
add_text(s9, 0.7, 2.0, 6.3, 4.9, [
    [("Sentiment: ", {"bold": True}), ("RoBERTa (English) per comment; a multilingual XLM-R model for Hindi-script comments; safety = P(positive) + 0.5 P(neutral), pulled to 0.5 for creators with few comments.", {})],
    [("Lag detection: ", {"bold": True}), ("event study on growth readings every 2 h: activity after an Instagram post against the same creator's own rate, with a placebo from random times of the same hour of day.", {})],
    [("Creator features: ", {"bold": True}), ("CLIP on thumbnails and BERT on text, matched to the brand's product brief.", {})],
    [("Positive control: ", {"bold": True}), ("a YouTube upload must lift that channel's own views, or the method is broken.", {})]],
    size=14, bullets=True, space=9, name="module 3b text")
code_box(s9, 7.2, 2.0, 5.5, 4.55, ["for event in instagram_posts:", "  for window k in -48h .. +48h (12 h):", "    excess_k = rate_k / own_rate - 1", "  null = same statistic at random", "         times, same hour of day", "  p_k = share(null >= excess_k)", "", "detected only if", "  min(p_after) < 0.05 / 4", "", "control: upload -> own views", "must be detected first"], size=13)
notes(s9, "The temporal branch. Sentiment is tested per language. Lag uses a placebo and a positive control so that a null result is believable.")

s10 = at(clone_frame(s7, "Implementation: Modules 4-5, fusion and app"), 10)
add_text(s10, 0.7, 2.0, 6.3, 4.9, [
    [("Fusion: ", {"bold": True}), ("final = 100 x (0.4 spillover + 0.3 sentiment + 0.3 features), minus 10 when sentiment is below 0.3; the confidence range combines each branch's uncertainty in quadrature.", {})],
    [("Backend: ", {"bold": True}), ("FastAPI + SQLModel on Supabase; /recommendations, /alerts, /feature-store, /platform-profiles.", {})],
    [("Frontend: ", {"bold": True}), ("Next.js 16 and TypeScript: brief form, ranked dashboard with basis badges, per-platform status, explainability graph, monitoring, analysis tab.", {})],
    [("New: ", {"bold": True}), ("YouTube vs Instagram status per creator; creators with no data rank below those with data.", {})]],
    size=14, bullets=True, space=9, name="module 4-5 text")
code_box(s10, 7.2, 2.0, 5.5, 4.55, ["final = 100 * (0.4*spillover", "               + 0.3*sentiment", "               + 0.3*features)", "if sentiment < 0.3: final -= 10", "", "half_width = sqrt(sum(w_i * u_i)^2)", "range = final +/- half_width", "", "rank by (has_posts, final)", "show basis: trained | inferred |", "            isolated"], size=13)
notes(s10, "Fusion and the app. The weights are a stated prior because there are not enough labelled outcomes to fit them, and the app shows each score with its basis and range.")

# ------------------------------------------------------------------------------------------------------------------------------ 11 demo
s11 = at(S[6], 11)
clear_body(s11, {"Project Demonstration"})
add_text(s11, 0.7, 2.0, 3.6, 4.9, [
    "Demo flow (about 4 minutes):",
    "1. Brand brief: 'Whey protein, fitness', budget 3,00,000",
    "2. Ranked list with score, range and basis badge",
    "3. 'YouTube vs Instagram status' for a creator",
    "4. Explainability: how the score is built",
    "5. Monitoring alerts with creator names",
    "6. Analysis tab: real result next to the simulated check"],
    size=13, bullets=False, space=6, name="demo flow")
add_text(s11, 0.7, 6.3, 6.0, 0.6, "[to fill: demo video recorded and checked]", size=12, color=RED, name="demo video note")
picture(s11, ASSETS / "dashboard_platform_status.jpg", 4.5, 2.0, w=4.1)
picture(s11, ASSETS / "analysis_real_vs_simulated.jpg", 8.75, 2.0, w=4.1)
add_text(s11, 4.5, 5.2, 4.1, 0.6, "Ranked result with per-platform status", size=12, color=GRAY, name="caption 1")
add_text(s11, 8.75, 5.2, 4.1, 0.6, "Analysis tab: real vs simulated", size=12, color=GRAY, name="caption 2")
notes(s11, "Run this live from the app. The screenshots are real. Keep the backend started a minute before the demo, because the CLIP and BERT models load on startup.")

# ------------------------------------------------------------------------------------------------------------------------------ 12-13 test plan
s12 = at(S[7], 12)
clear_body(s12, {"Test Plan and Strategy"})
set_title(s12, "Test Plan and Strategy", "Test Plan and Strategy (1 of 2)")
rows = [["Test type", "What is covered", "Tool", "Result (27 Oct)"],
        ["Unit: backend", "scoring, filters, feature store, alerts, platform profile", "pytest", "120 pass"],
        ["Unit: ML and scripts", "estimators, label model, lag, ranking, simulations", "pytest", "150 pass"],
        ["Unit: ingestion", "detector, daily job budget and blocks, Reddit, snapshots", "pytest", "120 pass"],
        ["Frontend", "type-check, lint, production build", "tsc, ESLint, Next.js", "pass, 7 pages"],
        ["Integration (manual)", "brief to dashboard to platform status, in a real browser", "browser", "checked"],
        ["Data validation", "owner audit, duplicates, human label checks, backups", "SQL, scripts", "see results"],
        ["Statistical validation", "placebo test, dose-response, simulated planted effects", "Python, numpy", "see results"]]
table(s12, 0.7, 1.95, 11.9, rows, [2.4, 5.5, 2.0, 2.0], size=12, row_h=0.5, name="test table")
add_text(s12, 0.7, 6.05, 11.9, 0.9, [[("Environment and roles: ", {"bold": True}), ("tests run on the developers' laptops against a shared Supabase database; Shimona tests data, temporal analysis and the app, Eesha the GAIL model, Akshat the infrastructure and gate scripts, [to fill: Abhyudyay's role]. All tools are open source.", {})]], size=12, name="environment")
notes(s12, "Why these methods: unit tests protect each module, the browser check protects the integration, and the data and statistical validation protect the claims, which matter most in a project with little labelled data.")

s13 = at(clone_frame(s12, "Test Plan and Strategy (2 of 2)"), 13)
add_text(s13, 0.7, 2.0, 5.9, 4.9, [
    [("Activities and timeline", {"bold": True, "color": RED})],
    "Tests were written with each module in Oct 2026 and all suites run before every push.",
    "Data fixes are tested by re-measuring (counts, duplicates, links) and every change keeps a backup table.",
    "Simulated checks plant a known effect on the real data to test the methods themselves.",
    [("Benefits", {"bold": True, "color": RED})],
    "Cheap to repeat, catches regressions, makes claims checkable."], size=13, bullets=True, space=6, name="test strategy")
add_text(s13, 6.9, 2.0, 5.8, 4.9, [
    [("Drawbacks and gaps", {"bold": True, "color": RED})],
    "No load or performance test of the API yet.",
    "No security test and no CI pipeline on GitHub (local gate script only).",
    "Docker image never run (Docker is not installed on the laptop).",
    "GAIL itself is tested only after the retrain; its simulated acceptance check failed 0 of 4 on the old model.",
    "Human label checks cover only 4% of events."], size=13, bullets=True, space=6, name="test gaps")
notes(s13, "Be open about the gaps: load, security and Docker are not done. The GAIL acceptance check is rerun on the new checkpoint.")

# ------------------------------------------------------------------------------------------------------------------------------ 14-15 results
s14 = at(S[8], 14)
clear_body(s14, {"Results and Discussion"})
set_title(s14, "Results and Discussion", "Results and Discussion (1 of 2): data, labels, graph")
tiers = QUAL["human_checked_precision_by_tier"]
order_t = [("official_label", "official label"), ("disclosure_tag", "disclosure tag"), ("brand_mention", "brand mention"), ("spoken", "spoken"), ("brand_and_code", "brand + code")]
cats = [f"{lab} (n={tiers[k]['checked']})" for k, lab in order_t] + ["text-only reading (n=113)"]
vals = [round(tiers[k]["precision"] * 100) for k, _ in order_t] + [round(QUAL["claude_text_only_readings"]["share"] * 100)]
bar_chart(s14, 0.6, 1.9, 6.3, 3.6, cats, [("Real ads", vals)], [BLUE], number_format='0"%"', maxv=118, title="Real ads among flagged events, by evidence tier", point_colors=[BLUE] * 5 + [AMBER], horizontal=True)
bar_chart(s14, 7.1, 1.9, 5.6, 3.6, ["Before", "+ shared brand", "+ @mentions"], [("Creators linked", [17, 85, 95])], [TEAL], maxv=165, title="Creators of the 150 with a graph link")
add_text(s14, 0.7, 5.6, 12.0, 1.35, [
    "Strong evidence tiers are almost always right (73 of 75 checked one by one, 91 to 99%), but that is only 4% of events; a text-only reading of weak tiers finds 61%, so their precision lies between about 60% and 95%.",
    "Graph links grew from 17 to 95 of 150 creators; most are 'same brand' links (only 7 real collaboration pairs), so we call the graph exploratory.",
    "Data: 59,300 YouTube videos, 270,357 growth readings, 1,857 sponsorship events."], size=12, bullets=True, space=4, name="results text 1")
notes(s14, "Expected: reliable labels. Observed: strong tiers yes, weak tiers uncertain. The deviation is honest and we corrected an earlier 91% figure that mixed assumed rows with checked ones.")

s15 = at(clone_frame(s14, "Results and Discussion (2 of 2): spillover, lag, baselines"), 15)
t = SEMI["table"]
keys = ("0.0", "0.1", "0.25", "0.5", "1.0")
line_chart(s15, 0.6, 1.9, 5.9, 3.55, ["0", "0.10", "0.25", "0.50", "1.00"], [("Naive analysis", [round(t[k]["naive"]["detects_effect_share"] * 100) for k in keys]), ("Placebo test (ours)", [round(t[k]["placebo"]["detects_effect_share"] * 100) for k in keys])], [GRAY, BLUE],
           title="SIMULATED: studies that say 'effect found'")
tag(s15, "SIMULATED chart", x=0.8, y=1.65, w=1.9) if False else None
ci = PLACEBO["ci"]
rows = [["Real-data test", "Result"],
        ["Within-neighbour placebo (65)", f"{PLACEBO['median_of_means']:+.2f} ({ci[0]:+.2f} to {ci[1]:+.2f})"],
        ["Stronger tie, more spillover?", f"trend {DOSE['trend']['spearman_tie_strength_vs_paired_difference']:+.2f}"],
        ["Sponsored vs usual video", f"views x{DIRECT['median_ratio_vs_own_typical_post']:.2f}"],
        ["Lag, Instagram to YouTube", "p = 0.043, not confirmed"],
        ["Ranking vs random (37 creators)", "no baseline beats random"]]
table(s15, 6.8, 1.95, 5.9, rows, [3.4, 2.5], size=12, row_h=0.5, name="real results")
add_text(s15, 0.7, 5.55, 12.0, 1.4, [
    "Expected a measurable spillover; observed none broad. The simulated check shows the test would catch an effect of 0.25 or more every time and the naive method raises false alarms, so the null is informative.",
    "Reasons for the deviation: small labelled set (159 examples), graph mostly 'same brand', 17 days of growth readings; a localised effect (about 20% of neighbours) would be missed.",
    "Compared with simple baselines (follower count, engagement rate, past effect) none beat random; GAIL's row follows the retrain."], size=12, bullets=True, space=4, name="results text 2")
notes(s15, "Read the left chart as a SIMULATED check: a planted effect on the real network. The right table is real data only. The honest summary is that we find no broad spillover and we can show our test would have found one.")

# ------------------------------------------------------------------------------------------------------------------------------ 16 timeline
s16 = at(S[9], 16)
clear_body(s16, {"Timeline – Update on Tasks"})
rows = [["Period", "Tasks", "Status"],
        ["Aug 2026", "Schema, ingestion, graph, feature store, first GAIL run, Review 1 (closed 26 Aug)", "Done"],
        ["Sep 2026", "Fusion layer, live API and web app, GAIL trained on 10 examples", "Done"],
        ["Early Oct", "Temporal branch (sentiment, lag), CLIP/BERT features, calibration report, filters, linking, Analysis tab", "Done"],
        ["11-26 Oct", "Daily collection, 24-month YouTube history, labels and brands, links, placebo and simulated validation", "Done"],
        ["27 Oct", "Platform status in the app, handoff, training files exported", "Done"],
        ["28 Oct+", "GAIL retraining and held-out scoring (Eesha), fusion refresh", "In progress"],
        ["After review", "Docker run, load test, human label checks, thesis, deployable build", "Planned"]]
table(s16, 0.7, 1.95, 11.9, rows, [1.9, 8.1, 1.9], size=12, row_h=0.56, name="timeline")
add_text(s16, 0.7, 6.55, 11.9, 0.4, "Dates are monthly milestones from the project plan and the repository history.", size=11, color=GRAY, name="timeline note")
notes(s16, "The project is complete as a pipeline. The open items are the final GAIL retraining and the hardening tasks that come after.")

# ------------------------------------------------------------------------------------------------------------------------------ 17 conclusion
s17 = at(S[10], 17)
clear_body(s17, {"Conclusion and Future work"})
add_text(s17, 0.7, 2.0, 5.9, 4.9, [
    [("Conclusion", {"bold": True, "color": RED})],
    "A complete pipeline from daily data collection to a web app with ranked, explained scores.",
    "Better data: 59,300 videos, 1,857 labelled events, 95 of 150 creators linked, 159 training examples.",
    "Honest validation: the real data shows no broad spillover and simulations show our tests would have found one.",
    "Known limits are stated, not hidden."], size=13, bullets=True, space=7, name="conclusion")
add_text(s17, 6.9, 2.0, 5.8, 4.9, [
    [("Future work", {"bold": True, "color": RED})],
    "Retrain GAIL, then held-out scoring, acceptance check and fusion refresh.",
    "Train also on the direct effect of sponsored posts (about 1,400 more events).",
    "Per-platform normalisation, five random seeds, cross-fitting.",
    "More Instagram counts and human label checks; Granger causality; rate card.",
    "Docker, load test and security pass; thesis."], size=13, bullets=True, space=7, name="future work")
notes(s17, "Close with the takeaway: a complete, honest pipeline, a clearer graph, and a clear plan.")

# ------------------------------------------------------------------------------------------------------------------------------ 18 references
s18 = at(S[11], 18)
clear_body(s18, {"References"})
refs = [
    "[1] P. Velickovic et al., \"Graph attention networks,\" in Proc. ICLR, 2018.",
    "[2] M. Fey and J. E. Lenssen, \"Fast graph representation learning with PyTorch Geometric,\" in ICLR Workshop on Representation Learning on Graphs and Manifolds, 2019.",
    "[3] J. Qiu, J. Tang, H. Ma, Y. Dong, K. Wang, and J. Tang, \"DeepInf: Social influence prediction with deep learning,\" in Proc. ACM SIGKDD, 2018, pp. 2110-2119.",
    "[4] S. Kim, J.-Y. Jiang, J. Han, and W. Wang, \"InfluencerRank: Discovering effective influencers via graph convolutional attentive recurrent neural networks,\" in Proc. ICWSM, vol. 17, no. 1, 2023, doi: 10.1609/icwsm.v17i1.22162.",
    "[5] M. G. Hudgens and M. E. Halloran, \"Toward causal inference with interference,\" J. Amer. Statist. Assoc., vol. 103, no. 482, pp. 832-842, 2008.",
    "[6] P. R. Rosenbaum and D. B. Rubin, \"The central role of the propensity score in observational studies for causal effects,\" Biometrika, vol. 70, no. 1, pp. 41-55, 1983.",
    "[7] J. M. Robins, A. Rotnitzky, and L. P. Zhao, \"Estimation of regression coefficients when some regressors are not always observed,\" J. Amer. Statist. Assoc., vol. 89, no. 427, pp. 846-866, 1994.",
    "[8] V. Chernozhukov et al., \"Double/debiased machine learning for treatment and structural parameters,\" Econometrics J., vol. 21, no. 1, pp. C1-C68, 2018.",
    "[9] A. Radford et al., \"Learning transferable visual models from natural language supervision,\" in Proc. ICML, PMLR 139, 2021, pp. 8748-8763.",
    "[10] J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, \"BERT: Pre-training of deep bidirectional transformers for language understanding,\" in Proc. NAACL-HLT, 2019, pp. 4171-4186.",
    "[11] A. Conneau et al., \"Unsupervised cross-lingual representation learning at scale,\" in Proc. ACL, 2020, pp. 8440-8451.",
    "[12] C. W. J. Granger, \"Investigating causal relations by econometric models and cross-spectral methods,\" Econometrica, vol. 37, no. 3, pp. 424-438, 1969."]
add_text(s18, 0.7, 1.95, 11.9, 5.0, refs, size=11, color=INK, space=5, name="references")
notes(s18, "References are in IEEE style. Page numbers are omitted where we were not certain of them.")

# ------------------------------------------------------------------------------------------------------------------------------ 19 thank you
s19 = at(S[12], 19)

# reorder to the final sequence (new slides were appended at the end of the package)
lst = prs.slides._sldIdLst
by_id = {sld.slide_id: el for sld, el in zip(prs.slides, list(lst))}
final_ids = [sld.slide_id for sld in order]                 # read the ids BEFORE the list is emptied
assert len(final_ids) == len(by_id) == len(set(final_ids)), (len(final_ids), len(by_id))
for el in list(lst):
    lst.remove(el)
for sid in final_ids:
    lst.append(by_id[sid])

# slide numbers for the footer of added slides are not used by the template; nothing else to do
prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))
print("\n".join(WARN) if WARN else "no overflow warnings")
