"""Direct effect of sponsorship on a creator's OWN audience (ml/direct_effect.py).

    $env:PYTHONPATH="."; python scripts/direct_effect.py

Read-only on the database. Writes models/direct_effect_creators.csv (one row
per creator, with a shrunk score and 95% interval) and models/direct_effect.json.

Knobs: GAIL_DIRECT_EVENTS=fitness (default; same brand rule as training) or all;
GAIL_FITNESS_CATEGORIES (default supplement,footwear,apparel,equipment,wellness);
GAIL_DIRECT_WINDOW (baseline half-width in days, default 30).
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.direct_effect import Post, effects_by_creator, overall, placebo_targets, settled, shrink  # noqa: E402

EVENTS = os.environ.get("GAIL_DIRECT_EVENTS", "fitness")
FITNESS_CATS = set(os.environ.get("GAIL_FITNESS_CATEGORIES",
                                  "supplement,footwear,apparel,equipment,wellness").split(","))
WINDOW = int(os.environ.get("GAIL_DIRECT_WINDOW", "30"))
FITNESS_CREATOR_CATEGORIES = {"athlete", "team", "league", "fitness_influencer"}  # as in train_prod_model.py

QUERIES = {
    "youtube": "select creator_id::text, video_id::text, published_at, view_count, like_count, "
               "coalesce(is_sponsored, false), "
               "case when duration_seconds is null then 'unknown' "
               "when duration_seconds <= 180 then 'short' else 'long' end from youtube_videos where creator_id is not null "
               "and published_at is not null and view_count is not null and like_count is not null",
    "instagram": "select creator_id::text, post_id::text, posted_at, like_count, comment_count, "
                 "coalesce(is_sponsored, false) or coalesce(has_paid_partnership_label, false), "
                 "coalesce(media_type, 'unknown') from instagram_posts where creator_id is not null and posted_at is not null "
                 "and like_count is not null and comment_count is not null",
}


def database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("DATABASE_URL not set and not found in .env")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    cur = psycopg2.connect(database_url()).cursor()
    today = date.today()

    posts: list[Post] = []
    for platform, sql in QUERIES.items():
        cur.execute(sql)
        for cid, pid, d, e1, e2, sp, fmt in cur.fetchall():
            day = d.date() if isinstance(d, datetime) else d
            posts.append(Post(cid, platform, pid, day, float(e1) + float(e2), bool(sp), fmt))
    posts = settled(posts, today)

    cur.execute("select creator_id::text, name, category from creators")
    creators = {cid: (name, cat) for cid, name, cat in cur.fetchall()}
    overrides = {r["name"].strip().lower(): r["include"].strip().lower() in ("yes", "true", "1")
                 for r in read_csv(ROOT / "data" / "creator_scope_overrides.csv") if r.get("name")}

    def in_scope(cid: str) -> bool:
        name, cat = creators.get(cid, ("", "other"))
        key = (name or "").strip().lower()
        return overrides[key] if key in overrides else cat in FITNESS_CREATOR_CATEGORIES

    cur.execute("select e.content_id::text, b.name, b.category from creator_sponsorship_events e "
                "left join brands b on b.brand_id = e.brand_id")
    db_brand = {cid: (name, cat) for cid, name, cat in cur.fetchall()}
    labels = {r["content_id"]: r for r in read_csv(ROOT / "data" / "event_brand_labels.csv")}

    def fitness_event(p: Post) -> str:
        """'yes' / 'no' / 'unclassified'. Hand labels win; else the brand's DB category."""
        lab = labels.get(p.post_id)
        if lab:
            return "yes" if lab["fitness"].strip().lower() == "yes" else "no"
        name, cat = db_brand.get(p.post_id, (None, None))
        if cat is None:
            return "unclassified"
        return "yes" if cat in FITNESS_CATS else "no"

    posts = [p for p in posts if in_scope(p.creator)]
    sponsored = [p for p in posts if p.sponsored]
    verdict = {p.post_id: fitness_event(p) for p in sponsored}
    counts = {v: sum(1 for x in verdict.values() if x == v) for v in ("yes", "no", "unclassified")}
    targets = sponsored if EVENTS == "all" else [p for p in sponsored if verdict[p.post_id] == "yes"]

    print(f"=== Direct effect: own audience's response to sponsored posts (window +-{WINDOW}d) ===")
    print(f"Posts (in scope, older than 14 days): {len(posts)}; sponsored: {len(sponsored)} "
          f"(fitness brand {counts['yes']}, other brand {counts['no']}, brand unknown {counts['unclassified']})")
    print(f"Event rule: {EVENTS} -> {len(targets)} sponsored posts considered")
    # Format mix: if sponsored and ordinary posts differ here, an unmatched
    # comparison would measure the format, not the sponsorship.
    for platform in QUERIES:
        def mix(ps):
            n = len(ps) or 1
            fm = {}
            for p in ps:
                fm[p.fmt] = fm.get(p.fmt, 0) + 1
            return ", ".join(f"{k} {100 * v / n:.0f}%" for k, v in sorted(fm.items()))
        sp_p = [p for p in targets if p.platform == platform]
        od_p = [p for p in posts if p.platform == platform and not p.sponsored]
        if sp_p:
            print(f"  {platform} format mix -- sponsored: {mix(sp_p)} | ordinary: {mix(od_p)}")

    eff = effects_by_creator(targets, posts, WINDOW)
    main_res = overall(eff)
    print(f"\nWith a baseline (>=3 same-format ordinary posts within +-{WINDOW}d): {main_res['n_posts']} posts "
          f"from {main_res['n_creators']} creators")
    print(f"Mean effect (log ratio vs own ordinary posts): {main_res['mean']:+.3f}  "
          f"95% CI [{main_res['lo']:+.3f}, {main_res['hi']:+.3f}]  (creator bootstrap)")
    print(f"  median {main_res['median']:+.3f}; sponsored post beat the creator's baseline in "
          f"{100 * main_res['share_positive']:.0f}% of cases")

    pl = overall(effects_by_creator(placebo_targets(posts, {c: len(v) for c, v in eff.items()}), posts, WINDOW))
    print(f"Placebo (random ORDINARY posts, same creators): {pl['mean']:+.3f}  "
          f"95% CI [{pl['lo']:+.3f}, {pl['hi']:+.3f}] -- should be ~0")
    # A single post's log engagement against its neighbours' median is not exactly
    # unbiased when engagement is skewed; the placebo measures that bias, so the
    # difference is the estimate to quote.
    adj = main_res["mean"] - pl["mean"]
    print(f"Placebo-adjusted effect (quote this one): {adj:+.3f}  "
          f"(approx. 95% CI [{main_res['lo'] - pl['mean']:+.3f}, {main_res['hi'] - pl['mean']:+.3f}])")

    for platform in QUERIES:
        sub = effects_by_creator([p for p in targets if p.platform == platform], posts, WINDOW)
        r = overall(sub)
        if r["n_posts"]:
            print(f"  {platform:9s} {r['mean']:+.3f}  [{r['lo']:+.3f}, {r['hi']:+.3f}]  "
                  f"({r['n_posts']} posts, {r['n_creators']} creators)")
    if EVENTS != "all":
        alt = overall(effects_by_creator(sponsored, posts, WINDOW))
        print(f"Sensitivity, ALL brands: {alt['mean']:+.3f}  [{alt['lo']:+.3f}, {alt['hi']:+.3f}]  "
              f"({alt['n_posts']} posts)")

    scores = shrink(eff)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1]["score"])
    pos = sum(1 for _, s in ranked if s["lo"] > 0)
    neg = sum(1 for _, s in ranked if s["hi"] < 0)
    print(f"\nPer creator (shrunk toward the mean; interval excludes 0: {pos} above, {neg} below, "
          f"{len(ranked) - pos - neg} unclear)")
    print(f"  {'creator':34s} {'n':>3s} {'raw':>7s} {'score':>7s}   95% interval")
    show = ranked[:15] + [None] + ranked[-10:] if len(ranked) > 25 else ranked
    for row in show:
        if row is None:
            print("  ...")
            continue
        cid, s = row
        name = creators.get(cid, (cid, ""))[0] or cid
        print(f"  {name[:34]:34s} {s['n']:3d} {s['raw']:+7.3f} {s['score']:+7.3f}   [{s['lo']:+.3f}, {s['hi']:+.3f}]")

    models = ROOT / "models"
    models.mkdir(exist_ok=True)
    with open(models / "direct_effect_creators.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["creator_id", "name", "category", "n_sponsored_posts", "raw_mean", "score", "lo", "hi"])
        for cid, s in ranked:
            name, cat = creators.get(cid, ("", ""))
            w.writerow([cid, name, cat, s["n"], f"{s['raw']:.4f}", f"{s['score']:.4f}", f"{s['lo']:.4f}", f"{s['hi']:.4f}"])
    (models / "direct_effect.json").write_text(json.dumps({
        "window_days": WINDOW, "event_rule": EVENTS, "fitness_categories": sorted(FITNESS_CATS),
        "overall": main_res, "placebo": pl, "placebo_adjusted": adj, "event_counts": counts,
        "creators": {cid: s for cid, s in ranked}}, indent=2, default=str))
    print(f"\nSaved {models / 'direct_effect_creators.csv'} and {models / 'direct_effect.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
