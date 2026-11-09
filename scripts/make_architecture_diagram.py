"""Draws the five-module architecture picture used on the architecture slide (1 Nov 2026), with the current design: spillover is context, fusion is 0 / 0.5 / 0.5.
Same layout idea as the earlier diagram (role, input, output, feeds-into per module), same colours per module.

    python scripts/make_architecture_diagram.py        -> presentation/assets/architecture_modules_v3.png
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FD = Path(r"C:\Windows\Fonts")
for f in ("segoeui.ttf", "segoeuib.ttf"):
    font_manager.fontManager.addfont(str(FD / f))
plt.rcParams["font.family"] = "Segoe UI"

MODULES = [
    ("Module 1: Data collection", "#1f5fbf", "#e8f0fd",
     "Entry point of the system",
     "YouTube, Instagram and Reddit\n(daily; growth readings every 2 h)",
     "409 creators in Supabase Postgres;\nsponsorship labels in six evidence tiers",
     "Module 2"),
    ("Module 2: Features and graph", "#1f8f4e", "#e9f6ee",
     "Turns raw data into model inputs",
     "Posts, comments, thumbnails,\nrelated accounts and mentions",
     "CLIP and BERT creator features; links:\ncollaboration, co-occurrence, @mention",
     "Modules 3 and 4"),
    ("Module 3: Model branches", "#7b3fb8", "#f2ebfa",
     "Spillover context and audience mood",
     "Creator graph and features;\ncomment sentiment",
     "GAIL-R spillover (context only);\nmood score with risk along links",
     "Module 4"),
    ("Module 4: Fusion", "#e07a10", "#fdf1e3",
     "One score with an honest range",
     "Mood score and creator-fit score\n(spillover shown, weight 0)",
     "final = 100 x (0.5 mood + 0.5 fit);\nrange and evidence grade A to D",
     "Module 5"),
    ("Module 5: API and app", "#16a5a5", "#e4f6f6",
     "Serves the shortlist to the brand",
     "Brief: product, budget,\nregion, audience hint",
     "Ranked creators with score, range, grade,\nclash warning; Creator Passport; Insights",
     "Brand client"),
]

W, H = 7.4, 5.55
fig = plt.figure(figsize=(W, H), dpi=220, facecolor="white")
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")

top, gap, card_h = H - 0.12, 0.2, 0.9
for i, (title, edge, fill, role, inp, out, feeds) in enumerate(MODULES):
    y = top - i * (card_h + gap) - card_h
    ax.add_patch(FancyBboxPatch((0.12, y), W - 0.24, card_h, boxstyle="round,pad=0,rounding_size=0.08", fc=fill, ec=edge, lw=1.4))
    ax.text(W / 2, y + card_h - 0.14, title, ha="center", va="center", fontsize=9.6, fontweight="bold", color=edge)
    ax.plot([0.12, W - 0.12], [y + card_h - 0.27, y + card_h - 0.27], color=edge, lw=0.7)
    cols = [(0.22, "Role", role), (1.78, "Input", inp), (3.6, "Output", out), (6.3, "Feeds into", feeds)]
    for x, head, body in cols:
        ax.text(x, y + card_h - 0.4, head + ":", fontsize=6.9, fontweight="bold", color=edge, va="top")
        ax.text(x, y + card_h - 0.54, body, fontsize=6.3, color="#1b1b1b", va="top", linespacing=1.25)
    if i < len(MODULES) - 1:
        ax.annotate("", xy=(W / 2, y - gap + 0.02), xytext=(W / 2, y - 0.01), arrowprops=dict(arrowstyle="-|>", color="#333", lw=1.1))

fig.savefig(ROOT / "presentation" / "assets" / "architecture_modules_v3.png", dpi=220, facecolor="white")
print("saved presentation/assets/architecture_modules_v3.png")
