"""Backfill instagram_posts.caption for rows scraped before the full-caption fix (P0.1).

Why this exists — the distinction matters. There are TWO caption defects in the live data,
with different signatures, but ONE root cause:

  - 49 rows: caption IS NULL. These correlate PERFECTLY with media_type IS NULL, i.e. the
    per-post metadata dict was empty ({}), so every field sourced from the `instagram user`
    listing was None. (Positional matching between `browser find` post URLs and the
    `instagram user` listing has no shared ID — see orchestrator.py's own comment. When the
    grid returns more links than the listing returns metadata rows, the extras get {}.)
  - 48 rows: caption present but clipped at <=100 chars (31 of them in the 96-100 band).
    `opencli instagram user` truncates its listing caption to exactly 100 characters.

ROOT CAUSE (verified, not assumed): `parse_caption()` — which reads the FULL caption out of
the rendered post page and is immune to both defects — was wired into orchestrator.py in
commit 8b493d1 on 2026-08-10 01:19. Every one of the 97 rows was fetched 2026-08-08 20:39 →
2026-08-09 15:49, i.e. ALL of them predate the fix. So the scraper code is already correct;
nothing re-scraped the existing rows afterwards. This is the project's documented
"verified that code ran, rather than that data arrived" failure mode, in the data.

Confirmed live before writing this (2026-08-11), on real posts:
  - truncated row DZHR_3_NcCr: stored 100 chars, parse_caption recovers 207.
  - null row C3kvKa5Nr6m: parse_caption recovers a real (short, emoji) caption.

This script therefore does NOT change scraper logic — it re-runs the already-fixed
extraction path over the stale rows. Idempotent and resumable: only writes when the
recovered caption is strictly longer than what's stored, so re-running is safe and a
failed/partial run can simply be re-run.

Run:  python backfill_captions.py [--limit N] [--dry-run]
Needs Chrome open + logged in, OPENCLI_PROFILE set. Do NOT run concurrently with Reddit.
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess

import psycopg2
import yaml

from instagram_comment_extract import parse_caption

# The post's OWN author: a username link immediately followed by a relative-age token
# ("2w", "3d"). Comment authors' links are never followed by one, so this isolates the
# author. Same structure already proven in discover_candidates.py.
_AUTHOR_LINK = re.compile(
    r"\[\s*\n*\s*[A-Za-z0-9_.\\]+\s*\n*\s*\]\(/([A-Za-z0-9_.]+)/\)\s*\n*\s*\d+[smhdwy]\b"
)

# Where author!=stored-username rows get recorded. NOT auto-corrected — see note in
# main(); re-attributing a post changes whose dataset it belongs to, which is a
# user-facing call, not a backfill's to make silently.
MISMATCH_PATH = os.path.join(os.path.dirname(__file__), "caption_author_mismatches.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill")

_OPENCLI = shutil.which("opencli")
if not _OPENCLI:
    raise RuntimeError("opencli not found on PATH")

SESSION = "capbackfill"


def load_env():
    env = dict(os.environ)
    path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k, v)
    return env


ENV = load_env()


def run_opencli(*args, timeout=90):
    env = dict(os.environ)
    if ENV.get("OPENCLI_PROFILE"):
        env["OPENCLI_PROFILE"] = ENV["OPENCLI_PROFILE"]
    r = subprocess.run(
        [_OPENCLI, *args], capture_output=True, text=True, timeout=timeout,
        env=env, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(f"opencli {' '.join(args)}: {r.stdout}{r.stderr}")
    return yaml.safe_load(r.stdout)


def fetch_caption(post_id: str, username: str) -> tuple[str | None, str | None]:
    """Open the real post page; return (caption, detected_author_or_None).

    ANCHORED on the username already stored on the row — deliberately, after a real
    self-inflicted incident on 2026-08-11. The first version of this function tried to
    auto-detect the post's author (first `[user](/user/)` link followed by a relative-age
    token) and key the caption parse on that. It corrupted ~33 rows: an Instagram post
    page also renders SUGGESTED/related posts, so the first such match is frequently some
    *other* post's author, and parse_caption then returned that suggested post's caption.
    Symptoms that exposed it: 94 rows carrying only 61 distinct captions, the same text
    repeated across unrelated post_ids, and one post_id reporting two different "authors"
    on two runs (suggestions are re-rolled per load).

    Anchoring on the known username cannot drift that way: if this post genuinely isn't
    that creator's, the parse simply returns None and the row honestly stays NULL — a
    known gap, never a confidently-wrong caption belonging to a stranger.

    The author-mismatch question is real and worth pursuing for P0.2 edges, but it needs
    a main-post-scoped extraction (e.g. `extract --selector` on the primary <article>),
    NOT first-match-in-document. Left out here rather than shipped broken twice.
    """
    url = f"https://www.instagram.com/p/{post_id}/"
    run_opencli("browser", SESSION, "open", url)
    run_opencli("browser", SESSION, "wait", "time", "2")
    extracted = run_opencli("browser", SESSION, "extract")
    if not isinstance(extracted, dict):
        raise RuntimeError("extract returned no envelope")
    # Verify the page actually IS the post we asked for. Skipping this check is what let
    # the corruption above go unnoticed for a whole 97-row run.
    got_url = extracted.get("url") or ""
    if post_id not in got_url:
        raise RuntimeError(f"page mismatch: asked {post_id}, got {got_url}")
    md = extracted.get("content") or ""
    return parse_caption(md, username), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = all rows")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        "select post_id, username, coalesce(length(caption), -1) "
        "from instagram_posts order by coalesce(length(caption), -1) asc"
    )
    rows = cur.fetchall()
    if args.limit:
        rows = rows[: args.limit]
    log.info("backfilling %d instagram_posts rows", len(rows))

    improved = same = failed = 0
    mismatches: list[dict] = []
    for i, (post_id, username, old_len) in enumerate(rows, 1):
        try:
            caption, actual = fetch_caption(post_id, username)
        except RuntimeError as e:
            failed += 1
            log.info("[%d/%d] %s FAILED: %s", i, len(rows), post_id, str(e)[:90])
            continue
        if actual and actual != username:
            mismatches.append({"post_id": post_id, "stored_username": username,
                                "actual_author": actual})
            log.info("[%d/%d] %s AUTHOR MISMATCH stored=%s actual=%s",
                      i, len(rows), post_id, username, actual)
        new_len = len(caption) if caption else 0
        if new_len <= max(old_len, 0):
            same += 1
            log.info("[%d/%d] %s no gain (old=%d new=%d)", i, len(rows), post_id, old_len, new_len)
            continue
        if not args.dry_run:
            # Strictly-longer guard mirrors orchestrator's own upsert rule, so this can
            # never shorten a caption that some later run already improved.
            cur.execute(
                "update instagram_posts set caption=%s, fetched_at=now() "
                "where post_id=%s and length(coalesce(caption,'')) < %s",
                (caption, post_id, new_len),
            )
            conn.commit()
        improved += 1
        log.info("[%d/%d] %s IMPROVED %d -> %d chars", i, len(rows), post_id, old_len, new_len)

    try:
        run_opencli("browser", SESSION, "close")
    except RuntimeError:
        pass
    conn.close()

    # Recorded, deliberately NOT auto-corrected. Re-attributing a post (changing
    # username/creator_id) removes it from one creator's dataset and adds it to
    # another's — a user-facing data call, not something a caption backfill should do
    # silently. These rows are also direct P0.2 input: a post by `sixers` or
    # `ljfamfoundation` sitting on LeBron's grid IS the team/related-account
    # relationship creator_related_accounts wants.
    if mismatches:
        with open(MISMATCH_PATH, "w", encoding="utf-8") as f:
            json.dump(mismatches, f, indent=2)
        log.info("recorded %d author mismatches -> %s", len(mismatches), MISMATCH_PATH)

    log.info("DONE improved=%d unchanged=%d failed=%d mismatched_author=%d",
              improved, same, failed, len(mismatches))


if __name__ == "__main__":
    main()
