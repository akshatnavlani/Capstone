"""One-off data fix (27 Oct 2026): give the brand to sponsored posts of unlinked creators, and classify brands that had no category. Backs up first; never touches is_sponsored.

    python assign_missing_brands_20261027.py --dry-run     # prints what it would do
    python assign_missing_brands_20261027.py               # applies it (backup tables brand_assign_backup_20261027, brand_category_backup_20261027)

WHY: 10 verified creators had 22 real sponsored posts (paid-partnership label or #ad) with no brand, and 25 brands had no category, so none of them could link creators in the
shared-brand graph. The brand of each post below was read from its own text (an @mention, hashtag or link naming the brand); posts whose text names no brand are left alone.
Two posts that LOOK sponsored but are not (a ketchup video that says "Not a paid promotion", and a video titled "Kohli's Best Paid Promotion") are NOT changed here: flipping a
sponsored label needs Shimona's yes; they are listed in the output.
Undo: set brand_id / category back from the backup tables.
"""
import argparse
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestrator import get_connection  # noqa: E402

# category 'consumer_other' = a real brand outside the fitness categories (supplement, footwear, apparel, equipment, food, wellness).
NEW_BRANDS = {"Vahdam India": "supplement", "Colgate": "consumer_other", "Indira IVF": "wellness", "Horlicks": "food", "Country Delight": "food", "Mahindra": "consumer_other",
              "HMD": "consumer_other", "Himalaya": "consumer_other", "Lakme": "consumer_other", "Samsung": "consumer_other", "Maybelline": "consumer_other", "ITC Aashirvaad": "food"}
EXISTING_NEW_CATEGORY = {"GarnierIndia": "consumer_other", "LiptonTeaIndia": "food", "Airtel": "consumer_other", "Visit Dubai": "consumer_other", "meller": "consumer_other",
                         "johnjacobseyewear": "consumer_other", "stoaparis": "consumer_other", "lorealparisindia": "consumer_other", "reliancejewels": "consumer_other", "Milton": "consumer_other",
                         "BGMI": "consumer_other", "Paytm": "consumer_other", "OSMO": "consumer_other", "duroflexworld": "consumer_other", "Cadbury": "food", "oakleymeta": "consumer_other",
                         "Amazon Prime": "consumer_other", "Agilitas": "apparel",
                         # not brands: a person, an event, a club, own channels, a broken name
                         "PriyapandeyYT": "not_a_brand", "Esports World Cup": "not_a_brand", "Surrey Cricket Club": "not_a_brand", "be": "not_a_brand",
                         "Park Hospital.\n\n\nGaurav's": "not_a_brand", "onechanceshorts": "not_a_brand", "theonechance": "not_a_brand"}
# (platform, content_id) -> brand name, each read from the post's own text
POSTS = {("instagram", "DetvNwqBkgH"): "Vahdam India", ("youtube", "L8vReLs0PsQ"): "Colgate", ("youtube", "DC-FHTsW60o"): "Indira IVF", ("youtube", "qHVwJdEct18"): "LiptonTeaIndia",
         ("youtube", "yYo0eyl5K80"): "Horlicks", ("instagram", "DeouZcuN5_D"): "Mahindra", ("youtube", "LNVnG5XFq7Q"): "HMD", ("youtube", "7OdnYz1UxPg"): "GarnierIndia",
         ("youtube", "aPtwByKBUGo"): "Country Delight", ("youtube", "iNgwGDIyyLg"): "Gayor Essentials", ("youtube", "htUY1tcK0aM"): "Lakme", ("youtube", "mChZ06vPtps"): "Himalaya",
         ("youtube", "6EX1SvZAuxI"): "Himalaya", ("youtube", "ZmOysASxfNk"): "Samsung", ("youtube", "mOPGfUNlv6E"): "Airtel", ("youtube", "TDm3ma0_JlU"): "Maybelline",
         ("youtube", "wlF8vn9ToIw"): "ITC Aashirvaad"}
LOOK_SPONSORED_BUT_NOT = [("youtube", "pcxTYVgflpc", "Sanjay Duseja: says '(Not a paid promotion, just something I personally use and like.)'"),
                          ("youtube", "tUkIMp4SMnE", "Tanmay Bhat: title 'Kohli's Best Paid Promotion', a joke video")]
TABLE = {"youtube": ("youtube_videos", "video_id"), "instagram": ("instagram_posts", "post_id")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("select brand_id::text, name, category from brands")
    brands = {n: (b, c) for b, n, c in cur.fetchall()}
    if not args.dry_run:
        cur.execute("create table if not exists brand_assign_backup_20261027 (platform text, content_id text, old_brand_id uuid, primary key (platform, content_id))")
        cur.execute("create table if not exists brand_category_backup_20261027 (brand_id uuid primary key, name text, old_category text, existed boolean)")
    made = 0
    for name, cat in NEW_BRANDS.items():
        if name not in brands:
            made += 1
            print(f"new brand: {name} ({cat})")
            if not args.dry_run:
                cur.execute("insert into brands (name, category, source) values (%s, %s, 'sponsorship_mention') on conflict (name) do nothing returning brand_id::text", (name, cat))
                row = cur.fetchone()
                cur.execute("insert into brand_category_backup_20261027 values (%s, %s, null, false) on conflict do nothing", (row[0], name)) if row else None
                brands[name] = (row[0] if row else None, cat)
    recat = 0
    for name, cat in EXISTING_NEW_CATEGORY.items():
        b = brands.get(name)
        if b and b[1] is None:
            recat += 1
            print(f"classify: {name!r} -> {cat}")
            if not args.dry_run:
                cur.execute("insert into brand_category_backup_20261027 values (%s::uuid, %s, null, true) on conflict do nothing", (b[0], name))
                cur.execute("update brands set category = %s, updated_at = now() where brand_id = %s::uuid and category is null", (cat, b[0]))
    assigned = 0
    for (platform, cid), name in POSTS.items():
        table, key = TABLE[platform]
        bid = brands.get(name, (None,))[0]
        cur.execute(f"select brand_id::text from {table} where {key} = %s", (cid,))
        row = cur.fetchone()
        if not row or row[0] is not None or bid is None:
            print(f"skip {platform} {cid} ({name}): {'not found' if not row else 'already has a brand' if row[0] else 'brand missing'}")
            continue
        assigned += 1
        print(f"assign: {platform} {cid} -> {name}")
        if not args.dry_run:
            cur.execute("insert into brand_assign_backup_20261027 values (%s, %s, null) on conflict do nothing", (platform, cid))
            cur.execute(f"update {table} set brand_id = %s::uuid where {key} = %s and brand_id is null", (bid, cid))
    if not args.dry_run:
        conn.commit()
    print(f"\n{'DRY RUN: ' if args.dry_run else ''}new brands {made}, brands classified {recat}, posts given a brand {assigned}")
    print("Look sponsored but are not (labels NOT changed; Shimona decides):")
    for p, c, why in LOOK_SPONSORED_BUT_NOT:
        print(f"  {p} {c}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
