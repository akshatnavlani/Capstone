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
from ml.creator_links import collaboration_pairs, india_links  # noqa: E402
from ml.direct_effect import (Post, effects_by_creator, overall, placebo_targets, prior, settled, shrink,  # noqa: E402
                              typical_log_engagement)

EVENTS = os.environ.get("GAIL_DIRECT_EVENTS", "fitness")
FITNESS_CATS = set(os.environ.get("GAIL_FITNESS_CATEGORIES",
                                  "supplement,footwear,apparel,equipment,wellness").split(","))
WINDOW = int(os.environ.get("GAIL_DIRECT_WINDOW", "30"))
RECENT_DAYS = int(os.environ.get("GAIL_RECENT_DAYS", "90"))  # window for "typical engagement now"
DEFAULT_FMT = {"youtube": "long", "instagram": "video"}
# Ranking adjustment for a sponsored post, on the log scale (Track A, 6 Nov 2026):
# out of time, sponsored fitness posts landed 0.34 below the creator's recent
# normal while ordinary posts landed 0.11 below (general drift), so the
# sponsorship itself costs about 0.23 (~20%). Per-creator direct-effect scores did
# not improve those predictions, so the ranking uses this one population value
# and the creator's own score is shown as context only.
SPONSORED_ADJ = float(os.environ.get("GAIL_SPONSORED_ADJ", "-0.23"))
FITNESS_CREATOR_CATEGORIES = {"athlete", "team", "league", "fitness_influencer"}  # as in train_prod_model.py
PEOPLE_CATEGORIES = {"athlete", "fitness_influencer", "lifestyle_influencer"}

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
    # include: yes / no / overseas. 'overseas' = not Indian: left out of every
    # estimate, and kept in the RANKING only with an Indian-market link (below).
    overrides = {r["name"].strip().lower(): r["include"].strip().lower()
                 for r in read_csv(ROOT / "data" / "creator_scope_overrides.csv") if r.get("name")}

    def override_of(cid: str) -> str | None:
        return overrides.get((creators.get(cid, ("", ""))[0] or "").strip().lower())

    def in_scope(cid: str) -> bool:
        ov = override_of(cid)
        if ov is not None:
            return ov in ("yes", "true", "1")
        return creators.get(cid, ("", "other"))[1] in FITNESS_CREATOR_CATEGORIES

    overseas = {c for c in creators if override_of(c) == "overseas"}
    eligible = {c for c in overseas if creators[c][1] in FITNESS_CREATOR_CATEGORIES}
    # Only collaborations with Indian PEOPLE count (user, 28 Oct): not team,
    # league or organisation accounts, and not brand deals.
    indian_people = {c for c, (_, cat) in creators.items() if c not in overseas and cat in PEOPLE_CATEGORIES}
    overseas_kept = india_links(eligible, indian_people, collaboration_pairs(cur),
                                {c: n for c, (n, _) in creators.items()})

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

    posts_rank = [p for p in posts if in_scope(p.creator) or p.creator in overseas_kept]
    posts = [p for p in posts_rank if p.creator not in overseas_kept]   # Indian creators: every estimate
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
    print(f"Mean effect (log engagement vs own ordinary posts' mean log): {main_res['mean']:+.3f}  "
          f"95% CI [{main_res['lo']:+.3f}, {main_res['hi']:+.3f}]  (creator bootstrap)")
    print(f"  median {main_res['median']:+.3f}; sponsored post beat the creator's baseline in "
          f"{100 * main_res['share_positive']:.0f}% of cases")

    pl = overall(effects_by_creator(placebo_targets(posts, {c: len(v) for c, v in eff.items()}), posts, WINDOW))
    print(f"Placebo (random ORDINARY posts, same creators): {pl['mean']:+.3f}  "
          f"95% CI [{pl['lo']:+.3f}, {pl['hi']:+.3f}] -- should be ~0")
    # With the mean-of-log baseline the placebo should be ~0; any remainder is a
    # bias of the comparison itself, so the difference is the estimate to quote.
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

    # Ranking scores also cover overseas creators with an Indian-market link;
    # the estimates printed above stay Indian-only.
    sponsored_rank = [p for p in posts_rank if p.sponsored]
    targets_rank = sponsored_rank if EVENTS == "all" else [p for p in sponsored_rank if fitness_event(p) == "yes"]
    eff_rank = effects_by_creator(targets_rank, posts_rank, WINDOW)
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
    print(f"\nOverseas accounts: {len(overseas)} marked; {len(overseas_kept)} kept for the ranking "
          f"(collaborate with an Indian creator/athlete/celebrity), {len(eligible) - len(overseas_kept)} dropped")
    for c, why in sorted(overseas_kept.items(), key=lambda kv: creators[kv[0]][0] or ""):
        print(f"  kept {creators[c][0][:30]:30s} {why[:110]}")
    followers = {}
    cur.execute("select creator_id::text, subscriber_count from youtube_channels where subscriber_count is not null")
    followers.update({(c, "youtube"): float(n) for c, n in cur.fetchall()})
    cur.execute("select creator_id::text, follower_count from instagram_profiles where follower_count is not null")
    followers.update({(c, "instagram"): float(n) for c, n in cur.fetchall()})
    write_creator_value(posts_rank, sponsored_rank, shrink(eff_rank), prior(eff_rank), creators, today, models,
                        overseas_kept, followers)
    return 0


def write_creator_value(posts, sponsored, scores, prior_score, creators, today, models, overseas_kept=None,
                        followers=None) -> None:
    """Per creator and platform: expected engagement of ONE sponsored post now.

    expected = exp(typical recent log engagement + direct-effect score) - 1, where
    typical = mean log engagement of the creator's ordinary posts in the last
    RECENT_DAYS (in the format they usually sponsor in). Creators never measured
    on a sponsored post get the population prior, marked basis='prior'.
    Engagement units differ by platform (YouTube views+likes, Instagram
    likes+comments): compare within a platform only.
    """
    import math
    from collections import Counter
    from datetime import timedelta
    from ml.cost_estimate import estimate, load_rate_card
    card = load_rate_card(ROOT / "data" / "cost_rate_card.csv")
    start = today - timedelta(days=14 + RECENT_DAYS)
    by_cp: dict[tuple[str, str], list] = {}
    for p in posts:
        if p.day >= start:
            by_cp.setdefault((p.creator, p.platform), []).append(p)
    sp_fmt: dict[tuple[str, str], Counter] = {}
    for p in sponsored:
        sp_fmt.setdefault((p.creator, p.platform), Counter())[p.fmt] += 1
    rows = []
    for (c, k), recent in by_cp.items():
        pref = sp_fmt[(c, k)].most_common(1)[0][0] if (c, k) in sp_fmt else DEFAULT_FMT.get(k, "any")
        t = typical_log_engagement(recent, pref)
        if t is None:
            continue
        log_typ, n_recent, fmt_used = t
        s = scores.get(c)
        basis = "measured" if s else "prior"
        s = s or prior_score
        rows.append({
            "creator_id": c, "name": creators.get(c, ("", ""))[0], "category": creators.get(c, ("", ""))[1],
            "platform": k, "format": fmt_used, "recent_ordinary_posts": n_recent,
            "typical_engagement": math.exp(log_typ) - 1,
            "direct_score": s["score"], "direct_lo": s["lo"], "direct_hi": s["hi"],
            "direct_basis": basis, "n_sponsored_posts": s["n"],
            "expected_sponsored_engagement": math.exp(log_typ + s["score"]) - 1,
            "expected_lo": math.exp(log_typ + s["lo"]) - 1, "expected_hi": math.exp(log_typ + s["hi"]) - 1,
            "overseas": "yes" if c in (overseas_kept or {}) else "no",
            "india_link": (overseas_kept or {}).get(c, ""),
        })
        # Ranking inputs (Track A): normal engagement x one population sponsored
        # adjustment, divided by an ESTIMATED cost from the rate card.
        fol = (followers or {}).get((c, k))
        cost = estimate(card, k, fmt_used, fol)
        rank_eng = math.exp(log_typ + SPONSORED_ADJ) - 1
        rows[-1].update({
            "followers": int(fol) if fol else "",
            "ranking_expected_engagement": rank_eng,
            "cost_tier": cost["tier"] if cost else "",
            "cost_low_inr": cost["low"] if cost else "", "cost_mid_inr": cost["mid"] if cost else "",
            "cost_high_inr": cost["high"] if cost else "",
            "engagement_per_1000_inr": 1000 * rank_eng / cost["mid"] if cost else "",
            "engagement_per_1000_inr_lo": 1000 * rank_eng / cost["high"] if cost else "",
            "engagement_per_1000_inr_hi": 1000 * rank_eng / cost["low"] if cost else "",
        })
    rows.sort(key=lambda r: (r["platform"], -r["expected_sponsored_engagement"]))
    path = models / "creator_value.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["creator_id"])
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})
    print(f"\n=== Expected engagement of one sponsored post now (option A ranking input) ===")
    print(f"{len(rows)} creator-platform rows ({sum(r['direct_basis'] == 'measured' for r in rows)} measured, "
          f"{sum(r['direct_basis'] == 'prior' for r in rows)} on the population prior); last {RECENT_DAYS} days")
    for k in ("youtube", "instagram"):
        top = [r for r in rows if r["platform"] == k][:10]
        if not top:
            continue
        unit = "views+likes" if k == "youtube" else "likes+comments"
        print(f"  {k} top 10 ({unit} per sponsored post, 95% interval):")
        for r in top:
            print(f"    {r['name'][:30]:30s} {r['expected_sponsored_engagement']:>12,.0f}  "
                  f"[{r['expected_lo']:,.0f} - {r['expected_hi']:,.0f}]  "
                  f"typical {r['typical_engagement']:,.0f}, score {r['direct_score']:+.2f} ({r['direct_basis']})")
    costed = [r for r in rows if r["engagement_per_1000_inr"] != ""]
    print(f"Cost estimates (rate card, ESTIMATED): {len(costed)}/{len(rows)} rows; ranking uses normal engagement "
          f"x exp({SPONSORED_ADJ:+.2f}) per estimated rupee")
    for k in ("youtube", "instagram"):
        top = sorted((r for r in costed if r["platform"] == k), key=lambda r: -r["engagement_per_1000_inr"])[:5]
        for r in top:
            print(f"    {k:9s} {r['name'][:28]:28s} {r['engagement_per_1000_inr']:>9,.0f} per Rs 1,000  "
                  f"[{r['engagement_per_1000_inr_lo']:,.0f} - {r['engagement_per_1000_inr_hi']:,.0f}]  "
                  f"({r['cost_tier']}, est. Rs {r['cost_mid_inr']:,.0f})")
    print(f"Saved {path}")


if __name__ == "__main__":
    raise SystemExit(main())
