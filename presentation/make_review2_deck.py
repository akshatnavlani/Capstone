"""Builds Review2_Presentation.pptx (16:9) from the result files in models/ and the screenshots in presentation/assets/. Re-run it after any result changes.

    python presentation/make_review2_deck.py            (needs python-pptx)

Every number on the slides is either read from models/*.json here or is a figure checked against the live database on 27 Oct 2026 (listed in FACTS below).
Simulated results are always tagged SIMULATED. Speaker notes carry the talking points.
"""
import json
import math
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "presentation" / "Review2_Presentation.pptx"
ASSETS = ROOT / "presentation" / "assets"
M = ROOT / "models"


def load(name):
    return json.loads((M / name).read_text(encoding="utf-8"))


SEMI, LAGP, QUAL = load("sim_semisynthetic_benchmark.json"), load("sim_lag_power.json"), load("sponsorship_quality.json")
PLACEBO = load("spillover_placebo_test.json")["scopes"]["in_the_150"]["all"]["per_neighbour"]
DIRECT = load("direct_effect.json")["results"]["youtube/views/all_events"]["sponsored_posts"]
DOSE = load("spillover_dose.json")

# Checked against the live database / code on 27 Oct 2026
FACTS = {"yt_videos": "59,300", "readings": "270,357", "yt_comments": "165,862", "ig_posts": "1,021", "ig_creators": "78", "reddit_comments": "61,570", "events": "1,874",
         "linked_before": 17, "linked_shared": 85, "linked_all": 95, "obs": 159, "neighbours": 75}

INK, TEAL, MINT, TINT, AMBER, AMBER_DK, GRAY, WHITE, SOFT = "0F2A33", "1F7A7A", "CFE8E4", "EEF4F3", "F2A33A", "9A5B00", "5E6C73", "FFFFFF", "F6F9F9"
HEAD, BODY = "Cambria", "Calibri"
WARN = []


def rgb(h):
    return RGBColor.from_string(h)


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
page = {"n": 0}


def est_lines(text, w_in, size):
    cpl = max(int(w_in / (size * 0.50 / 72)), 1)           # characters per line (Calibri averages about 0.5 em)
    return sum(max(math.ceil(len(part) / cpl), 1) for part in text.split("\n"))


def add_text(s, x, y, w, h, paras, size=16, bold=False, color=INK, font=BODY, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, bullets=False, space=4, name=None, italic=False):
    """paras: str | list[str | list[(text, {bold,color,size,italic})]]. Warns when the estimated height exceeds the box."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tb.name = name or "text"
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    items = [paras] if isinstance(paras, str) else paras
    need = 0.0
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
            r.font.italic = o.get("italic", italic)
            r.font.color.rgb = rgb(o.get("color", color))
        if bullets:
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(int(Inches(0.28))))
            pPr.set("indent", str(-int(Inches(0.28))))
            bu = etree.SubElement(pPr, qn("a:buChar"))
            bu.set("char", "•")
        need += est_lines(plain, w - (0.28 if bullets else 0), size) * size * 1.2 / 72 + space / 72
    if need > h + 0.05:
        WARN.append(f"slide {page['n']} '{(name or str(items[0])[:30])}': needs about {need:.2f} in, box is {h:.2f} in")
    return tb


def add_rect(s, x, y, w, h, fill=TINT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, name=None):
    r = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    r.name = name or "shape"
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        r.adjustments[0] = radius
    r.fill.solid()
    r.fill.fore_color.rgb = rgb(fill)
    if line:
        r.line.color.rgb = rgb(line)
        r.line.width = Pt(1)
    else:
        r.line.fill.background()
    r.shadow.inherit = False
    return r


def new_slide(title=None, dark=False, notes="", section=None):
    s = prs.slides.add_slide(BLANK)
    page["n"] += 1
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = rgb(INK if dark else WHITE)
    if title:
        add_text(s, 0.6, 0.42, 12.1, 0.9, title, size=30, bold=True, color=WHITE if dark else INK, font=HEAD, anchor=MSO_ANCHOR.TOP, name="title")
    if not dark:
        add_text(s, 0.6, 7.05, 8, 0.25, "Influencer-Brand Matching via GAIL & Graph Spillover  |  Review 2  |  28 Oct 2026", size=10, color=GRAY, name="footer")
        add_text(s, 12.0, 7.05, 0.75, 0.25, str(page["n"]), size=10, color=GRAY, align=PP_ALIGN.RIGHT, name="page")
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def sim_tag(s, x=11.2, y=0.5, w=1.6):
    r = add_rect(s, x, y, w, 0.36, fill="FFF3DC", line=AMBER, name="simulated tag")
    add_text(s, x, y + 0.06, w, 0.25, "SIMULATED", size=12, bold=True, color=AMBER_DK, align=PP_ALIGN.CENTER, name="simulated tag text")


def stat(s, x, y, w, h, value, label, note=None, accent=TEAL, fill=TINT, vsize=34):
    add_rect(s, x, y, w, h, fill=fill, name="stat card")
    add_text(s, x + 0.2, y + 0.15, w - 0.4, 0.7, value, size=vsize, bold=True, color=accent, font=HEAD, name="stat value")
    add_text(s, x + 0.2, y + 0.15 + vsize / 72 * 1.25 + 0.05, w - 0.4, 0.5, label, size=14, bold=True, color=INK, name="stat label")
    if note:
        add_text(s, x + 0.2, y + h - 0.6, w - 0.4, 0.5, note, size=12, color=GRAY, name="stat note")


def style_chart(ch, size=12):
    ch.font.size = Pt(size)
    ch.font.name = BODY
    ch.font.color.rgb = rgb(INK)


def bar_chart(s, x, y, w, h, cats, series, colors=None, number_format='0', maxv=None, title=None, horizontal=False, legend=False, point_colors=None):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = s.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    gf.name = "chart"
    ch = gf.chart
    style_chart(ch)
    ch.has_title = bool(title)
    if title:
        ch.chart_title.text_frame.text = title
        ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
        ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(12)
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.font.size = Pt(12)
    dl.font.bold = True
    dl.number_format = number_format
    dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    if horizontal:
        ch.category_axis.reverse_order = True
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb("DDE5E5")
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(11)
    va.tick_labels.font.color.rgb = rgb(GRAY)
    if maxv:
        va.maximum_scale = maxv
    va.minimum_scale = 0
    ch.category_axis.tick_labels.font.size = Pt(12)
    ch.category_axis.format.line.color.rgb = rgb("B7C3C3")
    for i, ser in enumerate(plot.series):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = rgb((colors or [TEAL, AMBER])[i % len(colors or [TEAL, AMBER])])
        if point_colors and i == 0:
            for j, c in enumerate(point_colors):
                pt = ser.points[j]
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = rgb(c)
    return ch


def line_chart(s, x, y, w, h, cats, series, colors, title=None):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals)
    gf = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    gf.name = "chart"
    ch = gf.chart
    style_chart(ch)
    ch.has_title = bool(title)
    if title:
        ch.chart_title.text_frame.text = title
        ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
        ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(12)
    va = ch.value_axis
    va.maximum_scale, va.minimum_scale = 105, 0
    va.major_gridlines.format.line.color.rgb = rgb("DDE5E5")
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(11)
    va.tick_labels.font.color.rgb = rgb(GRAY)
    ch.category_axis.tick_labels.font.size = Pt(12)
    for i, ser in enumerate(ch.plots[0].series):
        ser.format.line.color.rgb = rgb(colors[i])
        ser.format.line.width = Pt(3)
        ser.smooth = False
        ser.marker.format.fill.solid()
        ser.marker.format.fill.fore_color.rgb = rgb(colors[i])
        ser.marker.format.line.color.rgb = rgb(colors[i])
    lab = ch.plots[0].series[1].data_labels   # label only the placebo series: both lines sit at 100% and would overprint
    lab.show_value = True
    lab.font.size = Pt(12)
    lab.font.bold = True
    lab.number_format = '0"%"'
    lab.number_format_is_linked = False
    lab.position = XL_LABEL_POSITION.BELOW
    return ch


def table(s, x, y, w, rows, col_w, size=13, row_h=0.55, head_fill=INK):
    nrows, ncols = len(rows), len(rows[0])
    gf = s.shapes.add_table(nrows, ncols, Inches(x), Inches(y), Inches(w), Inches(row_h * nrows))
    gf.name = "table"
    tb = gf.table
    tblPr = tb._tbl.tblPr
    tblPr.set("firstRow", "1")
    tblPr.set("bandRow", "0")
    style_id = tblPr.find(qn("a:tableStyleId"))
    if style_id is not None:
        style_id.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"   # No Style, No Grid
    for j, cw in enumerate(col_w):
        tb.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        tb.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = tb.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.1)
            c.margin_top = c.margin_bottom = Inches(0.05)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid()
            c.fill.fore_color.rgb = rgb(head_fill if i == 0 else (TINT if i % 2 else WHITE))
            tf = c.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            r = p.add_run()
            r.text = str(val)
            r.font.name, r.font.size = BODY, Pt(size)
            r.font.bold = i == 0 or j == 0
            r.font.color.rgb = rgb(WHITE if i == 0 else INK)
            lines = est_lines(str(val), col_w[j] - 0.2, size)
            if lines * size * 1.2 / 72 + 0.1 > row_h + 0.02:
                WARN.append(f"slide {page['n']} table cell r{i}c{j}: {lines} lines may not fit a {row_h} in row")
    return tb


def picture(s, path, x, y, w):
    pic = s.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w))
    pic.name = "screenshot"
    pic.line.color.rgb = rgb("B7C3C3")
    pic.line.width = Pt(1)
    return pic


def arrow(s, x1, y1, x2, y2, color=TEAL):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(2.25)
    ln = c.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    return c


def icon_circle(s, x, y, d, label, fill=TEAL, color=WHITE, size=16):
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    c.fill.solid()
    c.fill.fore_color.rgb = rgb(fill)
    c.line.fill.background()
    c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size, r.font.bold, r.font.name = Pt(size), True, BODY
    r.font.color.rgb = rgb(color)
    c.name = "icon"
    return c


# --------------------------------------------------------------------------------------------------------------------- 1 title
s = new_slide(dark=True, notes="Opening. One sentence: we built the full pipeline from data to a web app, and this review is about what is real, what is validated and what is still open. We say the limits ourselves.")
import random as _r
_r.seed(4)
nodes = [(8.6, 1.4), (10.2, 0.9), (11.9, 1.7), (9.3, 2.7), (11.0, 2.9), (12.4, 3.6), (8.9, 4.2), (10.5, 4.5), (11.9, 5.3), (9.6, 5.9), (11.2, 6.3)]
edges = [(0, 1), (1, 2), (0, 3), (1, 3), (1, 4), (2, 4), (2, 5), (3, 4), (3, 6), (4, 7), (5, 7), (6, 7), (7, 8), (6, 9), (7, 9), (8, 10), (9, 10), (5, 8)]
for a, b in edges:
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(nodes[a][0]), Inches(nodes[a][1]), Inches(nodes[b][0]), Inches(nodes[b][1]))
    c.line.color.rgb = rgb("2F6A72")
    c.line.width = Pt(1.5)
for i, (nx, ny) in enumerate(nodes):
    d = 0.5 if i in (1, 4, 7) else 0.34
    o = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(nx - d / 2), Inches(ny - d / 2), Inches(d), Inches(d))
    o.fill.solid()
    o.fill.fore_color.rgb = rgb(AMBER if i in (1, 4, 7) else "5FB3AE")
    o.line.fill.background()
    o.shadow.inherit = False
add_text(s, 0.7, 1.9, 7.4, 2.2, "Influencer-Brand Matching via GAIL & Graph Spillover", size=40, bold=True, color=WHITE, font=HEAD, name="deck title")
add_text(s, 0.7, 4.25, 7.2, 0.9, "Review 2: the pipeline is complete, and every claim is tested", size=22, color="CFE8E4", name="subtitle")
add_text(s, 0.7, 5.6, 7.2, 1.0, ["Shimona Sinha (data, temporal analysis, web app)", "Eesha (GAIL model)  |  Akshat (infrastructure)", "UE23CS441A, Project 011  |  28 October 2026"], size=14, color="9FC4C0", space=2, name="team")

# --------------------------------------------------------------------------------------------------------------------- 2 at a glance
s = new_slide("What changed since the last review", notes="Four numbers tell the story. YouTube history grew about 2.8 times. Sponsorship events doubled after re-labelling. Linked creators went from 17 to 95 of the 150. The number of independent training examples is about four times larger. All measured on live data on 27 October and every data change has a backup.")
specs = [(FACTS["yt_videos"], "YouTube videos of the 150 creators", "was 21,100 on 25 Oct (history extended to 24 months)"),
         (FACTS["events"], "Sponsorship events", "was 897 on 25 Oct, after the labelling pass"),
         (f"{FACTS['linked_all']} of 150", "Creators with a graph link", f"was {FACTS['linked_before']} (collaboration and Reddit only)"),
         (str(FACTS["obs"]), "Independent training examples", "was about 39 (one example per engagement change)")]
for i, (v, l, n) in enumerate(specs):
    stat(s, 0.6 + i * 3.08, 1.75, 2.9, 2.45, v, l, n, vsize=34)
add_text(s, 0.6, 4.6, 12.1, 1.9, [[("Why this matters: ", {"bold": True}), ("GAIL can only learn from what the data shows, so we spent this phase on the data first: more history, correct labels and brands, and more links between creators.", {})],
                                   [("How we checked: ", {"bold": True}), ("numbers are from the live database on 27 Oct 2026, and every change to shared data was backed up before it was made.", {})]], size=16, space=8, name="why")

# --------------------------------------------------------------------------------------------------------------------- 3 pipeline
s = new_slide("The system end to end", notes="Walk left to right. Collection runs by itself every day. Labels and brands are cleaned and corrected. The graph links creators. GAIL estimates spillover; two other branches add sentiment and creator features; fusion combines the three into a 0 to 100 score with a confidence range; the web app shows it with its basis. Only GAIL still needs the final retraining.")
boxes = [("Collect", "YouTube API, Instagram, Reddit; runs daily on its own"), ("Clean + label", "owner checks, brand fixes, sponsorship detector"), ("Graph", "collaboration, shared brand, @mention links"),
         ("GAIL", "spillover: does a post lift linked creators"), ("Fusion", "0.4 spillover + 0.3 sentiment + 0.3 features"), ("Web app", "ranked list, scores, explanations")]
bw, gap, y0 = 1.85, 0.2, 1.75
for i, (t, d) in enumerate(boxes):
    x = 0.6 + i * (bw + gap)
    add_rect(s, x, y0, bw, 1.95, fill=TINT, name="step")
    icon_circle(s, x + 0.15, y0 + 0.15, 0.42, str(i + 1))
    add_text(s, x + 0.15, y0 + 0.68, bw - 0.3, 0.35, t, size=16, bold=True, color=INK, font=HEAD, name="step title")
    add_text(s, x + 0.15, y0 + 1.05, bw - 0.3, 0.85, d, size=12, color=GRAY, name="step text")
    if i < len(boxes) - 1:
        arrow(s, x + bw + 0.01, y0 + 0.98, x + bw + gap - 0.01, y0 + 0.98)
for j, (t, d) in enumerate([("Temporal sentiment", "comment sentiment per creator; English plus a Hindi-script model"), ("CLIP and BERT features", "how well a creator's posts match the brand brief")]):
    x = 5.4 + j * 3.6
    add_rect(s, x, 4.45, 3.4, 1.2, fill=WHITE, line=TEAL, name="branch")
    add_text(s, x + 0.2, 4.55, 3.0, 0.3, t, size=15, bold=True, color=TEAL, name="branch title")
    add_text(s, x + 0.2, 4.9, 3.0, 0.7, d, size=12, color=GRAY, name="branch text")
    arrow(s, x + 1.7, 4.44, 0.6 + 4 * (bw + gap) + bw / 2 + (j - 0.5) * 0.7, y0 + 1.97, color=GRAY)
add_text(s, 0.6, 4.6, 4.3, 1.2, [[("Status: ", {"bold": True}), ("everything runs and is tested. Only the final GAIL retraining is left.", {})]], size=15, name="status")

# --------------------------------------------------------------------------------------------------------------------- 4 data
s = new_slide("What we collected", notes="These are the 150 verified Indian fitness creators. YouTube is the strong side: 59 thousand videos and a growth reading every two hours since 11 October. Instagram is thinner because of the rate limit: 78 of 150 creators. Collection keeps running without anyone's laptop for YouTube, and daily for Instagram.")
cards = [(FACTS["yt_videos"], "YouTube videos", "Dec 2023 to Oct 2026"), (FACTS["readings"], "growth readings", "every 2 hours since 11 Oct"), (FACTS["yt_comments"], "YouTube comments", "for sentiment"),
         (FACTS["ig_posts"], "Instagram posts", f"{FACTS['ig_creators']} of 150 creators"), (FACTS["reddit_comments"], "Reddit comments", "3,308 posts, brand talk"), (FACTS["events"], "sponsorship events", "1,874 labelled, 109 creators")]
for i, (v, l, n) in enumerate(cards):
    x, y = 0.6 + (i % 3) * 4.1, 1.7 + (i // 3) * 2.15
    stat(s, x, y, 3.9, 1.95, v, l, n, vsize=34)
add_text(s, 0.6, 6.1, 12.1, 0.8, "Collection never stops: YouTube is read every 2 hours inside Supabase, Instagram once a day (read-only, capped at 130 page loads a day to avoid blocks), Reddit on request.", size=14, color=GRAY, name="collection note")

# --------------------------------------------------------------------------------------------------------------------- 5 data trust
s = new_slide("Making the data trustworthy", notes="This is the cleaning work. The important point for the committee: each fix is small, checked, and reversible. We removed Instagram posts that belonged to other accounts, removed wrong brand attachments, gave brands to sponsored posts that had none, and classified brands so they can link creators.")
fixes = [("Whose post is it?", "Instagram posts are checked against the true owner; foreign posts were detached, with a backup."), ("Wrong brands removed", "28 words that are not brands (gmail, Delhi) no longer count as sponsors."),
         ("Missing brands filled", "17 sponsored posts of 9 creators now carry the brand named in their own text."), ("Brands classified", "25 unclassified brands sorted, so they can link creators."),
         ("Labels corrected", "Two look-alike posts unflagged ('Not a paid promotion'); an accuracy figure of ours was retracted."), ("Sentiment fixed", "Hindi-script comments now use a multilingual model.")]
for i, (t, d) in enumerate(fixes):
    x, y = 0.6 + (i % 3) * 4.1, 1.75 + (i // 3) * 2.45
    add_rect(s, x, y, 3.9, 2.2, fill=TINT, name="fix card")
    icon_circle(s, x + 0.2, y + 0.2, 0.46, str(i + 1))
    add_text(s, x + 0.8, y + 0.26, 2.95, 0.4, t, size=16, bold=True, font=HEAD, name="fix title")
    add_text(s, x + 0.2, y + 0.85, 3.5, 1.3, d, size=14, color=INK, name="fix text")

# --------------------------------------------------------------------------------------------------------------------- 6 labels
s = new_slide("How reliable are the sponsorship labels?", notes="Be careful and honest here. The strong evidence tiers, checked one by one by a person, are almost always right: 73 of 75. But that is only 4 percent of events. When Claude read only the description of weak-tier events, only 61 percent looked sponsored, though text cannot hear a spoken sponsor. So the true weak-tier precision is somewhere between about 60 and 95 percent. We corrected an earlier 91 percent figure that mixed assumed rows with checked ones.")
tiers = QUAL["human_checked_precision_by_tier"]
order = [("official_label", "official label"), ("disclosure_tag", "disclosure tag"), ("brand_mention", "brand mention"), ("spoken", "spoken"), ("brand_and_code", "brand + code")]
cats = [f"{lab} (n={tiers[k]['checked']})" for k, lab in order] + ["text-only reading (n=113)"]
vals = [round(tiers[k]["precision"] * 100) for k, _ in order] + [round(QUAL["claude_text_only_readings"]["share"] * 100)]
bar_chart(s, 0.6, 1.5, 7.3, 5.2, cats, [("Share that are real ads", vals)], number_format='0"%"', maxv=115, title="Real ads among flagged events, by evidence tier", point_colors=[TEAL] * 5 + [AMBER], horizontal=True)
add_text(s, 8.3, 1.65, 4.4, 5.0, [[("Checked one by one by a person", {"bold": True, "color": TEAL})], "73 of 75 flagged events were real (95% range 91 to 99%), but that is only about 4% of the 1,874 events.",
                                  [("Text-only reading (amber)", {"bold": True, "color": AMBER_DK})], "Only 61% of 113 weak-tier events look sponsored from the description alone. Text cannot hear a spoken sponsor, so this is a lower bound.",
                                  [("So", {"bold": True})], "Weak tiers are 81% of events and their true precision is between about 60% and 95%. A person checking more rows is the only fix."], size=14, space=9, name="label text")

# --------------------------------------------------------------------------------------------------------------------- 7 graph
s = new_slide("Graph formation: from 17 to 95 linked creators", notes="Before, only 17 of the 150 creators had any link, mostly Reddit co-mentions, because only 7 of 880 listed collaborators were inside our 150. We added two real relations from data we already hold: two creators who promoted the same brand, and one creator @-mentioning another. The honest reading: most links mean same brand, not influence. 55 creators still have no link.")
bar_chart(s, 0.6, 1.5, 6.6, 5.2, ["Collaboration + Reddit (before)", "+ shared brand", "+ @mentions"], [("Creators of the 150 with a link", [FACTS["linked_before"], FACTS["linked_shared"], FACTS["linked_all"]])], maxv=160, title="Creators of the 150 with at least one link",
          point_colors=[GRAY, TEAL, TEAL])
add_text(s, 7.6, 1.65, 5.1, 5.1, [[("Two new relations", {"bold": True, "color": TEAL})], "Shared brand: both creators promoted the same classified brand (1,226 links).", "@mention: one creator tags another tracked creator (34 pairs inside the 150).",
                                  [("What the graph means", {"bold": True, "color": TEAL})], "Only 7 real collaboration pairs are inside the 150, so most links say \"same niche, same brand\", not \"one influenced the other\". We call it exploratory.",
                                  [("Still open", {"bold": True, "color": TEAL})], "55 creators have no link in any data we hold and stay neutral."], size=14, space=9, name="graph text")

# --------------------------------------------------------------------------------------------------------------------- 8 spillover real
s = new_slide("Spillover on real data: what the tests say", notes="Test A compares each neighbour with itself: its lift after a sponsored post versus its lift at placebo dates. The answer is about zero. The exposed-versus-unexposed comparison gave plus 0.49 but that is confounded because exposed creators were already growing faster; never quote it alone. Stronger ties show no stronger spillover. A sponsored video draws about the same views as the creator's usual video.")
ci = PLACEBO["ci"]
rows = [["Test (real data)", "Result", "Reading"],
        ["Within-neighbour placebo (65 neighbours)", f"{PLACEBO['median_of_means']:+.2f}  ({ci[0]:+.2f} to {ci[1]:+.2f})", "No broad spillover"],
        ["Strong-evidence events only", "-0.11  (-0.17 to 0.00)", "Same answer without weak labels"],
        ["Stronger tie = more spillover?", f"trend {DOSE['trend']['spearman_tie_strength_vs_paired_difference']:+.2f}  ({DOSE['trend']['ci95'][0]:+.2f} to {DOSE['trend']['ci95'][1]:+.2f})", "No dose-response"],
        ["Sponsored vs usual YouTube video", f"views x{DIRECT['median_ratio_vs_own_typical_post']:.2f}  ({math.exp(DIRECT['ci95'][0]):.2f} to {math.exp(DIRECT['ci95'][1]):.2f})", "Same views; slightly lower likes"]]
table(s, 0.6, 1.6, 12.1, rows, [4.6, 3.6, 3.9], size=15, row_h=0.7)
add_rect(s, 0.6, 5.5, 12.1, 1.0, fill="FFF8EA", line=AMBER, name="caution")
add_text(s, 0.85, 5.68, 11.6, 0.7, [[("Read with care: ", {"bold": True, "color": AMBER_DK}), ("the exposed-versus-unexposed comparison shows +0.49, but it is confounded: exposed creators were already growing faster before the posts. We never quote it alone.", {})]], size=15, name="caution text")

# --------------------------------------------------------------------------------------------------------------------- 9 simulated spillover
s = new_slide("Would our test have found a spillover? A simulated check", notes="This slide is simulated and labelled as such. We keep every real event and neighbour and their real noise, then plant an effect of known size plus a fake pre-existing trend. A naive analysis says there is an effect every time, even at zero, and is off by 0.38. Our placebo test has no false alarms, is off by 0.05, and finds 0.25 or more every time. Limit: an effect that reaches only 20 percent of neighbours is missed, which is what GAIL's attention is meant to find.")
sim_tag(s)
t = SEMI["table"]
cats = ["0", "0.10", "0.25", "0.50", "1.00"]
naive = [round(t[k]["naive"]["detects_effect_share"] * 100) for k in ("0.0", "0.1", "0.25", "0.5", "1.0")]
plac = [round(t[k]["placebo"]["detects_effect_share"] * 100) for k in ("0.0", "0.1", "0.25", "0.5", "1.0")]
line_chart(s, 0.6, 1.5, 7.4, 5.3, cats, [("Naive analysis", naive), ("Placebo test (ours)", plac)], [GRAY, TEAL], title="Studies that say \"effect found\", by planted effect")
add_text(s, 8.4, 1.65, 4.3, 5.1, [[("Planted effect on the real network", {"bold": True, "color": TEAL})], f"Naive analysis: off by +{t['0.0']['naive']['error_vs_truth']:.2f} and finds an effect even when there is none.",
                                  f"Placebo test: off by {t['0.0']['placebo']['error_vs_truth']:+.2f}, no false alarms, finds 0.25 or more in every study.",
                                  [("Limit", {"bold": True, "color": AMBER_DK})], f"If only about 20% of neighbours are affected, we would miss it ({round(SEMI['table_effect_reaches_20_percent_of_neighbours']['1.0']['placebo']['detects_effect_share'] * 100)}% found). Finding who matters is GAIL's job."], size=14, space=9, name="sim text")

# --------------------------------------------------------------------------------------------------------------------- 10 lag and sentiment
s = new_slide("Lag and sentiment", notes="Lag: after an Instagram post, do the creator's older YouTube videos gain more views over the next two days? The method passes its positive control. The best window gives p equals 0.043 which does not survive correcting for four windows, so no lag is confirmed. The simulation shows the all-posts test would find an extra 10 percent of a normal day and the strict test 15 to 25 percent, so a large delayed effect is ruled out but a small one could hide in 17 days of readings. Sentiment: the English model is good on English, weaker on Hinglish, and weak on Hindi script until we added a multilingual model for that part. These labels are Claude's, not human ground truth.")
add_text(s, 0.6, 1.5, 6.0, 0.4, "Lag: Instagram post to YouTube views", size=18, bold=True, color=TEAL, font=HEAD, name="lag head")
sets = list(LAGP["sets"].items())
add_text(s, 0.6, 2.0, 6.0, 4.4, [[("Real data: ", {"bold": True}), ("the method finds the control effect (a YouTube upload lifts that channel's views), but the Instagram to YouTube effect is not confirmed: best window p = 0.043, not significant after correction.", {})],
                                  [("SIMULATED check: ", {"bold": True, "color": AMBER_DK}), (f"extra attention planted after real Instagram posts. All-posts test ({sets[0][1]['units']} posts) finds +10% of a normal day; the strict test ({sets[1][1]['units']} posts) finds +15 to 25%. No false alarms.", {})],
                                  [("So: ", {"bold": True}), ("a large delayed effect is ruled out; a small one could still hide in 17 days of readings.", {})]], size=14, space=9, name="lag text")
chk = load("sentiment_check_claude_labels.json")
chk2 = load("sentiment_check_claude_labels_twitter-xlm-roberta-base-sentiment.json")
cats = ["English", "Hinglish", "Hindi script"]
bar_chart(s, 7.0, 1.5, 5.7, 4.6, cats, [("English-trained model", [round(chk[k]["spearman_with_label_value"], 2) for k in ("english", "hinglish", "devanagari")]), ("Multilingual model", [round(chk2[k]["spearman_with_label_value"], 2) for k in ("english", "hinglish", "devanagari")])],
          colors=[GRAY, TEAL], number_format='0.00', maxv=1.0, title="Sentiment: agreement with labels (Spearman)", legend=True)
add_text(s, 7.0, 6.2, 5.7, 0.7, "Labels are Claude's reading of 120 comments, not human ground truth. We use the multilingual model for Hindi-script comments only.", size=12, color=GRAY, name="sent note")

# --------------------------------------------------------------------------------------------------------------------- 11 GAIL
s = new_slide("GAIL: ready to retrain, with honest limits", notes="Data side is ready: 159 independent examples from 75 neighbours, 95 of 150 creators linked, and a corrected training patch (the old one would have crashed). Eesha retrains next. The key honesty point: 159 labelled examples is small for a model with about a million parameters, so it can memorise them. We therefore judge it only on creators held out of training, against simple baselines, and we never quote the in-sample number. The old model failed our simulated acceptance check 0 of 4; we rerun it on the new checkpoint.")
add_rect(s, 0.6, 1.6, 6.0, 4.3, fill=TINT, name="ready card")
add_text(s, 0.85, 1.75, 5.5, 0.4, "Ready", size=20, bold=True, color=TEAL, font=HEAD, name="ready head")
add_text(s, 0.85, 2.3, 5.5, 3.8, [f"{FACTS['obs']} independent training examples from {FACTS['neighbours']} neighbours (was about 39)", f"{FACTS['linked_all']} of 150 creators linked in the graph (was {FACTS['linked_before']})", "Training patch fixed and tested on the live data; training files exported",
                                  "Held-out scoring and baselines prepared", "Simulated acceptance check ready to run on the new checkpoint"], size=16, bullets=True, space=9, name="ready list")
add_rect(s, 6.9, 1.6, 5.8, 4.3, fill="FFF8EA", name="limits card")
add_text(s, 7.15, 1.75, 5.3, 0.4, "Honest limits", size=20, bold=True, color=AMBER_DK, font=HEAD, name="limits head")
add_text(s, 7.15, 2.3, 5.3, 3.8, ["Only 159 labelled examples: a large model can memorise them, so we test on held-out creators only", "The old model failed our simulated acceptance check (0 of 4); it is re-run after retraining",
                                  "Real data shows no clear spillover, so expect wider coverage rather than a proven effect", "55 creators have no link and stay neutral"], size=16, bullets=True, space=9, name="limits list")
add_text(s, 0.6, 6.15, 12.1, 0.6, [[("Next: ", {"bold": True}), ("Eesha retrains, then acceptance check, held-out scores against baselines, and fusion refresh.", {})]], size=15, name="next gail")

# --------------------------------------------------------------------------------------------------------------------- 12 app
s = new_slide("The web app: scores with their basis, per platform", notes="This is the real dashboard. Each recommendation shows its 0 to 100 score, confidence range and the basis of the spillover part. The new button shows YouTube and Instagram side by side, with unknown shown honestly where we have no data. In this example the creator is strong on YouTube, Instagram cannot be judged, and the graph has no signal so the spillover is neutral. Creators with no collected posts now rank below creators with data.")
picture(s, ASSETS / "dashboard_platform_status.jpg", 0.6, 1.5, 7.4)
add_text(s, 8.4, 1.6, 4.3, 5.2, [[("Real screenshot", {"bold": True, "color": TEAL})], "Each result shows a 0 to 100 score, a confidence range and the basis of its spillover part.",
                                 [("New: platform status", {"bold": True, "color": TEAL})], "YouTube and Instagram side by side: audience, typical views and likes, engagement, first-day growth. Where data is missing it says unknown.",
                                 [("Fixed", {"bold": True, "color": TEAL})], "Creators with no collected posts now rank below creators with data."], size=14, space=9, name="app text")

# --------------------------------------------------------------------------------------------------------------------- 13 analysis tab
s = new_slide("Real results and simulated checks, side by side", notes="Every claim in the app is shown twice: what the real data says, and what a simulation says about whether our method could have found something. They are never mixed, and training uses real data only.")
picture(s, ASSETS / "analysis_real_vs_simulated.jpg", 0.6, 1.5, 7.4)
add_text(s, 8.4, 1.6, 4.3, 5.2, [[("In the app", {"bold": True, "color": TEAL})], "Analysis tab, Live results: the real result, the simulated check on top of it, and what it means.",
                                 [("The rule", {"bold": True, "color": TEAL})], "Simulated rows never enter the database, the training set or a real result. Training uses real data only."], size=14, space=9, name="analysis text")

# --------------------------------------------------------------------------------------------------------------------- 14 limits
s = new_slide("What the data cannot tell us", notes="Say these before the committee asks. They are real limits, not bugs. The central one is that real spillover looks absent in our data and our graph mostly encodes shared brands.")
lim = [("Small labelled set", "159 independent examples limit what any model can learn; results are exploratory."), ("Mostly 'same brand' links", "576 of 605 shared-brand pairs are inside the 150, only 7 real collaborations."),
       ("Short history of growth", "17 days of 2-hour readings; Instagram counts missing for 403 posts (60 filled a day)."), ("Weak-tier labels", "81% of events; true precision between about 60% and 95% until more are checked."),
       ("Hinglish sentiment", "only moderate agreement (+0.45); human labels are pending.")]
for i, (t, d) in enumerate(lim):
    y = 1.65 + i * 1.02
    icon_circle(s, 0.6, y + 0.05, 0.55, str(i + 1), fill=AMBER, color=INK, size=18)
    add_text(s, 1.4, y, 3.6, 0.8, t, size=17, bold=True, font=HEAD, anchor=MSO_ANCHOR.MIDDLE, name="limit title")
    add_text(s, 5.0, y, 7.7, 0.85, d, size=15, color=INK, anchor=MSO_ANCHOR.MIDDLE, name="limit text")

# --------------------------------------------------------------------------------------------------------------------- 15 next
s = new_slide("What comes next", notes="Next phase. The strongest lever is a bigger set of training targets from data we already hold, such as the direct effect of each sponsored post on the sponsoring creator's own audience. Then robust statistics, more Instagram counts, human label checks, and Docker for one-command demos.")
rows = [["Next step", "Why", "Who"],
        ["Retrain GAIL; held-out scoring and acceptance check", "turns the data work into model results", "Eesha, then Shimona"],
        ["Train also on the direct effect of sponsored posts", "about 1,400 more events: the biggest jump in labels", "Eesha"],
        ["Per-platform normalisation, 5 random seeds, cross-fitting", "recovers dropped pairs; steadier estimates", "Eesha"],
        ["More Instagram counts and human label checks", "fixes the weakest data and the weak labels", "Shimona"],
        ["Docker for frontend and backend", "one-command demo, with the final model", "Shimona"]]
table(s, 0.6, 1.6, 12.1, rows, [5.2, 4.6, 2.3], size=14, row_h=0.78)

# --------------------------------------------------------------------------------------------------------------------- 16 close
s = new_slide(dark=True, notes="Close with the takeaway: a complete, honest pipeline; a graph that now connects 95 of 150 creators; tests that say no broad spillover and that would have caught it; and a clear plan. Then take questions.")
add_text(s, 0.9, 2.2, 11.5, 1.2, "Thank you", size=48, bold=True, color=WHITE, font=HEAD, name="thanks")
add_text(s, 0.9, 3.5, 11.0, 2.0, ["A complete pipeline, from data to a web app.", "A graph that links 95 of 150 creators.", "Tests that would have caught a broad spillover, and do not find one.", "A clear plan for what is left."], size=20, color="CFE8E4", space=8, name="takeaways")
add_text(s, 0.9, 6.2, 11, 0.5, "Questions", size=22, bold=True, color=AMBER, name="questions")

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))
print("\n".join(WARN) if WARN else "no overflow warnings")
