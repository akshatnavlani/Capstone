"""Two pictures for the deck (1 Nov 2026): the model framework (data to app, with the current branches and weights) and the Gantt chart.
Colours and fonts follow the Review 3 deck: paper background, black display type, pale blue / yellow boxes, green = done, amber = remaining.

    python scripts/make_deck_diagrams.py      -> presentation/assets/dual_framework_v4.png, gantt_v4.png
"""
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTD = ROOT / "presentation" / "assets"
FD = Path(r"C:\Windows\Fonts")
for f in ("segoeui.ttf", "segoeuib.ttf", "ariblk.ttf"):
    font_manager.fontManager.addfont(str(FD / f))
plt.rcParams["font.family"] = "Segoe UI"
PAPER, INK, MUTED = "#f1efea", "#111111", "#5b6068"

# ---------------------------------------------------------------- framework ----------------------------------------------------------------------------------------
fig = plt.figure(figsize=(13.2, 5.6), dpi=150, facecolor=PAPER)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 13.2)
ax.set_ylim(0, 5.6)
ax.axis("off")
ax.text(6.6, 5.3, "Three branches on one creator graph, fused into one score", ha="center", fontsize=15, fontweight="bold", color="#1f4e8c")


def box(x, y, w, h, title, lines, fill, edge="#222"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08", fc=fill, ec=edge, lw=1.3))
    ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="center", fontsize=11.5, fontweight="bold", color=INK)
    ax.text(x + w / 2, y + h - 0.55, "\n".join(lines), ha="center", va="top", fontsize=9.3, color="#222", linespacing=1.3)


def arrow(x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color="#222", lw=1.3))


BLUE, YEL, GRN = "#dce8f6", "#fdf7c6", "#e1f2e4"
box(0.15, 2.0, 1.75, 1.7, "Data sources", ["YouTube API", "Instagram", "Reddit"], BLUE)
box(2.25, 2.0, 1.85, 1.7, "Supabase", ["409 creators", "posts, comments,", "sponsor labels"], BLUE)
box(4.45, 2.0, 2.0, 1.7, "Features + graph", ["CLIP and BERT features", "collaboration, co-occurrence,", "@mention, shared brand"], YEL)
box(7.0, 3.75, 2.45, 1.3, "Spillover branch", ["GAIL-R, placebo penalty", "shown as context, weight 0"], YEL)
box(7.0, 2.05, 2.45, 1.3, "Mood branch", ["comment sentiment,", "risk along supported links"], YEL)
box(7.0, 0.35, 2.45, 1.3, "Creator-fit branch", ["CLIP and BERT match", "to the brief"], YEL)
box(9.95, 1.95, 1.65, 1.9, "Fusion", ["0.5 mood", "0.5 fit", "range, grade A to D"], GRN)
box(11.9, 2.25, 1.15, 1.3, "App", ["API,", "dashboard"], BLUE)
arrow(1.9, 2.85, 2.25, 2.85)
arrow(4.1, 2.85, 4.45, 2.85)
for yy in (4.4, 2.7, 1.0):
    arrow(6.45, 2.85, 7.0, yy)
arrow(9.45, 2.7, 9.95, 2.9)
arrow(9.45, 1.0, 9.95, 2.4)
arrow(9.45, 4.4, 9.95, 3.5)
arrow(11.6, 2.9, 11.9, 2.9)
fig.savefig(OUTD / "dual_framework_v4.png", dpi=150, facecolor=PAPER)
plt.close(fig)

# ---------------------------------------------------------------- Gantt --------------------------------------------------------------------------------------------
D = date
rows = [
    ("A. DATA INFRASTRUCTURE", None, None, None),
    ("Ingestion and schema (409 creators)", D(2026, 8, 1), D(2026, 8, 12), "done"),
    ("Daily collection, 24-month YouTube history", D(2026, 10, 11), D(2026, 10, 27), "done"),
    ("Sponsorship labels and standing-code fix", D(2026, 10, 14), D(2026, 11, 1), "done"),
    ("B. ML CORE", None, None, None),
    ("Graph and first GAIL run", D(2026, 8, 10), D(2026, 8, 26), "done"),
    ("Placebo and simulated validation", D(2026, 10, 11), D(2026, 10, 27), "done"),
    ("GAIL-R, benchmark, run 8 retrain", D(2026, 10, 28), D(2026, 11, 1), "done"),
    ("GPU run, 20+ seeds", D(2026, 11, 3), D(2026, 11, 17), "todo"),
    ("C. TEMPORAL AND FEATURES", None, None, None),
    ("Sentiment, lag tests, CLIP and BERT", D(2026, 10, 1), D(2026, 10, 12), "done"),
    ("Hinglish check, human label checks", D(2026, 10, 28), D(2026, 11, 22), "todo"),
    ("D. FUSION AND RANKING", None, None, None),
    ("Fusion layer, recommendation engine", D(2026, 9, 1), D(2026, 9, 22), "done"),
    ("Calibration, evidence grade, new weights", D(2026, 10, 2), D(2026, 11, 1), "done"),
    ("Rank by expected engagement per rupee", D(2026, 11, 5), D(2026, 11, 22), "todo"),
    ("E. APPLICATION", None, None, None),
    ("Dashboard, graph, Analysis tab", D(2026, 9, 10), D(2026, 10, 10), "done"),
    ("Creator Passport, Insights, redesign, Docker", D(2026, 10, 31), D(2026, 11, 1), "done"),
    ("Load and security test", D(2026, 11, 5), D(2026, 11, 20), "todo"),
    ("F. DOCUMENTS AND EVALUATION", None, None, None),
    ("Reviews 1 and 2, results pack, survey", D(2026, 8, 3), D(2026, 11, 1), "done"),
    ("Paper and thesis", D(2026, 11, 3), D(2026, 12, 12), "todo"),
]
fig, ax = plt.subplots(figsize=(13.2, 6.5), dpi=150, facecolor=PAPER)
ax.set_facecolor(PAPER)
n = len(rows)
for i, (label, a, b, st) in enumerate(rows):
    y = n - 1 - i
    if a is None:
        ax.axhspan(y - 0.45, y + 0.45, color="#e3e8f2", zorder=0)
        ax.text(mdates.date2num(D(2026, 6, 14)), y, label, va="center", fontsize=9.6, fontweight="bold", color="#1f2f66")
        continue
    ax.barh(y, (b - a).days or 1, left=mdates.date2num(a), height=0.55, color="#2f9e5a" if st == "done" else "#f0a630", zorder=2)
    ax.text(mdates.date2num(D(2026, 6, 14)), y, "   " + label, va="center", fontsize=8.8, color=INK)
ax.axvline(mdates.date2num(D(2026, 11, 1)), color="#c1121f", ls="--", lw=1.4)
ax.text(mdates.date2num(D(2026, 11, 1)) + 1.5, -1.0, "Current (1 Nov)", color="#c1121f", ha="left", fontsize=9, fontweight="bold")
ax.xaxis_date()
ax.set_xlim(mdates.date2num(D(2026, 6, 12)), mdates.date2num(D(2026, 12, 20)))
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%B"))
ax.xaxis.tick_top()
ax.set_yticks([])
ax.set_ylim(-1.7, n - 0.1)
for s in ("left", "right", "bottom", "top"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="x", labelsize=10, length=0)
ax.grid(axis="x", color="#d6d3cb", lw=0.7, zorder=0)
ax.text(mdates.date2num(D(2026, 6, 14)), -1.35, "■ Completed", color="#2f9e5a", fontsize=9.5, fontweight="bold")
ax.text(mdates.date2num(D(2026, 7, 14)), -1.35, "■ Remaining (after review)", color="#f0a630", fontsize=9.5, fontweight="bold")
fig.tight_layout(pad=0.4)
fig.savefig(OUTD / "gantt_v4.png", dpi=150, facecolor=PAPER)
print("saved dual_framework_v4.png and gantt_v4.png")
