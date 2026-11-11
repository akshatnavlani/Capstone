r"""Figures for the Phase-3 report (12 Nov 2026). Numbers: database counts on 12 Nov 2026, models/published_baselines_eesha.json,
AUDIENCE_FLOW_RESULTS_8NOV.md (cross-platform Granger, 10 Nov run), models/platform_pairs.json.

    venv\Scripts\python.exe report\make_report_figures.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 12, "axes.spines.top": False, "axes.spines.right": False})
BLUE, GREY, ORANGE = "#1f4e9c", "#9aa3ad", "#d9822b"

# 1. data collected (database, 12 Nov 2026)
data = [("YouTube videos", 184251), ("YouTube comments", 2296861), ("Instagram posts", 3286), ("Instagram comments", 34444),
        ("Reddit posts", 3308), ("Engagement readings", 573368), ("Sponsorship events", 3446)]
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.barh([d[0] for d in data][::-1], [d[1] for d in data][::-1], color=BLUE)
ax.set_xscale("log")
for i, (_, v) in enumerate(data[::-1]):
    ax.text(v * 1.15, i, f"{v:,}", va="center", fontsize=11)
ax.set_xlabel("Records in the database (log scale)")
ax.set_xlim(1000, 2e7)
fig.tight_layout(); fig.savefig(OUT / "fig_data_volume.png", dpi=200); plt.close(fig)

# 2. cross-platform Granger (105 creators, 10 Nov 2026); the shifted-timing median is stored only for the first direction
fig, ax = plt.subplots(figsize=(7.5, 4))
labels = ["Instagram posts ->\nYouTube comments (old videos)", "YouTube comments ->\nInstagram posts"]
ax.bar([-0.18, 0.82], [1.559, 1.561], 0.36, color=BLUE, label="Real timing (105 creators)")
ax.bar([0.18], [1.016], 0.36, color=GREY, label="Shifted timing, median of 500 placebo runs")
for x, f, t in ((-0.18, 1.559, "p = 0.002"), (0.82, 1.561, "p = 0.014")):
    ax.text(x, f + 0.04, t, ha="center", fontsize=11, fontweight="bold")
ax.set_xticks([0, 0.82]); ax.set_xticklabels(labels)
ax.set_ylabel("Granger F statistic (lags 1-3 days)")
ax.set_ylim(0, 2.3); ax.legend(frameon=False, loc="upper center", ncol=1, fontsize=10)
fig.tight_layout(); fig.savefig(OUT / "fig_cross_platform_granger.png", dpi=200); plt.close(fig)

# 3. published baselines on the planted-effect benchmark
b = json.loads((ROOT / "models" / "published_baselines_eesha.json").read_text(encoding="utf-8"))
rows = b["rows"]
fig, ax = plt.subplots(figsize=(8, 4.2))
names = [r["method"] for r in rows]
y = range(len(rows))
ax.barh([i - 0.2 for i in y], [r["no_trend"] for r in rows], 0.4, color=BLUE, label="No pre-trend")
ax.barh([i + 0.2 for i in y], [r["pre_trend"] for r in rows], 0.4, color=ORANGE, label="With pre-trend")
ax.set_yticks(list(y)); ax.set_yticklabels(names); ax.invert_yaxis()
ax.set_xlabel("Per-creator error, PEHE (lower is better)")
ax.legend(frameon=False, loc="lower right", fontsize=10)
fig.tight_layout(); fig.savefig(OUT / "fig_baselines_pehe.png", dpi=200); plt.close(fig)

# 4. same creator on both platforms (models/platform_pairs.json)
pp = json.loads((ROOT / "models" / "platform_pairs.json").read_text(encoding="utf-8"))
vals = sorted(c["median_difference_adjusted"] for c in pp["creators"] if c.get("median_difference_adjusted") is not None)
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.bar(range(len(vals)), vals, color=[BLUE if v > 0 else ORANGE for v in vals])
ax.axhline(0, color="black", lw=0.8)
ax.set_xlabel(f"Creators ({len(vals)}), sorted"); ax.set_ylabel("Instagram minus YouTube\n(log, placebo-adjusted)")
ax.set_xticks([])
fig.tight_layout(); fig.savefig(OUT / "fig_platform_pairs.png", dpi=200); plt.close(fig)
print("figures ->", OUT, sorted(p.name for p in OUT.glob("*.png")))
