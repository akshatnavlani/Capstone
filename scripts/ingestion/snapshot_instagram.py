"""Record how recent Instagram posts grow (likes and comments over time) for a SMALL set of creators.

    python snapshot_instagram.py --handles fitadesss itsprashantdesai
    python snapshot_instagram.py --handles fitadesss --max-age-days 5 --daily-cap 80
    python snapshot_instagram.py --handles fitadesss --dry-run     # prints the plan, opens nothing

Each run, for every handle: open the profile page (followers, post count, and the first screen of post links),
then open ONLY the posts younger than --max-age-days (the post's age comes from the exact time hidden in its
shortcode, so older posts cost no page load). Every page read appends one `post_snapshots` row, so a post's first
24 hours become a curve. New young posts are inserted with the facts the page shows (comments are collected by the
full collector, orchestrator.py).

REQUEST BUDGET. Instagram throttles automation (in Aug 2026 around 200 post pages in a few hours tripped it). This
script therefore: waits GAP_SECONDS between page loads, stops the whole run at the first sign of a block or after
two failed loads in a row, and refuses to start once --daily-cap page loads were made today (counted from the
snapshot rows it wrote). Start with 5 creators and 1-2 runs a day. It runs on a machine with the signed-in Chrome
and OpenCLI (not on GitHub).

Reads only: no likes, follows or comments.
"""

import argparse
import re
from datetime import datetime, timedelta, timezone

from ig_time import decode
from orchestrator import (_OG_JS, _POST_JS, _PROFILE_JS, Creator, RateLimiter, brand_id_for_text, get_connection, log,
                          og_approx_counts, parse_og_description, parse_post_extras, parse_profile_page,
                          record_post_snapshot, run_opencli, save_instagram_profile)

GAP_SECONDS = 8.0
MAX_CONSECUTIVE_FAILURES = 2
_LINK_JS = ('JSON.stringify([...document.querySelectorAll(\'a[href*="/p/"], a[href*="/reel/"]\')]'
            '.map(a => a.getAttribute("href")))')
_CAPTION_RE = re.compile(r':\s*"(.*)"\.?\s*$', re.S)


def shortcode_of(href: str) -> str | None:
    """'/fitadesss/reel/DeXH-wjTvZ5/' -> 'DeXH-wjTvZ5'."""
    m = re.search(r"/(?:p|reel)/([A-Za-z0-9_-]+)", href or "")
    return m.group(1) if m else None


def own_links(hrefs, handle: str) -> list[str]:
    """Post links on the creator's own grid, in page order, without duplicates (tagged/other accounts' posts are dropped)."""
    out, seen = [], set()
    for h in hrefs or []:
        h = str(h)
        code = shortcode_of(h)
        first = h.strip("/").split("/")[0].lower() if h.strip("/") else ""
        if code and code not in seen and first in (handle.lower(), "p", "reel"):
            seen.add(code)
            out.append(h)
    return out


def young_posts(hrefs, now: datetime, max_age_days: float) -> list[tuple[str, str, datetime]]:
    """[(href, shortcode, posted_at)] for links whose decoded time is within max_age_days (newest first)."""
    found = []
    for h in hrefs:
        code = shortcode_of(h)
        when = decode(code) if code else None
        if when and now - when <= timedelta(days=max_age_days):
            found.append((h, code, when))
    return sorted(found, key=lambda x: x[2], reverse=True)


def caption_from_og(og: str | None) -> str | None:
    """The caption part of '454 likes, 8 comments - user on October 11, 2026: "caption".'"""
    m = _CAPTION_RE.search(og or "")
    return m.group(1).strip() if m else None


def looks_blocked(text: str) -> bool:
    low = (text or "").lower()
    return "429" in low or "rate limit" in low or "chromewebdata" in low or "try again later" in low


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--handles", nargs="+", required=True, help="Instagram handles of creators already in `creators`")
    ap.add_argument("--max-age-days", type=float, default=7.0)
    ap.add_argument("--daily-cap", type=int, default=100, help="max page loads per day across all runs")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""select count(*) from post_snapshots where platform='instagram'
                       and fetched_at >= date_trunc('day', now() at time zone 'UTC') at time zone 'UTC'""")
        done_today = cur.fetchone()[0]
    budget = args.daily_cap - done_today
    log.info("%d handle(s); %d snapshot rows written today; budget left about %d page loads", len(args.handles), done_today, budget)
    if args.dry_run:
        log.info("[DRY RUN] would open each profile page, then each post younger than %.1f days; nothing was opened", args.max_age_days)
        return
    if budget <= len(args.handles):
        log.warning("daily cap reached; not starting")
        return

    limiter, loads, fails = RateLimiter(GAP_SECONDS), 0, 0
    for handle in args.handles:
        if loads >= budget:
            log.warning("budget used up after %d page loads; stopping", loads)
            break
        with conn.cursor() as cur:
            cur.execute("select creator_id, name, category from creators where lower(instagram_handle)=lower(%s) limit 1", (handle,))
            row = cur.fetchone()
        if not row:
            log.warning("%s is not a creator's Instagram handle in `creators`; skipped", handle)
            continue
        creator = Creator(creator_id=row[0], name=row[1], category=row[2], instagram_handle=handle)
        session = f"snap_{handle}"
        try:
            limiter.wait(); loads += 1
            run_opencli("browser", session, "open", f"https://www.instagram.com/{handle}/")
            run_opencli("browser", session, "wait", "time", "3")
            prof = parse_profile_page(run_opencli("browser", session, "eval", _PROFILE_JS))
            if prof:
                save_instagram_profile(conn, creator, handle, prof)
            hrefs = own_links(run_opencli("browser", session, "eval", _LINK_JS), handle)
            young = young_posts(hrefs, datetime.now(timezone.utc), args.max_age_days)
            log.info("%s: %s followers, %d post links on screen, %d younger than %.1f days",
                     handle, prof and prof["followers"], len(hrefs), len(young), args.max_age_days)
            fails = 0
            for href, code, when in young:
                if loads >= budget:
                    break
                limiter.wait(); loads += 1
                run_opencli("browser", session, "open", f"https://www.instagram.com{href}")
                run_opencli("browser", session, "wait", "time", "3")
                raw_og = run_opencli("browser", session, "eval", _OG_JS)
                og_text = raw_og if isinstance(raw_og, str) else ""
                if looks_blocked(og_text):
                    raise RuntimeError("block suspected: " + og_text[:80])
                og = parse_og_description(og_text)
                extras = parse_post_extras(run_opencli("browser", session, "eval", _POST_JS))
                a_likes, a_comments = og_approx_counts(og_text)
                likes = og["likes"] if og["likes"] is not None else a_likes
                comments = og["comments"] if og["comments"] is not None else a_comments
                caption = caption_from_og(og_text)
                with conn.cursor() as cur:
                    brand_id = brand_id_for_text(cur, caption)
                    cur.execute(
                        """insert into instagram_posts (post_id, username, creator_id, caption, media_type, like_count, comment_count,
                                                       posted_at, brand_id, thumbnail_url, has_paid_partnership_label)
                           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           on conflict (post_id) do update set
                               like_count=coalesce(%s, instagram_posts.like_count),
                               comment_count=coalesce(%s, instagram_posts.comment_count),
                               thumbnail_url=coalesce(excluded.thumbnail_url, instagram_posts.thumbnail_url),
                               has_paid_partnership_label=coalesce(excluded.has_paid_partnership_label, instagram_posts.has_paid_partnership_label),
                               fetched_at=now()""",
                        (code, handle, creator.creator_id, caption, "video" if "/reel/" in href else None,
                         og["likes"], og["comments"], when, brand_id, extras["image"], extras["paid"],
                         og["likes"], og["comments"]))
                    record_post_snapshot(cur, "instagram", code, creator.creator_id, None, likes, comments)
                conn.commit()
                log.info("  %s: %s likes, %s comments (age %.1f h)", code, likes, comments,
                         (datetime.now(timezone.utc) - when).total_seconds() / 3600)
        except RuntimeError as e:
            fails += 1
            log.error("%s: %s", handle, str(e)[:200].replace("\n", " "))
            if looks_blocked(str(e)) or fails >= MAX_CONSECUTIVE_FAILURES:
                log.error("stopping the whole run (block suspected or %d failures in a row)", fails)
                break
        finally:
            try:
                run_opencli("browser", session, "close", timeout=20)
            except RuntimeError:
                pass
    log.info("done: %d page loads", loads)


if __name__ == "__main__":
    main()
