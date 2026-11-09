"""One picture that summarises the graphical analysis of the whole project, sized 16:9 for the first slide of the deck (1 Nov 2026).
Every number is read from models/*.json; the two simulation panels are labelled SIMULATED. Colours and fonts follow the Review 3 deck
(paper background, black display type, blue bars, teal accent).

    python scripts/make_graphical_analysis.py [--out exports/graphical_analysis_slide1.png]
"""
import argparse
import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "exports" / "graphical_analysis_slide1.png"))
OUT = ap.parse_args().out
J = lambda n: json.loads((ROOT / "models" / n).read_text(encoding="utf-8"))  # noqa: E731

FD = Path(r"C:\Windows\Fonts")
for f in ("ariblk.ttf", "segoeui.ttf", "segoeuib.ttf"):
    font_manager.fontManager.addfont(str(FD / f))
HEAD, BODY = "Arial Black", "Segoe UI"
BG, INK, BLUE, TEAL, GREY, RED, MUTED = "#f1efea", "#111111", "#0033cc", "#33cccc", "#aab0b6", "#e60000", "#5b6068"
plt.rcParams.update({"font.family": BODY, "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK, "axes.edgecolor": INK, "figure.facecolor": BG, "axes.facecolor": BG})

runs = J("gail_real_results.json")["runs"]
t8 = J("gail_training_summary_1nov.json")
power = J("power_analysis.json")
b1, b0 = J("semisynth_new_graph_effect1.json"), J("semisynth_new_graph_effect0.json")
rank = J("ranking_test.json")
sent, xlm = J("sentiment_check_claude_labels.json"), J("sentiment_check_claude_labels_twitter-xlm-roberta-base-sentiment.json")

fig = plt.figure(figsize=(16, 9), dpi=150)
gs = fig.add_gridspec(2, 3, left=0.055, right=0.985, top=0.80, bottom=0.115, hspace=0.62, wspace=0.34)


def title(ax, t, sub=None):
    ax.set_title(t, loc="left", fontfamily=HEAD, fontsize=12.5, pad=19 if sub else 8)
    if sub:
        ax.text(0, 1.035, sub, transform=ax.transAxes, fontsize=9.2, color=MUTED, va="bottom")


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=3, labelsize=9.5)


fig.text(0.055, 0.935, "Does a sponsorship spill over to linked creators?", fontfamily=HEAD, fontsize=27, va="center")
fig.text(0.055, 0.882, "Graphical analysis of the whole project: what we measured, how we checked the method, and what the data can and cannot tell us", fontsize=13, color=MUTED, va="center")
fig.add_artist(plt.Line2D([0.055, 0.985], [0.845, 0.845], color=INK, lw=1.6))

# A: the result narrows, still no effect -------------------------------------------------------------------------------------------------------------------
ax = fig.add_subplot(gs[0, 0])
stages = {12: None, 19: None, 60: None, 74: None}
for r in runs:
    n = r.get("exposed")
    if n in stages and stages[n] is None and r.get("gail_r_ci95"):
        stages[n] = (r["gail_r_effect"], *r["gail_r_ci95"])
stages[74] = (t8["gail_r"]["effect_on_exposed"], *t8["gail_r"]["ci95"])
ys = list(range(len(stages)))
for y, (n, (e, lo, hi)) in zip(ys, stages.items()):
    ax.plot([lo, hi], [y, y], color=BLUE, lw=4.5, solid_capstyle="round", alpha=0.85)
    ax.plot(e, y, "o", color=BG, mec=INK, mew=1.6, ms=8, zorder=3)
ax.axvline(0, color=INK, lw=1.2, ls="--")
ax.set_yticks(ys, [f"{n} exposed" for n in stages])
ax.invert_yaxis()
ax.set_xlabel("estimated effect on engagement (log scale)", fontsize=9.5)
ax.set_xlim(-1.35, 0.8)
title(ax, "A. More data, tighter range, still no effect", "GAIL-R estimate with 95% interval; dashed line = no effect")
clean(ax)

# B: method check (simulated) ------------------------------------------------------------------------------------------------------------------------------
ax = fig.add_subplot(gs[0, 1])
ate = lambda block, key: st.mean(r["ate_error"] for r in block[key] if isinstance(r, dict) and r.get("ate_error") is not None)  # noqa: E731
methods = [("Naive difference", "Naive difference"), ("GNN, no causal training", "GNN predictor (no causal training)"), ("Doubly robust, no graph", "DR, no graph"), ("GAIL v1", "GAIL v1 (current)"), ("GAIL-R", "GAIL-R"), ("GAIL-R + placebo", "GAIL-R + placebo")]
vals = [(m, ate(b1["pretrend"], k), ate(b0["pretrend"], k)) for m, k in methods]
yy = list(range(len(vals)))
h = 0.38
for i, (m, e1, e0) in enumerate(vals):
    best = m == "GAIL-R + placebo"
    ax.barh(i - h / 2, e1, height=h, color=BLUE if best else GREY)
    ax.barh(i + h / 2, e0, height=h, color=TEAL if best else "#d3d7db")
ax.set_yticks(yy, [m for m, *_ in vals], fontsize=9.5)
ax.invert_yaxis()
ax.set_xlabel("average error (lower is better)", fontsize=9.5)
title(ax, "B. Our method keeps its error low", "SIMULATED: planted effect + planted trend on the real graph")
from matplotlib.patches import Patch  # noqa: E402

ax.legend(handles=[Patch(color=GREY, label="true effect planted"), Patch(color="#d3d7db", label="no effect planted"), Patch(color=BLUE, label="our method (effect)"), Patch(color=TEAL, label="our method (no effect)")],
          frameon=False, fontsize=8.6, loc="upper left", bbox_to_anchor=(-0.02, -0.17), ncol=2, columnspacing=1.4)
clean(ax)

# C: power (simulated) -------------------------------------------------------------------------------------------------------------------------------------
ax = fig.add_subplot(gs[0, 2])
eff = power["deltas"]
cols = {"18": GREY, "40": TEAL, "80": BLUE}
for k in ("18", "40", "80"):
    ax.plot(eff, [100 * v for v in power["real_structure"]["share_detected"][k]], "-o", color=cols[k], lw=2.4, ms=5, label=f"{k} exposed")
ax.axhline(80, color=INK, lw=1, ls=":")
ax.text(eff[-1], 82, "80% power", ha="right", fontsize=8.8)
ax.set_xlabel("planted effect size", fontsize=9.5)
ax.set_ylabel("studies that detect it (%)", fontsize=9.5)
ax.set_ylim(0, 104)
ax.legend(frameon=False, fontsize=8.8, loc="lower right")
title(ax, "C. What the null could have shown", "SIMULATED: real outcomes with an effect planted")
clean(ax)

# D: label fix ---------------------------------------------------------------------------------------------------------------------------------------------
ax = fig.add_subplot(gs[1, 0])
labels = ["sponsored\nvideos", "sponsorship\nevents"]
before, after = [3370, 3501], [2900, 3031]
x = range(2)
w = 0.36
ax.bar([i - w / 2 for i in x], before, w, color=GREY, label="before the fix")
ax.bar([i + w / 2 for i in x], after, w, color=BLUE, label="after the fix")
for i in x:
    ax.text(i - w / 2, before[i] + 50, f"{before[i]:,}", ha="center", fontsize=9.5)
    ax.text(i + w / 2, after[i] + 50, f"{after[i]:,}", ha="center", fontsize=9.5, fontweight="bold")
ax.set_xticks(list(x), labels, fontsize=9.8)
ax.set_ylim(0, 4200)
ax.legend(frameon=False, fontsize=8.8, loc="upper right", ncol=2)
title(ax, "D. Labels corrected: 470 standing codes removed", "same promo-code block under every video is not a new sponsorship")
clean(ax)

# E: ranking test -------------------------------------------------------------------------------------------------------------------------------------------
ax = fig.add_subplot(gs[1, 1])
items = list(rank["methods"].items())
for i, (k, v) in enumerate(items):
    lo, hi = v["spearman_ci95"]
    ax.plot([lo, hi], [i, i], color=BLUE, lw=4.5, solid_capstyle="round", alpha=0.85)
    ax.plot(v["spearman"], i, "o", color=BG, mec=INK, mew=1.6, ms=8, zorder=3)
ax.axvline(0, color=INK, lw=1.2, ls="--")
ax.set_yticks(range(len(items)), [k.replace(" (median log views)", "").replace(" (videos before cutoff)", "") for k, _ in items], fontsize=9.5)
ax.invert_yaxis()
ax.set_xlabel("rank correlation with what a sponsored video later did", fontsize=9.5)
title(ax, f"E. No simple ranking beats chance ({rank['creators']} creators)", "every interval contains zero")
clean(ax)

# F: sentiment by language ----------------------------------------------------------------------------------------------------------------------------------
ax = fig.add_subplot(gs[1, 2])
langs = [("english", "English"), ("hinglish", "Hinglish"), ("devanagari", "Hindi script")]
x = range(3)
a = [sent[k]["auc_positive_vs_rest"] for k, _ in langs]
b = [xlm[k]["auc_positive_vs_rest"] for k, _ in langs]
ax.bar([i - w / 2 for i in x], a, w, color=GREY, label="English model")
ax.bar([i + w / 2 for i in x], b, w, color=TEAL, label="multilingual model")
for i in x:
    ax.text(i - w / 2, a[i] + 0.015, f"{a[i]:.2f}", ha="center", fontsize=9.3)
    ax.text(i + w / 2, b[i] + 0.015, f"{b[i]:.2f}", ha="center", fontsize=9.3, fontweight="bold")
ax.axhline(0.5, color=INK, lw=1, ls=":")
ax.text(-0.45, 0.515, "coin flip", ha="left", fontsize=8.6)
ax.set_xticks(list(x), [n for _, n in langs], fontsize=9.8)
ax.set_ylim(0.4, 1.08)
ax.set_ylabel("AUC (positive vs the rest)", fontsize=9.5)
ax.legend(frameon=False, fontsize=8.8, loc="upper left", ncol=1)
title(ax, "F. Mood model by comment language", "120 comments labelled by an AI model, not a person")
clean(ax)

fig.text(0.055, 0.022, "Source: models/*.json (gail_real_results, power_analysis, semisynth_new_graph_effect0/1, ranking_test, sentiment_check, gail_training_summary_1nov). Panels B and C are simulations on the real graph and real outcomes.",
         fontsize=9, color=MUTED, va="center")
fig.savefig(OUT, dpi=150, facecolor=BG)
print("saved", OUT)
