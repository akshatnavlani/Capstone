"""Find comments that look like buying or wanting to buy (English, Hindi, Hinglish) and save the matches.

    python purchase_intent.py --dry-run     # counts only, writes nothing
    python purchase_intent.py               # saves the matches in purchase_intent_comments (safe to re-run)

This is a PROXY outcome, not sales: a comment saying "ordered" or "kahan se milega" is an audience reaction to a promotion.
Two kinds: 'bought' (says they ordered, bought, or used the code) and 'asking' (asks where to buy, for the link, or the price).
Phrases are matched as whole words (Roman text) or substrings (Devanagari). Every phrase is checked in test_purchase_intent.py.
"""

import argparse
import html
import re

# Strongest first: a comment gets the first kind it matches, plus 'asking' if it also asks.
BOUGHT = [
    r"just ordered", r"ordered (it|this|these|them|yesterday|today|using|with)", r"i ordered", r"i have ordered", r"already ordered",
    r"just bought", r"bought (it|this|these|from you|using|with)", r"i (just )?purchased (it|this|these|from|using|with)", r"have purchased (it|this|these|from|using|with)",
    r"order kiya", r"order kar diya", r"order kar liya", r"order kar di", r"maine order", r"mangwaya", r"mangaya", r"mangwa liya",
    r"kharid liya", r"kharid li",
    r"used (your|ur|the) code", r"using (your|ur) code", r"applied (your|ur|the) code", r"code worked", r"code applied",
    r"got it using", r"ordered using", r"ordered with",
    r"ऑर्डर कर", r"ऑर्डर किया", r"खरीद लिया", r"मंगवाया",
]
ASKING = [
    r"where (can i|to|do i) buy", r"where to get", r"where can i get", r"from where (to|can i) (buy|get|order)",
    r"link (please|pls|plz|bhejo|do|dedo|de do)", r"link\s*\?", r"drop the link", r"share the link", r"link in (the )?(bio|description|comments?)\??",
    r"kahan se (milega|milegi|le|kharid|order|buy)", r"kaha se (milega|milegi|le|kharid|order|buy)", r"kidhar (milega|milegi)",
    r"kaise (order|kharid|buy)", r"order kaise", r"kaise milega", r"buy kaise", r"kahan milega",
    r"(what|whats|what's) (is )?the (price|cost) of (it|this|that|these)", r"price (kya|kitna|\?)", r"kitne ka", r"kitna (price|ka|hai)", r"how much (is|does) (it|this|that|these) (cost)?", r"cost\s*\?", r"price\s*\?",
    r"कहाँ से (मिलेगा|मिलेगी|ले|खरीद)", r"कहां से (मिलेगा|मिलेगी|ले|खरीद)", r"लिंक दो", r"लिंक भेजो", r"कितने का", r"कीमत क्या",
]
_COMPILED = {
    "bought": [(p, re.compile(r"(?<![a-z0-9])" + p + r"(?![a-z0-9])" if p.isascii() else p, re.I)) for p in BOUGHT],
    "asking": [(p, re.compile(r"(?<![a-z0-9])" + p + r"(?![a-z0-9])" if p.isascii() else p, re.I)) for p in ASKING],
}


def purchase_intent(text: str | None) -> list[tuple[str, str]]:
    """[('bought', 'order kiya'), ('asking', 'link please')] for the first phrase of each kind found in the comment."""
    if not text:
        return []
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))   # YouTube comments arrive with HTML links and line breaks
    out = []
    for kind in ("bought", "asking"):
        for _pattern, rx in _COMPILED[kind]:
            m = rx.search(text)
            if m:
                out.append((kind, m.group(0).lower()[:60]))
                break
    return out


QUERIES = {
    "youtube": "select c.comment_id, c.video_id, v.creator_id, c.text from youtube_comments c join youtube_videos v on v.video_id = c.video_id where c.text is not null",
    "instagram": "select c.comment_id, c.post_id, p.creator_id, c.text from instagram_comments c join instagram_posts p on p.post_id = c.post_id where c.text is not null",
    "reddit": "select c.comment_id, c.post_id, rp.creator_id, c.body from reddit_comments c join reddit_posts p on p.post_id = c.post_id "
              "left join lateral (select creator_id from reddit_post_creators r where r.post_id = p.post_id limit 1) rp on true where c.body is not null",
}


def main() -> None:
    from psycopg2.extras import execute_values

    from orchestrator import get_connection
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = get_connection()
    rows = []
    for platform, sql in QUERIES.items():
        total = 0
        with conn.cursor(name=f"pi_{platform}") as cur:
            cur.itersize = 5000
            cur.execute(sql)
            for cid, post, creator, text in cur:
                total += 1
                for kind, phrase in purchase_intent(text):
                    rows.append((platform, cid, post, creator, kind, phrase))
        hits = sum(1 for r in rows if r[0] == platform)
        print(f"{platform}: {total} comments read, {hits} matches ({100.0 * hits / max(total, 1):.2f}%)", flush=True)
    if args.dry_run:
        print("[DRY RUN] nothing written")
        return
    with conn.cursor() as cur:
        execute_values(cur, """insert into purchase_intent_comments (platform, comment_id, post_id, creator_id, kind, phrase) values %s
                               on conflict (platform, comment_id, kind) do update set phrase = excluded.phrase, scored_at = now()""", rows, page_size=2000)
    conn.commit()
    print("saved", len(rows), "matches")


if __name__ == "__main__":
    main()
