"""Score the sentiment model on the hand-labelled Hinglish comments (novelty F). Offline; writes models/hinglish_check.json.

    python scripts/score_hinglish_sample.py [--labels exports/hinglish_labels_partial.csv]

Labels come from Shimona (positive / neutral / negative; skip rows are ignored). Each comment is cleaned of HTML tags and scored with
  * the model the pipeline uses for Latin-script comments (cardiffnlp/twitter-roberta-base-sentiment-latest), and
  * the multilingual XLM-R model the pipeline uses only for Devanagari comments (cardiffnlp/twitter-xlm-roberta-base-sentiment), to see whether it would do better on Hinglish.
The model score is safety = P(positive) + 0.5 P(neutral), 0..1. Reported: Spearman rank correlation with the labels (negative 0, neutral 0.5, positive 1) and the AUC of telling
positive from negative comments (0.5 = chance), each with a 95% bootstrap interval. With a few dozen labels the intervals are wide: read this as a rough check, not a benchmark.
"""
import argparse
import csv
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VALUE = {"negative": 0.0, "neutral": 0.5, "positive": 1.0}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text))).strip()


def spearman(a, b) -> float:
    ra, rb = np.argsort(np.argsort(a)).astype(float), np.argsort(np.argsort(b)).astype(float)
    return 0.0 if ra.std() == 0 or rb.std() == 0 else float(np.corrcoef(ra, rb)[0, 1])


def auc_pos_vs_neg(score, label) -> float | None:
    pos, neg = score[label == 1.0], score[label == 0.0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    return float(np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg]))


def boot(fn, score, label, draws=2000, seed=0):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(draws):
        i = rng.integers(0, len(label), len(label))
        v = fn(score[i], label[i])
        if v is not None and v == v:
            vals.append(v)
    return [round(float(np.quantile(vals, 0.025)), 2), round(float(np.quantile(vals, 0.975)), 2)] if len(vals) > 100 else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", default=str(ROOT / "exports" / "hinglish_labels_partial.csv"))
    ap.add_argument("--out", default=str(ROOT / "models" / "hinglish_check.json"))
    args = ap.parse_args()
    rows = [r for r in list(csv.reader(open(args.labels, encoding="utf-8-sig", newline="")))[1:] if len(r) > 3 and r[3].strip().lower() in VALUE]
    texts = [clean(r[2]) for r in rows]
    label = np.array([VALUE[r[3].strip().lower()] for r in rows])
    print(f"{len(rows)} labelled comments: {int((label == 1).sum())} positive, {int((label == .5).sum())} neutral, {int((label == 0).sum())} negative", flush=True)

    from ml.temporal.sentiment import MODEL_NAME, MULTILINGUAL_MODEL, SentimentScorer, multilingual_scorer
    results = {}
    for name, make in ((MODEL_NAME, lambda: SentimentScorer(MODEL_NAME)), (MULTILINGUAL_MODEL, multilingual_scorer)):
        score = np.asarray(make().score(texts), float)
        ok = ~np.isnan(score)
        s, l = score[ok], label[ok]
        res = {"n": int(ok.sum()), "spearman": round(spearman(s, l), 2), "spearman_ci95": boot(spearman, s, l), "auc_pos_vs_neg": None, "mean_score_by_label": {}}
        a = auc_pos_vs_neg(s, l)
        res["auc_pos_vs_neg"] = round(a, 2) if a is not None else None
        res["auc_ci95"] = boot(auc_pos_vs_neg, s, l)
        for k, v in VALUE.items():
            if (l == v).any():
                res["mean_score_by_label"][k] = round(float(s[l == v].mean()), 2)
        results[name] = res
        print(f"{name}: Spearman {res['spearman']} {res['spearman_ci95']}, AUC pos vs neg {res['auc_pos_vs_neg']} {res['auc_ci95']}, mean score by label {res['mean_score_by_label']}", flush=True)
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "labelled": len(rows), "labels": {k: int((label == v).sum()) for k, v in VALUE.items()}, "models": results,
           "limits": "a few dozen labels from one labeller, drawn at random from code-mixed YouTube comments (at most 3 per creator); the intervals are wide; skipped rows (links, unclear) are left out"}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
