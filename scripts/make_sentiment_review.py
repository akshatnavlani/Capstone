"""Sample comments for the human check of the sentiment scorer, by language (English / Hinglish / Devanagari).

    python scripts/make_sentiment_review.py --per-language 40      # writes rows into sentiment_review (table from migration 20261022000000)
    python scripts/make_sentiment_review.py --dry-run               # counts only

Comments come from the verified creators' YouTube, Instagram and Reddit comments, 20-220 characters, no links, at least 4 words, no
creator-owned text duplicates. The model's score is stored with each row but never shown to the reviewer. Safe to run again: comments
already sampled are skipped. Batches of 20 mix the three languages.
"""
import argparse
import html
import os
import random
import re
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# Hindi words written in Roman letters that are not English words; two or more distinct ones mark a comment as Hinglish.
HINDI_ROMAN = set("""bhai bhaiya hai hain nahi nahin nhi kya kyu kyun kyon aap aapka tum tumhara mat ko ka ki ke se mein ye yeh wo woh kaise kitna kitne
bahut bohot acha accha achha sahi bhi aur toh hoga hogi karo karna yaar lekin abhi kuch koi mera meri tera teri apna apni wala wali
dekho dekh liye diya mujhe tumhe unka isme usme jaise kaun kab kahan kaha bolo raha rahi rahe tha thi lagta lagti bilkul zyada jyada
thoda sabse sirf matlab pata chahiye chahie milega milegi aaj""".split())
# words left out on purpose because they are also ordinary English words: me, to, so, sir, ji, kar (car), par, the, sab, bol, lena, dena, kal
ENGLISH_STOP = set("the is are you your this that and for with was were have has it's its not but can just very so what how why my me".split())
URL = re.compile(r"https?://|www\.", re.I)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def language_of(text: str) -> str | None:
    """'devanagari', 'hinglish', 'english' or None (not usable)."""
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 12:
        return None
    if sum(1 for c in letters if DEVANAGARI.match(c)) / len(letters) > 0.3:
        return "devanagari"
    if any(ord(c) > 0x024F and not DEVANAGARI.match(c) for c in letters):
        return None                                   # another script (Tamil, Telugu, Arabic ...): not part of this check
    words = re.findall(r"[a-z']+", text.lower())
    hindi = {w for w in words if w in HINDI_ROMAN}
    english = sum(1 for w in words if w in ENGLISH_STOP)
    if len(hindi) >= 2:
        return "hinglish"
    if not hindi and english >= 2:
        return "english"
    return None


def usable(text: str) -> bool:
    return 20 <= len(text) <= 220 and len(text.split()) >= 4 and not URL.search(text) and not re.search(r"(.)\1{5,}", text)


QUERIES = {
    "youtube": "select c.comment_id, v.creator_id::text, c.text from youtube_comments c join youtube_videos v on v.video_id = c.video_id where c.text is not null and v.creator_id in {ver}",
    "instagram": "select c.comment_id, p.creator_id::text, c.text from instagram_comments c join instagram_posts p on p.post_id = c.post_id where c.text is not null and p.creator_id in {ver}",
    "reddit": "select c.comment_id, rp.creator_id::text, c.body from reddit_comments c join reddit_posts p on p.post_id = c.post_id "
              "join lateral (select creator_id from reddit_post_creators r where r.post_id = p.post_id limit 1) rp on true where c.body is not null and rp.creator_id in {ver}",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-language", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed", type=int, default=22)
    args = ap.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        m = re.search(r"^DATABASE_URL=(.+)$", (ROOT / ".env").read_text(encoding="utf-8"), re.M)
        url = m.group(1).strip().strip('"') if m else ""
    conn = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"))
    cur = conn.cursor()
    ver = "(select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed','probable'))"
    cur.execute("select platform, comment_id from sentiment_review")
    done = set(cur.fetchall())
    pool = {"english": [], "hinglish": [], "devanagari": []}
    for platform, sql in QUERIES.items():
        cur.execute(sql.format(ver=ver))
        for cid, creator, text in cur.fetchall():
            t = clean(text)
            if (platform, cid) in done or not usable(t):
                continue
            lang = language_of(t)
            if lang:
                pool[lang].append((platform, cid, creator, t))
    print({k: len(v) for k, v in pool.items()}, "usable comments by language")
    rng = random.Random(args.seed)
    pick = {}
    for lang, rows in pool.items():
        seen, chosen = set(), []
        rng.shuffle(rows)
        for r in rows:
            key = r[3].lower()[:60]
            if key not in seen:
                seen.add(key); chosen.append(r)
            if len(chosen) == args.per_language:
                break
        pick[lang] = chosen
    print({k: len(v) for k, v in pick.items()}, "sampled")
    if args.dry_run:
        return
    from ml._scipy_compat import avoid_blocked_scipy_solver
    avoid_blocked_scipy_solver()
    from ml.temporal.sentiment import SentimentScorer
    scorer = SentimentScorer()
    cur.execute("select coalesce(max(batch), 0) from sentiment_review")
    first_batch = cur.fetchone()[0] + 1
    rows = []
    for lang, items in pick.items():
        scores = scorer.score([t for *_x, t in items])
        rows += [(lang, *it, float(s) if s == s else None) for it, s in zip(items, scores)]
    rng.shuffle(rows)                                      # batches of 20 mix the languages
    for i, (lang, platform, cid, creator, text, score) in enumerate(rows):
        cur.execute("""insert into sentiment_review (batch, position, language, platform, comment_id, creator_id, comment_text, model_score)
                       values (%s,%s,%s,%s,%s,%s,%s,%s) on conflict (platform, comment_id) do nothing""",
                    (first_batch + i // 20, 1 + i % 20, lang, platform, cid, creator, text, score))
    conn.commit()
    cur.execute("select language, count(*) from sentiment_review group by 1 order by 1")
    print("in sentiment_review now:", cur.fetchall())


if __name__ == "__main__":
    main()
