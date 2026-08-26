"""Backfill `creators.name` for handle-named creators from their live Instagram profile.

WHY THIS IS ONLY NOW POSSIBLE. Bulk promotion set `creators.name = instagram_handle` for 200+
creators, and the Reddit topic-sub search queries by `name` -- so a handle-shaped name is the
single precondition failure blocking all Reddit work for them (P0.5).

The previous attempt (2026-08-17) resolved ZERO and diagnosed why: the profile fetch already
returns the name, it was simply never persisted, and re-fetching needed Instagram calls that
were blocked behind a sustained HTTP 429. **That block has cleared** -- the adapter succeeded on
every call made on 2026-08-19 -- so this is the same plan, finally runnable.

DB-side sources are exhausted and cannot close this. Measured 2026-08-19 against the 200
name-gated creators: YouTube channel description covers 5, YouTube title 5,
`instagram_profiles.full_name` 8, `instagram_profiles.bio` 7. A live fetch is the only source
with the reach to matter.

WHAT COUNTS AS A REAL NAME: `looks_like_real_name()` -- reused, not reimplemented -- requires a
SPACE. That is not cosmetic. Reddit tokenizes on separators, so "Mumbai Indians" is searchable
where "mumbaiindians" is not; word separation IS the improvement. A spacing-blind version of
this check previously rejected 17 recoverable names as "no change".

Never guesses. A profile with no name, or a name equal to the handle, is left alone and counted
as genuinely unresolvable -- an acceptable outcome for handle-only personas, not a failure.

Run: python backfill_real_names.py [--dry-run] [--limit N]
"""

import argparse
import json
import logging
import os
import re
import time
import unicodedata

import psycopg2

from account_classify import fetch_profile
from assign_reddit_subs import looks_like_real_name
from orchestrator import ENV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("names")

# A name is only useful here if REDDIT CAN SEARCH IT, so the raw profile name is cleaned
# before it is judged. Every rule below comes from a real value seen in the first dry run:
#   'Shivaldo_Chingangbam'                        -> separators are real word breaks
#   'Saurabh Thapa | Fitness Experience Designer' -> the suffix is a job title, not a name
#   'RAGI CHAUDHARY[flag emoji]'                  -> decoration that no Reddit post contains
_SUFFIX_SEPS = ("|", "•", "·", "—", "–", "/")


# Variation selectors and ZWJ are Unicode MARKS/format chars, so a category test keeps them.
# They carry no searchable text and left a trailing artefact on a real name.
_INVISIBLE = {"‍", "‌", "﻿"} | {chr(c) for c in range(0xFE00, 0xFE10)}


def _keepable(ch: str) -> bool:
    r"""Keep letters, COMBINING MARKS, and digits; everything else becomes a space.

    The marks matter and a `\w`-based regex silently drops them: Devanagari vowel signs are
    Unicode category Mc/Mn, which Python's `\w` does NOT match, so a regex filter turned
    'ऋचा चौहान' into 'ऋच च ह न' -- every matra stripped, the name destroyed and unsearchable.
    Caught 2026-08-19 on a real profile, so this is category-based, not pattern-based.
    """
    if ch in _INVISIBLE:
        return False
    return unicodedata.category(ch)[0] in ("L", "M", "N")


def clean_name(raw: str) -> str:
    """Normalise a profile name into something Reddit search can actually match."""
    if not raw:
        return ""
    name = raw
    for sep in _SUFFIX_SEPS:          # 'Saurabh Thapa | Fitness ...' -> 'Saurabh Thapa'
        if sep in name:
            name = name.split(sep)[0]
    name = "".join(ch if (_keepable(ch) or ch in " '-") else " " for ch in name)
    name = re.sub(r"[_.]+", " ", name)  # 'Shivaldo_Chingangbam' -> 'Shivaldo Chingangbam'
    return re.sub(r"\s+", " ", name).strip()


CHECKPOINT = os.path.join(os.path.dirname(__file__), "name_backfill_checkpoint.json")

# Creators whose Reddit work is blocked purely because name == handle.
GATED = """
    select c.creator_id, c.instagram_handle
    from creators c
    where c.instagram_handle is not null
      and lower(c.name) = lower(c.instagram_handle)
      and not exists (select 1 from reddit_posts r where r.creator_id = c.creator_id)
      and not exists (select 1 from reddit_post_creators r where r.creator_id = c.creator_id)
      and coalesce(array_length(c.reddit_topic_subs, 1), 0) = 0
      and coalesce(array_length(c.reddit_handles, 1), 0) = 0
    order by c.instagram_handle
"""


def load_done() -> dict:
    try:
        with open(CHECKPOINT, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_done(done: dict) -> None:
    with open(CHECKPOINT, "w", encoding="utf-8") as fh:
        json.dump(done, fh, ensure_ascii=False, indent=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ignore-checkpoint", action="store_true",
                     help="Re-process creators already attempted. Needed once, to capture the "
                          "bios that earlier runs fetched and discarded; names already correct "
                          "are simply rewritten with the same value.")
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    with conn.cursor() as cur:
        if args.ignore_checkpoint:
            # Bio-capture pass: the creators whose bios were fetched and dropped are the ones
            # ALREADY resolved, so the name-gated query would skip precisely the wrong set.
            cur.execute("""
                select c.creator_id, c.instagram_handle from creators c
                join instagram_profiles p on lower(p.username) = lower(c.instagram_handle)
                where c.instagram_handle is not null and length(coalesce(p.bio, '')) = 0
                order by c.instagram_handle
            """)
        else:
            cur.execute(GATED)
        gated = cur.fetchall()

    done = load_done()
    todo = gated if args.ignore_checkpoint else [(cid, h) for cid, h in gated if h not in done]
    if args.limit:
        todo = todo[: args.limit]
    log.info("name-gated: %d  |  already attempted: %d  |  this run: %d",
              len(gated), len(done), len(todo))

    resolved = unresolved = failed = 0
    for i, (cid, handle) in enumerate(todo, 1):
        try:
            prof = fetch_profile(handle)
        except Exception as e:
            failed += 1
            log.warning("[%d/%d] %s: fetch failed (%s)", i, len(todo), handle, str(e)[:80])
            continue
        raw = (prof or {}).get("name") or ""
        name = clean_name(raw)

        # PERSIST THE BIO TOO. The fetch returns it either way, and throwing it away is what
        # left only 26 of 16,815 profile rows with any bio -- which in turn capped the
        # account_classify held-out set at 17 usable cases and leaves `assign_reddit_subs`
        # with no way to tell a tennis player from a cricketer. Same call, no extra cost.
        bio = (prof or {}).get("bio") or ""
        if bio and not args.dry_run:
            with conn.cursor() as cur:
                cur.execute("""
                    update instagram_profiles set bio=%s, updated_at=now()
                    where lower(username)=lower(%s) and length(coalesce(bio,'')) = 0
                """, (bio, handle))
            conn.commit()

        if not looks_like_real_name(name, handle):
            unresolved += 1
            done[handle] = {"status": "unresolvable", "raw_name": raw}
            log.info("[%d/%d] %s: no usable name (raw=%r)", i, len(todo), handle, raw[:40])
        else:
            resolved += 1
            done[handle] = {"status": "resolved", "name": name, "raw_name": raw}
            log.info("[%d/%d] %s -> %r%s", i, len(todo), handle, name,
                      "" if name == raw else f"   (cleaned from {raw!r})")
            if not args.dry_run:
                with conn.cursor() as cur:
                    cur.execute("update creators set name=%s where creator_id=%s", (name, cid))
                    # Persist to the profile row too, so the DB-side source stops being empty
                    # for the next tool that looks there.
                    cur.execute("""
                        update instagram_profiles set full_name=%s
                        where lower(username)=lower(%s)
                          and length(coalesce(full_name,'')) = 0
                    """, (name, handle))
                conn.commit()
        if not args.dry_run:
            save_done(done)
        time.sleep(3)

    conn.close()
    log.info("DONE resolved=%d unresolvable=%d fetch_failed=%d%s",
              resolved, unresolved, failed, "  [DRY RUN]" if args.dry_run else "")


if __name__ == "__main__":
    main()
