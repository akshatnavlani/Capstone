"""Label every still-unlabelled sponsored event as fitness or not, from its brand's type. 6 Nov 2026.

    python scripts/label_events_by_brand_type.py [--dry-run]

THE RULE (Shimona, 6 Nov 2026, set before any re-run): every fitness or health brand is in scope --
supplements, protein, hydration, health foods and drinks, sportswear, shoes, equipment, wellness, yoga and
meditation. Makeup, skincare, lifestyle and other consumer brands are out.

  yes  brand type supplement, footwear, equipment, apparel (all held apparel brands are sportswear), wellness,
       and these health foods: Pintola, Yogabar, Alpino, MyFitness, Mille Supergrain, Horlicks, LiptonTeaIndia
  no   other food (Cadbury, ITC Aashirvaad, Country Delight), consumer_other, not_a_brand

Hand labels already in data/event_brand_labels.csv are never changed. A (creator, brand) pair that a hand
label marks as the creator's OWN brand stays "no" for that creator's other events of the same brand
(self-promotion is not sponsorship). Events with no brand identified are left unlabelled, so the training
rule excludes them, as before.

Appends rows to data/event_brand_labels.csv. Reads the database, writes nothing to it.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from orchestrator import load_env  # noqa: E402

LABELS = ROOT / "data" / "event_brand_labels.csv"
YES_TYPES = {"supplement", "footwear", "equipment", "apparel", "wellness"}
HEALTH_FOODS = {"Pintola", "Yogabar", "Alpino", "MyFitness", "Mille Supergrain", "Horlicks", "LiptonTeaIndia"}
# hand-label brand spelling -> database brand name, where they differ
BRAND_ALIASES = {"2X Nutrition": "2XN", "2X Nutrition RealGainz": "2XN"}
NOTE = "auto from brand type '{}' (user rule 2026-11-06: every fitness or health brand = yes; makeup, skincare, lifestyle, other consumer = no)"

# Same event definition as pair_count.py clause 1 and train_prod_model.load_sponsorship_dates.
EVENTS = """
select p.post_id::text, 'instagram', c.name, p.posted_at::date, b.name, b.category
  from instagram_posts p join creators c using (creator_id) join brands b on b.brand_id = p.brand_id
 where (p.is_sponsored or p.has_paid_partnership_label) and p.posted_at is not null
union all
select v.video_id::text, 'youtube', c.name, v.published_at::date, b.name, b.category
  from youtube_videos v join creators c using (creator_id) join brands b on b.brand_id = v.brand_id
 where v.is_sponsored and v.published_at is not null
union all
select r.post_id::text, 'reddit', c.name, r.posted_at::date, b.name, b.category
  from reddit_posts r join creators c using (creator_id) join brands b on b.brand_id = r.brand_id
 where r.is_sponsored and r.posted_at is not null
"""


def verdict(brand: str, category: str) -> str:
    if category in YES_TYPES or brand in HEALTH_FOODS:
        return "yes"
    return "no"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    with open(LABELS, encoding="utf-8") as f:
        hand = list(csv.DictReader(f))
    labelled = {r["content_id"] for r in hand}
    own = {(r["creator"], BRAND_ALIASES.get(r["brand"], r["brand"])) for r in hand if "own brand" in r.get("note", "").lower()}

    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    cur.execute(EVENTS)
    new, counts = [], {}
    for cid, platform, creator, day, brand, category in cur.fetchall():
        if cid in labelled:
            continue
        if any(creator == c and (brand == b or brand.lower() in b.lower() or b.lower() in brand.lower()) for c, b in own):
            fit, note = "no", "own brand: self-promotion, not sponsorship (same creator and brand as a hand label)"
        else:
            fit, note = verdict(brand, category), NOTE.format(category)
        labelled.add(cid)
        new.append({"content_id": cid, "platform": platform, "creator": creator, "posted_at": day.isoformat(),
                    "brand": brand, "fitness": fit, "note": note})
        counts[(category, fit)] = counts.get((category, fit), 0) + 1

    for (category, fit), n in sorted(counts.items()):
        print(f"  {category:15s} {fit:3s} {n}")
    print(f"{len(hand)} hand labels kept; {len(new)} new labels "
          f"({sum(r['fitness'] == 'yes' for r in new)} yes, {sum(r['fitness'] == 'no' for r in new)} no)")
    if args.dry_run:
        print("[dry run] file not changed")
        return
    with open(LABELS, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(hand[0]), lineterminator="\n")  # the file uses LF
        w.writerows(new)
    print(f"appended to {LABELS}")


if __name__ == "__main__":
    main()
