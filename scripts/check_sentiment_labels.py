"""Compare the sentiment scorer with labels of the 120 sampled comments, per language (READ ONLY on the database).

    python scripts/check_sentiment_labels.py [--labels models/sentiment_labels_by_claude.json] [--human]

Default labels = `models/sentiment_labels_by_claude.json`: made by Claude on 26 Oct 2026 reading the comments WITHOUT their model scores. They are NOT human ground truth
(one reader, no second opinion, ambiguous jokes marked neutral); they give an early, indicative accuracy. With `--human` the labels come from `sentiment_review.verdict`
instead (positive / negative / neutral / unclear) once a person has filled it in, and that result replaces this one.
Score = the safety score of ml/temporal/sentiment.py (positive probability + 0.5 x neutral probability). Label value: positive 1, neutral 0.5, negative 0.
Reports per language: n, AUC of the score for positive vs the rest and for negative vs the rest, Spearman of score with label value, and the mean score by label.
"""
import argparse
import json
import os
import statistics as st
import sys
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from ml.sponsorship_quality import auc  # noqa: E402
from run_ranking_test import spearman  # noqa: E402

import numpy as np  # noqa: E402

VALUE = {"positive": 1.0, "neutral": 0.5, "negative": 0.0}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", default=str(ROOT / "models" / "sentiment_labels_by_claude.json"))
    ap.add_argument("--human", action="store_true")
    ap.add_argument("--model", help="score the comments again with this Hugging Face model (must be in the local cache) instead of using the stored model_score")
    args = ap.parse_args()
    url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env")["DATABASE_URL"]
    cur = psycopg2.connect(url).cursor()
    cur.execute("select batch, position, language, model_score, verdict, comment_text from sentiment_review where model_score is not null order by batch, position")
    data = cur.fetchall()
    if args.model:
        from ml.temporal.sentiment import SentimentScorer

        from ml.temporal.sentiment import multilingual_scorer

        scorer = multilingual_scorer(args.model) if "xlm-roberta" in args.model else SentimentScorer(args.model)
        new = scorer.score([d[5] for d in data])
        data = [d[:3] + (float(x),) + d[4:] for d, x in zip(data, new)]
    rows = []
    claude = json.load(open(args.labels, encoding="utf-8"))["labels"] if not args.human else {}
    for b, p, lang, score, verdict, _text in data:
        lab = verdict if args.human else claude.get(f"{b}.{p}")
        if lab in VALUE:
            rows.append((lang, float(score), lab))
    print(("HUMAN labels" if args.human else "CLAUDE labels (not human ground truth)"), "- comments with a usable label:", len(rows))
    out = {}
    for lang in ("english", "hinglish", "devanagari", "all"):
        r = [x for x in rows if lang == "all" or x[0] == lang]
        if len(r) < 8:
            continue
        s = np.array([x[1] for x in r])
        lab = [x[2] for x in r]
        pos, neg = np.array([l == "positive" for l in lab]).astype(int), np.array([l == "negative" for l in lab]).astype(int)
        res = {"n": len(r), "positive": int(pos.sum()), "negative": int(neg.sum()), "neutral": len(r) - int(pos.sum()) - int(neg.sum()),
               "auc_positive_vs_rest": auc(pos, s) if 0 < pos.sum() < len(r) else None, "auc_negative_vs_rest_low_score": auc(neg, -s) if 0 < neg.sum() < len(r) else None,
               "spearman_with_label_value": spearman(list(s), [VALUE[l] for l in lab]),
               "mean_score_by_label": {k: round(float(st.mean(x[1] for x in r if x[2] == k)), 3) for k in VALUE if any(x[2] == k for x in r)}}
        out[lang] = res
        f = lambda v: "n/a" if v is None else f"{v:.2f}"  # noqa: E731
        print(f"{lang:10s} n {res['n']:3d} (pos {res['positive']}, neu {res['neutral']}, neg {res['negative']}) | AUC pos-vs-rest {f(res['auc_positive_vs_rest'])} | AUC neg-vs-rest {f(res['auc_negative_vs_rest_low_score'])} | Spearman {res['spearman_with_label_value']:+.2f} | mean score {res['mean_score_by_label']}")
    Path(ROOT / "models" / (("sentiment_check_human" if args.human else "sentiment_check_claude_labels") + ("_" + args.model.split("/")[-1] if args.model else "") + ".json")).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
