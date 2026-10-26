"""Give every detected sponsorship event a probability of being a real ad, and measure how good that probability is on creators the model never saw.

    python scripts/score_sponsorship_events.py            # report only (reads the database, writes models/sponsorship_quality.json)
    python scripts/score_sponsorship_events.py --write    # also writes sponsorship_event_scores (needs migration 20261026010000)

Labels = what Shimona checked one by one: sponsorship_review rows with reviewer exactly 'Shimona' (sponsored = 1; not_sponsored and footer_only = 0; unsure skipped) and her spoken_scan hits (yes = 1, no = 0).
Left out of every human number: rows marked 'assumed' or 'not checked one by one', the 45 spoken_scan 'yes' rows approved without checking on 24 Oct, and all Claude readings (reported separately). Method and features: ml/sponsorship_quality.py. Nothing here changes
is_sponsored or any training data; GAIL's inputs stay as they are until the probabilities are explicitly adopted.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psycopg2
from dotenv import dotenv_values
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ml import sponsorship_quality as sq  # noqa: E402

MODEL_VERSION = "tier-precision-human-only-2026-10-27"
TEXT_SQL = {
    "youtube": "select video_id, creator_id::text, coalesce(title,''), coalesce(description,'') from youtube_videos where video_id = any(%s)",
    "instagram": "select post_id, creator_id::text, '', coalesce(caption,'') from instagram_posts where post_id = any(%s)",
    "reddit": "select post_id, creator_id::text, coalesce(title,''), coalesce(body,'') from reddit_posts where post_id = any(%s)",
}
UNCHECKED_YES_DATE = "2026-10-24"
PRIOR_CHECKS = 5


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (c - h) / d, (c + h) / d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--pairs", help="training_pair_deltas.json: restrict the hand-check sample to events the spillover rows use")
    ap.add_argument("--n-label", type=int, default=100)
    ap.add_argument("--out", default=str(ROOT / "models" / "sponsorship_quality.json"))
    args = ap.parse_args()
    url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env")["DATABASE_URL"]
    conn = psycopg2.connect(url)
    cur = conn.cursor()

    cur.execute("select platform, content_id, sponsorship_evidence, coalesce(jsonb_array_length(sponsorship_raw_matches), 0) from creator_sponsorship_events")
    events = {(p, c): (t or "none", int(n)) for p, c, t, n in cur.fetchall()}

    labels = {}                                                        # (platform, content_id) -> 0/1
    # Human = rows Shimona checked ONE BY ONE (reviewer exactly 'Shimona'). Rows she marked "assumed" / "not checked one by one" copy the rule's own answer, and
    # rows by Claude (earlier draft and 26 Oct pre-labels, text only) are not human checks: both are kept out of every human number and reported on their own.
    cur.execute("select platform, content_id, verdict from sponsorship_review where verdict is not null and reviewer = 'Shimona'")
    for p, c, v in cur.fetchall():
        if v in ("sponsored", "not_sponsored", "footer_only"):
            labels[(p, c)] = int(v == "sponsored")
    cur.execute("select video_id, verdict from spoken_scan where verdict in ('yes','no') and reviewer = 'Shimona' and not (verdict = 'yes' and reviewed_at::date = %s)", (UNCHECKED_YES_DATE,))
    for c, v in cur.fetchall():
        labels.setdefault(("youtube", c), int(v == "yes"))              # a row already in sponsorship_review keeps its own verdict

    wanted = defaultdict(set)
    for p, c in list(labels) + list(events):
        wanted[p].add(c)
    text = {}
    for p, ids in wanted.items():
        cur.execute(TEXT_SQL[p], (sorted(ids),))
        for c, creator, title, body in cur.fetchall():
            text[(p, c)] = (creator, title, body)

    def row_for(key):
        creator, title, body = text[key]
        tier, n = events.get(key, ("none", 0))
        return {"tier": tier, "n_evidence": n, "platform": key[0], "title": title, "body": body}, creator

    keys = [k for k in labels if k in text and text[k][0]]
    rows, groups = zip(*(row_for(k) for k in keys))
    rows, groups, y = list(rows), list(groups), np.array([labels[k] for k in keys])
    is_event = np.array([k in events for k in keys])
    print(f"checked rows used: {len(y)} ({int(y.sum())} real ads, {int((1 - y).sum())} not ads) from {len(set(groups))} creators; {int(is_event.sum())} of them are detected events")

    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model_version": MODEL_VERSION,
           "labelled_rows": int(len(y)), "real_ads": int(y.sum()), "not_ads": int((1 - y).sum()), "creators": len(set(groups)), "detected_events_among_labelled": int(is_event.sum())}

    by_tier = defaultdict(lambda: [0, 0])
    for r, lab, ev in zip(rows, y, is_event):
        if ev:
            by_tier[r["tier"]][0] += int(lab)
            by_tier[r["tier"]][1] += 1
    out["human_checked_precision_by_tier"] = {t: {"real_ads": a, "checked": n, "precision": round(a / n, 3)} for t, (a, n) in sorted(by_tier.items())}
    print("precision of the detector on events Shimona checked one by one, by tier:")
    for t, v in out["human_checked_precision_by_tier"].items():
        print(f"  {t:16s} {v['real_ads']:3d} of {v['checked']:3d} = {v['precision']:.2f}")

    cur.execute("select platform, content_id, verdict, reviewer from sponsorship_review where reviewer ilike 'claude%' and verdict in ('sponsored','not_sponsored','footer_only')")
    claude = [(events[(p_, c_)][0], int(v == "sponsored")) for p_, c_, v, _ in cur.fetchall() if (p_, c_) in events]
    if claude:
        ck, cn = sum(a for _, a in claude), len(claude)
        clo, chi = wilson(ck, cn)
        out["claude_text_only_readings"] = {"decided_flagged_events": cn, "look_sponsored": ck, "share": round(ck / cn, 3), "wilson95": [round(clo, 3), round(chi, 3)],
                                            "note": "Two Claude passes (15 Oct draft, 26 Oct pre-labels) reading only the description or caption, NOT human checks. Text alone cannot hear a spoken sponsorship or see the video, so this is a lower bound on how many are real ads; the one-by-one human checks above are the reference."}
        print(f"Claude's text-only readings (NOT human): {ck} of {cn} decided flagged events look sponsored from the text alone = {ck / cn:.2f} (95% interval {clo:.2f} to {chi:.2f})")
    cur.execute("select count(*) from sponsorship_review where reviewer ilike 'shimona%' and reviewer <> 'Shimona'")
    out["rows_marked_assumed_or_not_checked_one_by_one"] = cur.fetchone()[0]

    results = {}
    for name, kw in (("text_and_tier", {}), ("tier_only", {"tier_only": True})):
        results[name] = sq.cross_validate(rows, y, groups, k=5, repeats=10, **kw)
        print(f"grouped 5-fold x10, {name:14s}: AUC {results[name]['auc']:.3f} +/- {results[name]['auc_sd']:.3f}  precision {results[name]['precision']:.3f}  recall {results[name]['recall']:.3f}  accuracy {results[name]['accuracy']:.3f}")
    out["grouped_cv_all_checked_rows"] = results
    # the detector as it stands: everything flagged = "ad"; accuracy on checked rows that were flagged or not
    flagged = is_event
    base = sq.binary_metrics(y, flagged.astype(float))
    out["detector_as_is"] = {k: round(v, 3) if isinstance(v, float) else v for k, v in base.items()}
    print(f"detector as-is on the same rows (event = ad): precision {base['precision']:.3f} recall {base['recall']:.3f} (recall is flattered: the checked unflagged rows are a promo-word sample, not all unflagged posts)")

    # events only: how well does the model separate real ads from non-ads among rows the detector flagged?
    ev_idx = np.where(is_event)[0]
    ev_rows, ev_y, ev_groups = [rows[i] for i in ev_idx], y[ev_idx], [groups[i] for i in ev_idx]
    if len(set(ev_y)) == 2:
        out["grouped_cv_flagged_events_only"] = {}
        for name, kw in (("text_and_tier", {}), ("tier_only", {"tier_only": True})):
            r = sq.cross_validate(ev_rows, ev_y, ev_groups, k=5, repeats=10, **kw)
            out["grouped_cv_flagged_events_only"][name] = r
            print(f"flagged events only (n={len(ev_y)}, {int(ev_y.sum())} real), {name:14s}: AUC {r['auc']:.3f} +/- {r['auc_sd']:.3f}  precision {r['precision']:.3f}  recall {r['recall']:.3f}")

    # The text model did not beat the tier baseline on creators it never saw, so events are scored by tier: the human-checked precision of the tier,
    # pulled toward the pooled precision (K pseudo-checks) so a tier with one or two checks is not trusted on its own.
    pooled = float(ev_y.mean())
    tier_p = {t: (v["real_ads"] + PRIOR_CHECKS * pooled) / (v["checked"] + PRIOR_CHECKS) for t, v in out["human_checked_precision_by_tier"].items()}
    ev_keys = [k for k in events if k in text]
    tiers = np.array([events[k][0] for k in ev_keys])
    p = np.array([tier_p.get(t, pooled) for t in tiers])
    lo, hi = wilson(int(ev_y.sum()), len(ev_y))
    out["scoring_rule"] = f"tier precision from human checks, shrunk toward pooled {pooled:.3f} with {PRIOR_CHECKS} pseudo-checks"
    out["pooled_precision_checked_flagged_events"] = {"real_ads": int(ev_y.sum()), "checked": int(len(ev_y)), "precision": round(pooled, 3), "wilson95": [round(lo, 3), round(hi, 3)]}
    out["tier_scores"] = {t: round(v, 3) for t, v in tier_p.items()}
    out["scored_events"] = int(len(ev_keys))
    print(f"flagged events Shimona checked one by one: {int(ev_y.sum())} of {len(ev_y)} real = {pooled:.3f} (95% interval {lo:.2f} to {hi:.2f})")
    print("score per tier:", out["tier_scores"], "| events scored:", len(ev_keys))

    # which unchecked weak-tier events to hand-check: the ones spillover actually rests on, a seeded random pick (a random sample also gives an unbiased precision)
    pair_events = set()
    if args.pairs:
        pair_events = {r["event_item_id"] for r in json.load(open(args.pairs, encoding="utf-8")) if r.get("relation") == "shared_brand"}
    pool = [k for k in ev_keys if k not in labels and events[k][0] in ("brand_and_code", "brand_mention", "creator_comment") and (not pair_events or k[1] in pair_events)]
    rng = np.random.default_rng(7)
    pick = [pool[i] for i in rng.permutation(len(pool))[:args.n_label]]
    out["suggested_to_label"] = [{"platform": k[0], "content_id": k[1], "tier": events[k][0]} for k in pick]
    out["unchecked_weak_tier_events_in_spillover_pairs"] = len(pool)
    print(f"unchecked weak-tier events in the spillover pairs: {len(pool)}; suggested hand-check sample: {len(pick)}")

    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)

    if args.write:
        now = datetime.now(timezone.utc)
        execute_values(cur, "insert into sponsorship_event_scores (content_id, platform, p_ad, model_version, scored_at) values %s "
                            "on conflict (content_id, platform) do update set p_ad = excluded.p_ad, model_version = excluded.model_version, scored_at = excluded.scored_at",
                       [(k[1], k[0], float(pi), MODEL_VERSION, now) for k, pi in zip(ev_keys, p)])
        conn.commit()
        print("wrote", len(ev_keys), "rows to sponsorship_event_scores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
