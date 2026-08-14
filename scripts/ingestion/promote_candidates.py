"""Promote accepted sheet candidates into the `creators` table (P0.3).

The identify -> curate -> PROMOTE -> deepen flow was missing its third step, so ~123
curated candidates existed only on the Google Sheet with no DB row, and deepening had
nothing to attach content to.

Constraints, each verified directly against the live DB on 2026-08-11 (not taken from
docs):
  - `creators` has NO follower_count column. Confirmed by reading
    information_schema.columns. It goes to `instagram_profiles.follower_count`.
  - `category` CHECK constraint is exactly:
    athlete | team | league | fitness_influencer | lifestyle_influencer | other
    Confirmed via pg_get_constraintdef. Any other value hard-fails the insert, so
    unknown values are coerced to 'other' and reported rather than sent through.
  - Unique partial indexes exist on youtube_handle and instagram_handle (WHERE NOT
    NULL) -- these are what make handle-matching upserts safe.
  - `approval_status` is the user's column. This script NEVER writes to the sheet.

Upsert, not insert-only: the sheet legitimately holds values the DB lacks (e.g.
`athleanx` has an instagram_handle on the sheet but NULL in the DB), so promoting must
enrich existing rows, not skip them. Reuses orchestrator.get_or_create_creator, which
is already idempotent across all handles and merges rather than duplicating -- so the
16 grandfathered creators are matched and enriched, never re-inserted.

Run:  python promote_candidates.py [--dry-run]
"""

import argparse
import logging
import os

import psycopg2

import sheets_sync
from orchestrator import ENV, get_or_create_creator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("promote")

VALID_CATEGORIES = {
    "athlete", "team", "league", "fitness_influencer", "lifestyle_influencer", "other",
}


def clean(value) -> str | None:
    """Sheet cells arrive as strings; 'null'/'' mean absent, not a literal handle."""
    if value is None:
        return None
    v = str(value).strip()
    if not v or v.lower() in {"null", "none", "[]"}:
        return None
    return v


def parse_list(value) -> list[str]:
    v = clean(value)
    if not v:
        return []
    try:
        import json
        parsed = json.loads(v)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--handles", nargs="+", metavar="IG_HANDLE",
                     help="Promote ONLY these instagram handles (must still be 'accepted' on "
                          "the sheet). Required by the standing targeted-promotion rule: promote "
                          "a candidate only when their handle already sits in an unresolved "
                          "creator_related_accounts row, so the promotion immediately converts a "
                          "dangling row into a real edge. Without this flag the script promotes "
                          "EVERY accepted row, which adds creators without adding training pairs.")
    args = ap.parse_args()

    rows = sheets_sync.read_rows()
    accepted = [r for r in rows if (r.get("approval_status") or "").strip().lower() == "accepted"]
    log.info("sheet rows=%d accepted=%d", len(rows), len(accepted))

    if args.handles:
        wanted = {h.strip().lstrip("@").lower() for h in args.handles}
        accepted = [r for r in accepted
                     if (clean(r.get("instagram_handle")) or "").lstrip("@").lower() in wanted]
        found = {(clean(r.get("instagram_handle")) or "").lstrip("@").lower() for r in accepted}
        missing = wanted - found
        if missing:
            # Loud, not silent: a typo or a not-yet-accepted handle would otherwise look
            # like a successful no-op run.
            log.error("not accepted on the sheet (or handle typo), NOT promoting: %s",
                       ", ".join(sorted(missing)))
        log.info("targeted promotion: %d of the accepted rows selected", len(accepted))

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    promoted = enriched = skipped = 0
    bad_category = []

    for r in accepted:
        name = clean(r.get("name"))
        if not name:
            skipped += 1
            continue
        category = (clean(r.get("category")) or "other").lower()
        if category not in VALID_CATEGORIES:
            # Coerced, not sent through: an invalid value hard-fails the CHECK and
            # would abort the whole batch mid-way.
            bad_category.append((name, category))
            category = "other"

        ig = clean(r.get("instagram_handle"))
        yt = clean(r.get("youtube_handle"))
        if not ig and not yt:
            # No handle => nothing to match on and nothing to scrape. Reddit-only
            # candidates aren't promotable through this path.
            log.info("skip %s: no instagram/youtube handle to match on", name)
            skipped += 1
            continue

        if args.dry_run:
            log.info("[dry-run] would promote %s (%s) ig=%s yt=%s", name, category, ig, yt)
            promoted += 1
            continue

        with conn.cursor() as cur:
            cur.execute(
                "select creator_id from creators where "
                "(instagram_handle is not null and instagram_handle=%s) or "
                "(youtube_handle is not null and youtube_handle=%s)",
                (ig, yt),
            )
            pre_existing = cur.fetchone() is not None

        creator = get_or_create_creator(
            conn, name=name, category=category,
            instagram_handle=ig, youtube_handle=yt,
            reddit_handles=parse_list(r.get("reddit_handles")),
            reddit_topic_subs=parse_list(r.get("reddit_topic_subs")),
        )
        conn.commit()

        if pre_existing:
            enriched += 1
        else:
            promoted += 1

        # follower_count lives on instagram_profiles, NOT creators. Insert a lean
        # profile row if absent; never clobber an existing follower_count with a
        # staler sheet value, and never touch creator_id=null rows (they're comment
        # authors, deliberately lean -- see schema notes).
        fc = clean(r.get("follower_count"))
        if ig and fc and fc.isdigit():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into instagram_profiles (username, creator_id, follower_count)
                    values (%s,%s,%s)
                    on conflict (username) do update set
                        creator_id = coalesce(instagram_profiles.creator_id, excluded.creator_id),
                        follower_count = coalesce(instagram_profiles.follower_count, excluded.follower_count)
                    """,
                    (ig, creator.creator_id, int(fc)),
                )
            conn.commit()

    conn.close()
    log.info("DONE newly_promoted=%d enriched_existing=%d skipped=%d", promoted, enriched, skipped)
    if bad_category:
        log.warning("coerced %d invalid categories to 'other': %s", len(bad_category), bad_category)


if __name__ == "__main__":
    main()
