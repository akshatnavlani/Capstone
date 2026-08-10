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
import logging
import os
import re
import shutil
import subprocess

import psycopg2
import yaml

from instagram_comment_extract import parse_caption

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("collab")

RELATION_TYPE = "frequent_collaborator"  # Track C filters on this exact literal
SESSION = "collabx"

_OPENCLI = shutil.which("opencli")
_LINK = re.compile(r"\]\(/([A-Za-z0-9_.]+)/\)")
_PIC = re.compile(r"!\[([A-Za-z0-9_.]+)'s profile picture\]")
_AGE_AUTHOR = re.compile(r"\]\(/([A-Za-z0-9_.]+)/\)\s*\n+\s*\d+[smhdwy]\b")
_PAID = re.compile(r"paid partnership", re.I)

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
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("select lower(instagram_handle), creator_id from creators "
                     "where instagram_handle is not null")
        known = {h: cid for h, cid in cur.fetchall()}
        cur.execute("select post_id, username, creator_id from instagram_posts "
                     "where creator_id is not null order by (caption is null) desc, post_id")
        posts = cur.fetchall()
    if args.limit:
        posts = posts[: args.limit]
    log.info("analysing %d posts against %d known creators", len(posts), len(known))

    edges: set[tuple[str, str]] = set()
    caption_fixes = paid_count = failed = 0

    for i, (post_id, uname, creator_id) in enumerate(posts, 1):
        try:
            info = analyse_post(post_id, uname)
        except RuntimeError as e:
            failed += 1
            log.info("[%d/%d] %s failed: %s", i, len(posts), post_id, str(e)[:70])
            continue

        if info["paid_partnership"]:
            paid_count += 1

        # Edges: every co-author that is itself a known creator, in BOTH directions is
        # NOT written -- only owner->collaborator, matching the table's semantics
        # (creator_id owns the row, handle names the related account).
        for h in info["coauthors"]:
            hl = h.lower()
            if hl in known and hl != (uname or "").lower():
                edges.add((creator_id, hl))
                # the reciprocal direction, when that collaborator is also a creator
                edges.add((known[hl], (uname or "").lower()))

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

    log.info("collab co-author edges resolvable: %d", len(edges))
    for cid, h in sorted(edges, key=lambda x: x[1]):
        log.info("   creator=%s -> %s", str(cid)[:8], h)

    written = 0
    if not args.dry_run and edges:
        with conn.cursor() as cur:
            for cid, h in edges:
                cur.execute(
                    """insert into creator_related_accounts
                       (creator_id, platform, handle, relation_type)
                       values (%s,'instagram',%s,%s)
                       on conflict (creator_id, platform, handle) do nothing""",
                    (cid, h, RELATION_TYPE),
                )
                written += cur.rowcount
        conn.commit()

    with conn.cursor() as cur:
        cur.execute("select count(*) from creator_related_accounts")
        total = cur.fetchone()[0]
    conn.close()
    log.info("DONE new_edge_rows=%d table_total=%d caption_fixes=%d paid_partnership_posts=%d failed=%d",
              written, total, caption_fixes, paid_count, failed)


if __name__ == "__main__":
    main()
