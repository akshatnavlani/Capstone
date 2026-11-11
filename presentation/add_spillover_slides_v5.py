"""Review3_Presentation_v4.pptx + two spillover results slides (every test, 10 Nov 2026) -> Review3_Presentation_v5.pptx.
v4 is left untouched. Numbers come from AUDIENCE_FLOW_RESULTS_8NOV.md, SPILLOVER_RESULTS_7NOV.md and models/*.json.

    python presentation/add_spillover_slides_v5.py
"""
import copy
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
SRC, OUT = HERE / "Review3_Presentation_v4.pptx", HERE / "Review3_Presentation_v5.pptx"
FONT, RED, BLUE, TINT, GREEN, GRAY = "Trebuchet MS", "FF0000", "0033CC", "E8EEFB", "D9F2DC", "F2F2F2"

prs = Presentation(SRC)
ref = prs.slides[18]   # "Results and Discussion (2 of 2)": copy its background, title box and rule


def new_slide(title):
    s = prs.slides.add_slide(ref.slide_layout)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = RGBColor.from_string("F1EFEA")
    for sh in ref.shapes:
        if sh.name in ("Rectangle 1", "Text Box 34"):
            s.shapes._spTree.append(copy.deepcopy(sh._element))
    for sh in s.shapes:
        if sh.name == "Text Box 34":
            sh.text_frame.paragraphs[0].runs[0].text = title
            for r in sh.text_frame.paragraphs[0].runs[1:]:
                r.text = ""
    return s


def text(s, x, y, w, h, lines, size=13, color=BLUE, bold_first=False):
    tf = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(5)
        r = p.add_run()
        r.text = line
        r.font.name, r.font.size, r.font.color.rgb = FONT, Pt(size), RGBColor.from_string(color)
        r.font.bold = bold_first and i == 0


def table(s, x, y, w, rows, col_w, size=11, row_h=0.34, fills=None):
    t = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows))).table
    for j, cw in enumerate(col_w):
        t.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        t.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = RGBColor.from_string(BLUE if i == 0 else (fills or {}).get(i, TINT))
            c.margin_top = c.margin_bottom = Inches(0.03)
            p = c.text_frame.paragraphs[0]
            p.text = ""
            r = p.add_run()
            r.text = val
            r.font.name, r.font.size = FONT, Pt(size)
            r.font.bold = i == 0 or (j == len(row) - 1 and val.startswith("DETECTED"))
            r.font.color.rgb = RGBColor.from_string("FFFFFF" if i == 0 else "111111")


# ---- slide A: every spillover test
a = new_slide("Spillover: every test we ran, every result")
rows = [["Test (plan written and pushed before the data)", "Size", "Result"],
        ["Instagram post -> comments on the same creator's OLD YouTube videos, 1-3 days", "105 creators", "DETECTED, p 0.002"],
        ["YouTube activity -> the same creator's Instagram posts", "105 creators", "DETECTED, p 0.014"],
        ["Creator A posts -> comments on linked creator B's old videos (tag pairs)", "238 pairs", "Not detected (p 0.054, near miss)"],
        ["Same, creators who made a video together", "164 pairs", "Not detected"],
        ["A sponsored -> linked creators' engagement (GAIL-R)", "298 exposed", "Not detected"],
        ["A tags B -> A's commenters move to B / B's 7-day engagement", "100 / 116 events", "Not detected"],
        ["A tags B -> B's comments name A", "100 events", "Not detected"],
        ["A sponsors brand X -> B's comments name brand X", "3,985 events", "Not detected"],
        ["A and B in one video -> B's engagement", "177 events", "Not detected"],
        ["Sponsored post on one app -> same creator's other app", "34 events", "Not detected"],
        ["Sponsored video -> brand named on the creator's next videos", "431 events", "Not detected"],
        ["A sponsors -> B's old videos' views within 48 h", "63 events", "Not detected"]]
table(a, 0.6, 1.9, 12.1, rows, [7.4, 1.8, 2.9], fills={1: GREEN, 2: GREEN})
text(a, 0.6, 6.45, 12.1, 0.8, ["Every test was run once and every result is shown. Granger and placebo tests show prediction, not proof of cause."], size=11)

# ---- slide B: what it means
b = new_slide("Spillover: where it was found, and what is still running")
text(b, 0.6, 1.95, 5.9, 3.0, [
    "Found: within one creator, across platforms",
    "When a creator posts on Instagram, comments on their older YouTube videos rise over the next 1-3 days. Real timing beats 500 shifted timings (p 0.002, 105 creators); the other direction also holds (p 0.014).",
    "Comments on videos older than 72 h remove the effect of a new upload.",
    "A 'how' test (creators who point followers to the other app) was not supported: the audience seems to cross over by itself."],
    size=13, bold_first=True)
text(b, 6.8, 1.95, 5.9, 3.0, [
    "Not found: between different creators",
    "Ten tests, from 34 to 3,985 events. The strongest (every day of a year for 238 tag pairs) beat shuffled timing (p 0.002) but not random unlinked pairs (p 0.054): most of the shared timing is the common calendar.",
    "Large spillover between creators is ruled out; a small one cannot be told from zero with our data."],
    size=13, bold_first=True)
table(b, 0.6, 5.05, 12.1, [["Still running (rules fixed in advance)", "Result date"],
                           ["Tag retest with up to 300 comments per video (441 events)", "13-14 Nov 2026"],
                           ["Big creator -> small guest's subscribers, 48 h", "20 Nov 2026"],
                           ["New collaborations -> B's subscribers, 48 h (readings every 30 min)", "20 Nov 2026"]], [9.1, 3.0], size=11)

# put the two slides right after "Results and Discussion (2 of 2)"
lst = prs.slides._sldIdLst
els = list(lst)
new = els[-2:]
for el in new:
    lst.remove(el)
pos = 18   # index of the reference slide in the v4 order
for k, el in enumerate(new, 1):
    lst.insert(pos + k, el)
prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))
