"""Extract Instagram COLLAB co-authors -> collaboration edges + recover collab captions.

WHY (Step 1 finding, 2026-08-11, evidence-based not assumed):
The 37 NULL-caption rows are **collab posts, not scraper contamination**. Evidence:
  - 11 of 18 probed posts show the stored creator's own handle in the co-author header
    block (the region before Instagram's '* * *' separator).
  - On the one profile whose grid loaded (virat.kohli), 5 of 7 NULL-caption posts are
    STILL on his live grid — a HIGHER hit rate than with-caption posts (19 of 33).
    Contamination would show the opposite: absent from the grid, not over-represented.
  - Zero probed posts showed the pure-contamination signature (stored handle absent AND
    no collapsed 'and N others' co-author list).
So the NULL caption is a SYMPTOM of a signal we want: on a collab post the caption is
authored by the PRIMARY author, so a parse anchored to the stored creator correctly
finds nothing.

Two outputs from one page fetch:
  1. creator_related_accounts rows (the edges the project has lacked for six rounds)
  2. the recovered caption, parsed against the PRIMARY author

ANCHORING DISCIPLINE (this is the bug I shipped earlier today, so it is explicit):
the previous failure searched the WHOLE document for the first `[user](/user/)` link
followed by a relative-age token, and Instagram post pages also render suggested posts,
so it frequently locked onto a stranger's post and wrote their caption. Here the search
is SCOPED to the region immediately after the '* * *' separator, which is the main
post's own block, and the detected author is cross-checked against the header co-author
list before its caption is accepted. Every fetch also asserts the returned page URL
matches the requested post_id.

Track C constraints (verified, unchanged): relation_type must be exactly
'frequent_collaborator'; both endpoints must already exist as creators rows or the
resolver silently drops the row.

Run: python collab_edges.py [--dry-run] [--limit N]
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import time

import psycopg2
import yaml

from instagram_comment_extract import parse_caption

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("collab")

RELATION_TYPE = "frequent_collaborator"  # Track C filters on this exact literal
SESSION = "collabx"

# Deliberate pacing between posts, added 2026-08-11 after hitting a real Instagram
# HTTP 429. The first version of this script had NO inter-request gap at all: it ran
# ~200 post-page fetches (3 opencli calls each) back-to-back across the backfill and
# collab passes, which is what accumulated the limit. The agent-reach skill's Instagram
# section is explicit that the response to a 429 is to re-login and REDUCE FREQUENCY,
# so this is the documented remedy rather than an invented one. orchestrator.py already
# gates at 3s; this is deliberately slower because we have now actually been limited.
POST_GAP_SECONDS = 5.0

_OPENCLI = shutil.which("opencli")
_LINK = re.compile(r"\]\(/([A-Za-z0-9_.]+)/\)")
_PIC = re.compile(r"!\[([A-Za-z0-9_.]+)'s profile picture\]")
_AGE_AUTHOR = re.compile(r"\]\(/([A-Za-z0-9_.]+)/\)\s*\n+\s*\d+[smhdwy]\b")
_PAID = re.compile(r"paid partnership", re.I)

# Co-author provenance checkpoint, rewritten as it grows so an interrupted run still
# leaves the sheet-push input on disk.
COAUTHOR_CHECKPOINT = os.path.join(os.path.dirname(__file__), "coauthor_checkpoint.json")

# Path segments that are not usernames
_NON_USER = {"explore", "reels", "p", "accounts", "directory", "about", "legal", "stories"}


def load_env():
    env = dict(os.environ)
    with open(os.path.join(os.path.dirname(__file__), "..", "..", ".env"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k, v)
    return env


ENV = load_env()


def run_opencli(*args, timeout=90):
    e = dict(os.environ)
    if ENV.get("OPENCLI_PROFILE"):
        e["OPENCLI_PROFILE"] = ENV["OPENCLI_PROFILE"]
    r = subprocess.run([_OPENCLI, *args], capture_output=True, text=True,
                        timeout=timeout, env=e, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"opencli {' '.join(args)}: {r.stdout}{r.stderr}")
    return yaml.safe_load(r.stdout)


def analyse_post(post_id: str, stored_username: str) -> dict | None:
    """Fetch one post page and return co-authors, primary author, caption, paid flag."""
    run_opencli("browser", SESSION, "open", f"https://www.instagram.com/p/{post_id}/")
    run_opencli("browser", SESSION, "wait", "time", "2")
    ex = run_opencli("browser", SESSION, "extract")
    if not isinstance(ex, dict):
        raise RuntimeError("no envelope")
    if post_id not in (ex.get("url") or ""):
        raise RuntimeError(f"page mismatch: got {ex.get('url')}")
    md = ex.get("content") or ""

    sep = md.find("* * *")
    header = md[:sep] if sep > 0 else md[:2500]
    body = md[sep:sep + 4000] if sep > 0 else md[:4000]

    # Co-authors: both the linked handles and the rendered profile-picture alt-text in
    # the header. The picture alts catch collaborators whose link is collapsed behind
    # an "and N others" control.
    coauthors = [u for u in dict.fromkeys(_LINK.findall(header) + _PIC.findall(header))
                 if u not in _NON_USER]

    # Primary author, scoped to the main post block only (NOT first-match-in-document).
    m = _AGE_AUTHOR.search(body)
    primary = m.group(1) if m else None

    caption = None
    if primary:
        # Only trust the primary author if it is corroborated by the header block.
        if primary in coauthors or primary == stored_username:
            caption = parse_caption(md, primary)
    if not caption:
        caption = parse_caption(md, stored_username)

    return {
        "post_id": post_id, "stored": stored_username, "primary": primary,
        "coauthors": coauthors, "caption": caption,
        "paid_partnership": bool(_PAID.search(md)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only-new", action="store_true",
                     help="Only posts never scanned before (has_paid_partnership_label IS NULL). "
                          "Re-scanning already-scanned posts costs ~13s each and adds "
                          "rate-limit exposure for no new information, since co-authors and "
                          "the paid-partnership flag don't change retroactively.")
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("select lower(instagram_handle), creator_id from creators "
                     "where instagram_handle is not null")
        known = {h: cid for h, cid in cur.fetchall()}
        cur.execute("select post_id, username, creator_id from instagram_posts "
                     "where creator_id is not null "
                     + ("and has_paid_partnership_label is null " if args.only_new else "")
                     + "order by (caption is null) desc, post_id")
        posts = cur.fetchall()
    if args.limit:
        posts = posts[: args.limit]
    log.info("analysing %d posts against %d known creators", len(posts), len(known))

    edges: set[tuple[str, str]] = set()
    observed_coauthors: dict[str, list] = {}  # handle -> [(owner_username, post_id), ...]
    caption_fixes = paid_count = failed = written = 0

    for i, (post_id, uname, creator_id) in enumerate(posts, 1):
        if i > 1:
            time.sleep(POST_GAP_SECONDS)
        try:
            info = analyse_post(post_id, uname)
        except RuntimeError as e:
            failed += 1
            msg = str(e)
            log.info("[%d/%d] %s failed: %s", i, len(posts), post_id, msg[:70])
            # A 429 is the platform telling us to stop, not a per-item hiccup. Abort the
            # run rather than grinding through the remaining posts and deepening the
            # limit -- the mistake that caused it in the first place.
            if "429" in msg:
                log.warning("HTTP 429 — aborting run immediately to avoid deepening the "
                             "rate limit. Re-run later; the script is resumable.")
                break
            continue

        if info["paid_partnership"]:
            paid_count += 1
        if not args.dry_run:
            # Raw observation only -- Track C owns is_sponsored. Written for every post
            # actually fetched, so FALSE means "fetched, no label" and NULL keeps
            # meaning "never observed".
            with conn.cursor() as cur:
                cur.execute(
                    "update instagram_posts set has_paid_partnership_label=%s where post_id=%s",
                    (bool(info["paid_partnership"]), post_id),
                )
            conn.commit()

        # Write a row for EVERY observed collaboration, not only the ones that resolve
        # today. Corrected 2026-08-11 after being (rightly) called over-cautious: Track
        # C's resolver matches handle text against creators AT RESOLUTION TIME, so a row
        # for (virat.kohli, instagram, anushkasharma) resolves to nothing now and
        # AUTO-RESOLVES the moment anushkasharma is promoted -- no re-scrape, no rework.
        # These facts cost rate-limited Instagram fetches to obtain and are nearly free
        # to store. Unresolvable rows are silently skipped by the resolver, UNIQUE
        # prevents duplicates, creator_id is still a valid FK, and nothing touches the
        # creator set. Discarding them was throwing away expensive data.
        # INCREMENTAL FLUSH (2026-08-14). Previously these were accumulated in memory and
        # written once at the end -- which cost a real run: the 97-post pass was killed at
        # ~83/97 and every edge it had discovered was lost, because the INSERT never ran.
        # The per-post writes in that same run (captions, paid-partnership flag) all
        # survived. So the rule is simply: write when you learn it. An interruption now
        # costs at most the single post being fetched.
        post_edges: set[tuple[str, str]] = set()
        for h in info["coauthors"]:
            hl = h.lower()
            if hl and hl != (uname or "").lower():
                post_edges.add((creator_id, hl))
                # reciprocal direction only when that collaborator IS a creator (we need
                # a real creator_id to own the row)
                if hl in known:
                    post_edges.add((known[hl], (uname or "").lower()))
            if hl:
                observed_coauthors.setdefault(hl, []).append((uname, post_id))

        new_this_post = post_edges - edges
        edges |= post_edges
        if new_this_post and not args.dry_run:
            with conn.cursor() as cur:
                for cid, h in new_this_post:
                    cur.execute(
                        """insert into creator_related_accounts
                           (creator_id, platform, handle, relation_type)
                           values (%s,'instagram',%s,%s)
                           on conflict (creator_id, platform, handle) do nothing""",
                        (cid, h, RELATION_TYPE),
                    )
                    written += cur.rowcount
            conn.commit()

        # Co-author provenance is checkpointed to disk each time it grows, so a kill
        # cannot lose the sheet-push input either. Cheap local write, no API cost.
        if new_this_post and not args.dry_run:
            try:
                with open(COAUTHOR_CHECKPOINT, "w", encoding="utf-8") as f:
                    json.dump({k: v for k, v in observed_coauthors.items()}, f, indent=2)
            except OSError:
                pass

        if info["caption"] and not args.dry_run:
            with conn.cursor() as cur:
                cur.execute(
                    "update instagram_posts set caption=%s where post_id=%s "
                    "and length(coalesce(caption,'')) < %s",
                    (info["caption"], post_id, len(info["caption"])),
                )
                if cur.rowcount:
                    caption_fixes += 1
            conn.commit()

    log.info("distinct collaboration pairs observed: %d (rows newly inserted: %d)",
              len(edges), written)

    with conn.cursor() as cur:
        cur.execute("select count(*) from creator_related_accounts")
        total = cur.fetchone()[0]
        # RESOLVED = rows whose handle matches some OTHER creator's own handle. This is
        # what Track C's resolver can actually turn into an edge; report it separately
        # from rows written, because they now legitimately differ.
        cur.execute("""
            select count(*) from creator_related_accounts r
            where r.relation_type = %s
              and exists (select 1 from creators c
                          where lower(c.instagram_handle) = lower(r.handle)
                            and c.creator_id <> r.creator_id)
        """, (RELATION_TYPE,))
        resolved = cur.fetchone()[0]
    conn.close()
    log.info("DONE new_edge_rows=%d table_total=%d RESOLVED=%d caption_fixes=%d paid_partnership_posts=%d failed=%d",
              written, total, resolved, caption_fixes, paid_count, failed)

    # Co-authors -> sheet for USER REVIEW. Never auto-promoted: many are orgs, brands or
    # politicians (commonwealthsport, globalboxingseries, naralokesh), and promoting them
    # wholesale would pollute the creator set and re-import the #fitindia-collision class
    # of error. They enter the normal curation flow with approval_status BLANK.
    if observed_coauthors and not args.dry_run:
        import sheets_sync
        known_lower = set(known)
        new = {h: v for h, v in observed_coauthors.items() if h not in known_lower}
        rows_out = []
        for h, occurrences in sorted(new.items()):
            owner, post_id = occurrences[0]
            rows_out.append({
                "name": h,
                "instagram_handle": h,
                "category": "other",  # best guess; must be a CHECK value if ever promoted
                "follower_count": "",
                "notes": f"co-author of @{owner} on post {post_id}"
                         + (f" (+{len(occurrences)-1} more collab posts)" if len(occurrences) > 1 else ""),
                "brand_signals": "",
                "approval_status": "",
            })
        try:
            n = sheets_sync.push_candidates(rows_out)
            # NB "already creators" counts observed handles that exist as creators,
            # which INCLUDES self-references (a creator's own handle appearing in the
            # header of their own post). Those are correctly excluded from edges, so
            # this number is NOT an upper bound on resolvable edges -- it briefly read
            # that way and caused real confusion. Only a co-author appearing on ANOTHER
            # creator's post can produce a resolvable edge.
            log.info("pushed %d NEW co-author candidates to the sheet for review "
                      "(%d distinct co-authors observed, %d of them already creators "
                      "incl. self-references)", n, len(observed_coauthors),
                      len(observed_coauthors) - len(new))
        except Exception as e:
            log.warning("sheet push failed: %s", e)


if __name__ == "__main__":
    main()
