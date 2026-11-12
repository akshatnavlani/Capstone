r"""One-page-style PDF of every spillover test and its result (12 Nov 2026). Sources: AUDIENCE_FLOW_RESULTS_8NOV.md,
models/audience_flow_results_rep_9nov.json, models/tag_confirmation_results_12nov.json, models/between_creator_granger_10nov.json,
SPILLOVER_RESULTS_7NOV.md; row 11 from the team's 11 Nov GAIL-R run (paper draft).

    python report\make_spillover_results_pdf.py      (system Python 3.12: reportlab)
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(r"C:\Users\Shimona\Downloads\Spillover_Results_12Nov2026.pdf")
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping

pdfmetrics.registerFont(TTFont("TNR", "C:/Windows/Fonts/times.ttf"))
pdfmetrics.registerFont(TTFont("TNR-B", "C:/Windows/Fonts/timesbd.ttf"))
addMapping("TNR", 0, 0, "TNR"), addMapping("TNR", 1, 0, "TNR-B"), addMapping("TNR", 0, 1, "TNR"), addMapping("TNR", 1, 1, "TNR-B")
F, FB = "TNR", "TNR-B"
body = ParagraphStyle("b", fontName=F, fontSize=9.5, leading=11.5)
bold = ParagraphStyle("bb", parent=body, fontName=FB)
h1 = ParagraphStyle("h1", fontName=FB, fontSize=17, leading=21, alignment=TA_CENTER, spaceAfter=4)
sub = ParagraphStyle("s", fontName=F, fontSize=10, leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#444444"), spaceAfter=10)
h2 = ParagraphStyle("h2", fontName=FB, fontSize=12.5, leading=15, spaceBefore=10, spaceAfter=5)
note = ParagraphStyle("n", parent=body, fontSize=8.5, leading=10.5, textColor=colors.HexColor("#444444"))
GREEN, GREY, HEAD = colors.HexColor("#DDF1E0"), colors.HexColor("#F4F4F4"), colors.HexColor("#1F4E9C")


def table(header, rows, widths, detected=()):
    data = [[Paragraph(f"<font color='white'><b>{h}</b></font>", body) for h in header]]
    for r in rows:
        data.append([Paragraph(str(c), bold if i == len(r) - 1 and "Detected" in str(c) and "Not" not in str(c) else body) for i, c in enumerate(r)])
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), HEAD), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for i in range(1, len(data)):
        style.append(("BACKGROUND", (0, i), (-1, i), GREEN if (i - 1) in detected else (GREY if i % 2 == 0 else colors.white)))
    t.setStyle(TableStyle(style))
    return t


W = [0.8, 7.4, 2.7, 3.9, 2.6]
H = ["#", "Test", "Size", "Result", "Verdict"]
story = [Paragraph("Spillover: every test and its result", h1),
         Paragraph("Influencer-Brand Matching via GAIL &amp; Graph Spillover — Indian fitness and health creators — 12 November 2026", sub),
         Paragraph("Every test's rules were written down and pushed to GitHub before the data was examined, and each test was run once. "
                   "Green rows passed the pre-set mark: 95% range above zero and placebo (random dates or unlinked creators) showing nothing.", body)]

story += [Paragraph("A. Same creator, across platforms", h2), table(H, [
    ["1", "Instagram post → more comments on the same creator's older YouTube videos (1–3 days later)", "105 creators", "p = 0.002 (real timing vs 500 random timings)", "Detected"],
    ["2", "YouTube activity → the same creator posts more on Instagram", "105 creators", "p = 0.014", "Detected"]], W, detected=(0, 1))]

story += [Paragraph("B. Between creators, after a tag (creator A tags creator B)", h2), table(H, [
    ["3", "B's views and likes in the 7 days after the tag — main replication (2 years of tags)", "291 events, 173 pairs", "+10% (range +0.5% to +20%); random dates −1%", "Detected"],
    ["4", "Same, first run (1 year)", "116 events", "+4% (range −8% to +16%)", "Not detected"],
    ["5", "Same, check on 35 new creator pairs", "42 events", "−11% (range −29% to +13%); too few events to tell", "Not detected"],
    ["6", "A's commenters start commenting on B's videos", "246 events", "0.0%", "Not detected"],
    ["7", "B's comments start naming A", "100 events", "no change", "Not detected"],
    ["8", "A's posting predicts comments on B's older videos (every day for a year)", "238 pairs", "p = 0.002 vs random timing; p = 0.054 vs unlinked pairs (needed &lt; 0.05)", "Not detected (very close)"],
    ["9", "Same, creators who made a video together", "164 pairs", "p = 0.034 vs random timing; p = 0.124 vs unlinked pairs", "Not detected"],
    ["10", "A and B in the same video → B's engagement", "177 events", "no change", "Not detected"]], W, detected=(0,))]

story += [Paragraph("C. Between creators, after a sponsorship (a brand pays creator A)", h2), table(H, [
    ["11", "GAIL-R: A sponsored → linked creators' engagement over 30 days*", "305 exposed, 106 creators", "−16% (range −30% to +3%)", "Not detected; a rise above 3% is ruled out"],
    ["12", "A sponsors brand X → B's comments mention brand X", "3,985 events", "no change", "Not detected"],
    ["13", "A sponsors → B's older videos get more views within 48 h", "63 events", "no change", "Not detected"],
    ["14", "Sponsored post on one app → the same creator's other app", "34 events", "no change", "Not detected"],
    ["15", "Sponsored video → brand named on the creator's next videos", "431 events", "no change", "Not detected"]], W)]

story += [KeepTogether([Paragraph("D. Still running (results on 20 November 2026)", h2), table(["#", "Test", "So far", "Needs", "Readings"], [
    ["16", "New collaborations → tagged creator's subscribers within 48 h", "10 collaborations", "20", "every 30 minutes"],
    ["17", "Big creator → small guest's subscribers within 48 h", "0 events", "20", "every 30 minutes"]], W)])]

story += [Paragraph("In one line each", h2),
          Paragraph("<b>Strong:</b> a creator's fans follow them across YouTube and Instagram (tests 1 and 2).", body), Spacer(1, 3),
          Paragraph("<b>Found once:</b> being tagged by another creator gives about a 10% one-week boost in views and likes (test 3); "
                    "a small check on new pairs could not confirm or rule it out (test 5), and more data is being collected.", body), Spacer(1, 3),
          Paragraph("<b>Not found:</b> a sponsorship does not measurably help the sponsored creator's network over a month; any effect is small "
                    "(tests 11–15).", body), Spacer(1, 8),
          Paragraph("* Row 11 is from the team's GAIL-R run of 11 November 2026 (paper draft). Ranges are 95% intervals; percentages are "
                    "approximate conversions of log-scale effects. Placebo and Granger tests show prediction in time, not proof of cause. "
                    "Plans and result files: AUDIENCE_FLOW_PLAN_8NOV.md, TAG_ENGAGEMENT_CONFIRMATION_PLAN_12NOV.md, "
                    "BETWEEN_CREATOR_GRANGER_PLAN_10NOV.md, AUDIENCE_FLOW_RESULTS_8NOV.md and models/*.json in the repository.", note)]

SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                  title="Spillover results", author="Capstone team 011").build(story)
print("saved", OUT)
