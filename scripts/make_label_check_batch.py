"""Put the events that models/sponsorship_quality.json suggests for hand-checking into sponsorship_review (next batch) and write a short sheet to read.

    python scripts/make_label_check_batch.py [--sheet scripts/label_check_sheet.md]

A person answers sponsored / not_sponsored / footer_only / unsure per row; the verdicts go into sponsorship_review.verdict, and
scripts/score_sponsorship_events.py then re-measures the detector's precision with them. Re-running does not add rows twice (unique platform + content_id).
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import psycopg2
from dotenv import dotenv_values
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
LINK = {"youtube": "https://www.youtube.com/watch?v={}", "instagram": "https://www.instagram.com/p/{}/"}
TEXT = {"youtube": "select e.creator_id, c.name, y.title, y.description, e.sponsorship_raw_matches from creator_sponsorship_events e join youtube_videos y on y.video_id = e.content_id left join creators c on c.creator_id = e.creator_id where e.platform = 'youtube' and e.content_id = %s",
        "instagram": "select e.creator_id, c.name, '', i.caption, e.sponsorship_raw_matches from creator_sponsorship_events e join instagram_posts i on i.post_id = e.content_id left join creators c on c.creator_id = e.creator_id where e.platform = 'instagram' and e.content_id = %s"}
_KEY = re.compile(r"(code|coupon|promo|discount|use my|sponsor|paid|partner|collab|#ad\b)", re.I)


def snippet(body: str, width: int = 260) -> str:
    body = re.sub(r"\s+", " ", body or "").strip()
    m = _KEY.search(body)
    start = max((m.start() if m else 0) - width // 3, 0)
    return ("..." if start else "") + body[start:start + width]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", default=str(ROOT / "scripts" / "label_check_sheet.md"))
    args = ap.parse_args()
    url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env")["DATABASE_URL"]
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    picks = [p for p in json.loads((ROOT / "models" / "sponsorship_quality.json").read_text(encoding="utf-8"))["suggested_to_label"] if p["platform"] in LINK]
    cur.execute("select coalesce(max(batch), 0) + 1 from sponsorship_review")
    batch = cur.fetchone()[0]
    lines = [f"# Hand-check sheet, batch {batch}", "",
             "For each row open the link and decide: **y** = the post itself promotes a brand (paid / sponsored / affiliate promotion made for that post), "
             "**n** = not an ad, **f** = a vlog or other post that only carries a discount code in its description, **?** = cannot tell.", "",
             "Reply like `1 y, 2 n, 3 f, 4 ?` (any subset is fine; unanswered rows stay unchecked).", ""]
    position = 0
    for p in picks:
        cur.execute(TEXT[p["platform"]], (p["content_id"],))
        row = cur.fetchone()
        if not row:
            continue
        creator_id, name, title, body, matches = row
        position += 1
        cur.execute("insert into sponsorship_review (batch, position, sample_kind, platform, content_id, creator_id, creator_name, title, snippet, evidence, detected_sponsored, link) "
                    "values (%s,%s,'flagged',%s,%s,%s,%s,%s,%s,%s,true,%s) on conflict (platform, content_id) do nothing",
                    (batch, position, p["platform"], p["content_id"], creator_id, name, title, snippet(body), Json(matches), LINK[p["platform"]].format(p["content_id"])))
        lines += [f"**{position}.** {name} ({p['platform']}, tier {p['tier']})", f"   {title}" if title else "", f"   > {snippet(body)}", f"   {LINK[p['platform']].format(p['content_id'])}", ""]
    conn.commit()
    Path(args.sheet).write_text("\n".join(x for x in lines if x is not None), encoding="utf-8")
    print(f"batch {batch}: {position} rows in sponsorship_review, sheet at {args.sheet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
