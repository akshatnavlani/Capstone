"""Draw the Hinglish sentiment test set to label by hand (novelty F). READ ONLY on the database; writes exports/hinglish_labeling_sample.csv.

    python scripts/make_hinglish_sample.py [--n 120] [--seed 7]

WHY. Comment sentiment on Hindi-English (romanised Hindi mixed with English) text is the weakest part of the sentiment branch (correlation about 0.47 with hand labels). To say how good the model really
is on this kind of comment, a person has to label a random sample. The sample is drawn BEFORE any model sees it, at random, at most 3 comments per creator, so the score is not tuned to it.

Fill in the `your_label` column with one of: positive, neutral, negative (or skip, if the comment cannot be understood). Then run scripts/score_hinglish_sample.py (not written until the labels exist).
A comment counts as code-mixed when it is written in Latin letters and holds at least two common romanised Hindi words.
"""
import argparse
import csv
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HINDI_WORDS = {
    "hai", "hain", "nahi", "nahin", "bhai", "bhaiya", "kya", "kaise", "kaisa", "ye", "yeh", "woh", "wo", "mera", "meri", "tera", "teri", "aap", "tum", "tu", "hum", "mujhe", "tumhe", "apna", "sab", "bohot", "bahut",
    "accha", "acha", "achha", "badhiya", "mast", "zabardast", "kamaal", "shandar", "gazab", "bekar", "bakwas", "faltu", "kuch", "koi", "kyun", "kyu", "lekin", "par", "aur", "toh", "to", "ho", "hota", "hoga", "karo",
    "kar", "karna", "karte", "raha", "rahi", "rahe", "wala", "wali", "liye", "se", "ko", "ka", "ki", "ke", "me", "mein", "pe", "dena", "lena", "bata", "batao", "sir", "video", "dekh", "dekha", "samajh", "dhanyawad",
}
LATIN = re.compile(r"^[\x20-\x7E’‘“”\U0001F300-\U0001FAFF☀-➿]+$")


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        m = re.search(r"^DATABASE_URL=(.+)$", (ROOT / ".env").read_text(encoding="utf-8"), re.M)
        url = m.group(1).strip().strip('"')
    return url.replace("postgresql+psycopg2://", "postgresql://")


def is_code_mixed(text: str) -> bool:
    if not LATIN.match(text):
        return False
    words = re.findall(r"[a-z]+", text.lower())
    strong = [w for w in words if w in HINDI_WORDS and w not in {"to", "me", "se", "par", "sir", "video", "ho", "ko", "ka", "ki", "ke", "pe", "aur"}]
    return len(set(strong)) >= 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "exports" / "hinglish_labeling_sample.csv"))
    args = ap.parse_args()
    conn = psycopg2.connect(database_url(), connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    # a random 60,000-comment pool keeps the query fast; the draw below is random inside it
    cur.execute("""select c.comment_id, v.creator_id::text, cr.name, c.text from youtube_comments c
                   join youtube_videos v on v.video_id = c.video_id join creators cr on cr.creator_id = v.creator_id
                   where length(c.text) between 25 and 220 and v.creator_id is not null
                   order by md5(c.comment_id || %s) limit 60000""", (str(args.seed),))
    pool = [r for r in cur.fetchall() if is_code_mixed(r[3])]
    random.Random(args.seed).shuffle(pool)
    per, rows = Counter(), []
    for cid, creator_id, name, text in pool:
        if per[creator_id] >= 3:
            continue
        per[creator_id] += 1
        rows.append((cid, name, re.sub(r"\s+", " ", text).strip()))
        if len(rows) == args.n:
            break
    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "creator", "comment", "your_label (positive / neutral / negative / skip)"])
        for r in rows:
            w.writerow([*r, ""])
    print(f"{len(pool)} code-mixed comments in the pool; wrote {len(rows)} from {len(per)} creators to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
