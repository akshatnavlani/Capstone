"""Ingestion orchestrator — Track A (Data/Infra).

Design + rationale: see ORCHESTRATION.md at repo root.
Schema this writes into: see SCHEMA.md at repo root.

Weeks 5-6 status: real, working fetch/upsert logic for YouTube (official Data API) and
Instagram (OpenCLI + the browser-automation comment extractor). Reddit fetch/upsert is
real but deliberately lean (see RedditWorker) since Reddit's role here is community
context, not the primary sponsorship-disclosure source PROJECT_PLAN.md cares about for
GAIL training data — that's YouTube/Instagram creator-published content.

Brand-name leads (scripts/ingestion/brand_extraction.py) are extracted from every
caption/title/description fetched and upserted into `brands`, linking via `brand_id`.
This is a lead-generation pass, not the real `is_sponsored` classifier (Track C's job,
still not built as of this writing) — see SCHEMA.md "Brand data" for that boundary.

Run: python scripts/ingestion/orchestrator.py --platform youtube --handles athleanx
Requires DATABASE_URL (+ YOUTUBE_API_KEY / OPENCLI_PROFILE as relevant) in .env.
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

import yaml

from brand_extraction import extract_brand_mentions
from instagram_comment_extract import parse_comments

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("orchestrator")


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    env = dict(os.environ)
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env.setdefault(k, v)
    return env


ENV = load_env()


@dataclass
class Creator:
    creator_id: str | None
    name: str
    category: str
    youtube_handle: str | None = None
    instagram_handle: str | None = None
    reddit_handles: list[str] = field(default_factory=list)


class RateLimiter:
    """Enforces a minimum interval between calls for one platform's single session.

    Real measured OpenCLI-via-Chrome latency is 5.1-8.6s/call (avg 6.68s) — see
    DATA_COLLECTION_STATUS.md Section 4b. min_interval is the GAP added on top of a
    call's own latency, not a replacement for it — real sustained rate ends up close
    to ~370 calls/hour at min_interval=3.
    """

    def __init__(self, min_interval_seconds: float = 3.0):
        self.min_interval = min_interval_seconds
        self._last_call = 0.0

    def wait(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


_OPENCLI_BIN = shutil.which("opencli")
if not _OPENCLI_BIN:
    raise RuntimeError("opencli not found on PATH")


def run_opencli(*args: str, timeout: int = 30) -> dict | list:
    # subprocess.run's default (no shell=True) uses CreateProcess directly on
    # Windows, which can't resolve a bare "opencli" to the npm-installed
    # opencli.cmd shim (no extension = no match) — shutil.which() does the same
    # PATHEXT-aware resolution a shell would, so this works without shell=True.
    env = dict(os.environ)
    if ENV.get("OPENCLI_PROFILE"):
        env["OPENCLI_PROFILE"] = ENV["OPENCLI_PROFILE"]
    # subprocess.run(text=True) defaults to the OS locale encoding (cp1252 on this
    # Windows machine) to decode child stdout — crashes on real comment text with
    # emoji (confirmed: 'charmap' codec can't decode byte 0x8d). Force UTF-8.
    result = subprocess.run(
        [_OPENCLI_BIN, *args], capture_output=True, text=True, timeout=timeout, env=env,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"opencli {' '.join(args)} failed: {result.stdout}{result.stderr}")
    return yaml.safe_load(result.stdout)


def youtube_api_get(endpoint: str, **params) -> dict:
    params["key"] = ENV["YOUTUBE_API_KEY"]
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.loads(resp.read())


def upsert_brand(cur, name: str) -> str:
    cur.execute(
        """
        insert into brands (name) values (%s)
        on conflict (name) do update set updated_at = now()
        returning brand_id
        """,
        (name,),
    )
    return cur.fetchone()[0]


def brand_id_for_text(cur, text: str | None) -> str | None:
    if not text:
        return None
    mentions = extract_brand_mentions(text)
    if not mentions:
        return None
    # explicit-confidence mentions first; take the first candidate found
    best = next((m for m in mentions if m.confidence == "explicit"), mentions[0])
    brand_id = upsert_brand(cur, best.candidate_name)
    log.info("brand lead: %r -> brand_id=%s (confidence=%s)", best.candidate_name, brand_id, best.confidence)
    return brand_id


class PlatformWorker:
    platform_name = "base"

    def __init__(self, rate_limiter: RateLimiter, dry_run: bool = False):
        self.rate_limiter = rate_limiter
        self.dry_run = dry_run

    def run_batch(self, creators: list[Creator], conn) -> None:
        for creator in creators:
            handle = self._handle_for(creator)
            if not handle:
                continue
            try:
                self.process_creator(creator, handle, conn)
            except Exception:
                log.exception("Failed for %s (%s) on %s — skipping, continuing batch",
                               creator.name, handle, self.platform_name)

    def _handle_for(self, creator: Creator) -> str | None:
        raise NotImplementedError

    def process_creator(self, creator: Creator, handle: str, conn) -> None:
        raise NotImplementedError


class YouTubeWorker(PlatformWorker):
    platform_name = "youtube"

    def _handle_for(self, creator: Creator) -> str | None:
        return creator.youtube_handle

    def process_creator(self, creator: Creator, handle: str, conn) -> None:
        channel_resp = youtube_api_get(
            "channels", forHandle=handle.lstrip("@"),
            part="snippet,statistics,contentDetails",
        )
        items = channel_resp.get("items", [])
        if not items:
            log.warning("No YouTube channel found for handle %s", handle)
            return
        ch = items[0]
        channel_id = ch["id"]
        snippet, stats = ch["snippet"], ch["statistics"]
        uploads_playlist = ch["contentDetails"]["relatedPlaylists"]["uploads"]

        with conn.cursor() as cur:
            cur.execute(
                """
                insert into youtube_channels
                    (channel_id, creator_id, channel_handle, title, description,
                     subscriber_count, view_count, video_count, country)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (channel_id) do update set
                    subscriber_count=excluded.subscriber_count,
                    view_count=excluded.view_count,
                    video_count=excluded.video_count,
                    fetched_at=now(), updated_at=now()
                """,
                (channel_id, creator.creator_id, handle, snippet.get("title"),
                 snippet.get("description"), stats.get("subscriberCount"),
                 stats.get("viewCount"), stats.get("videoCount"), snippet.get("country")),
            )
        conn.commit()

        self.rate_limiter.wait()
        playlist_resp = youtube_api_get(
            "playlistItems", playlistId=uploads_playlist, part="contentDetails", maxResults=10,
        )
        video_ids = [i["contentDetails"]["videoId"] for i in playlist_resp.get("items", [])]
        if not video_ids:
            return

        self.rate_limiter.wait()
        videos_resp = youtube_api_get(
            "videos", id=",".join(video_ids), part="snippet,statistics,contentDetails",
        )
        for v in videos_resp.get("items", []):
            vs, vstats = v["snippet"], v["statistics"]
            with conn.cursor() as cur:
                brand_id = brand_id_for_text(cur, f"{vs.get('title', '')} {vs.get('description', '')}")
                cur.execute(
                    """
                    insert into youtube_videos
                        (video_id, channel_id, creator_id, title, description, published_at,
                         thumbnail_url, view_count, like_count, comment_count, tags, brand_id)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict (video_id) do update set
                        view_count=excluded.view_count, like_count=excluded.like_count,
                        comment_count=excluded.comment_count, brand_id=coalesce(excluded.brand_id, youtube_videos.brand_id),
                        fetched_at=now()
                    """,
                    (v["id"], channel_id, creator.creator_id, vs.get("title"), vs.get("description"),
                     vs.get("publishedAt"), vs.get("thumbnails", {}).get("high", {}).get("url"),
                     vstats.get("viewCount"), vstats.get("likeCount"), vstats.get("commentCount"),
                     vs.get("tags"), brand_id),
                )
            conn.commit()

            self.rate_limiter.wait()
            try:
                comments_resp = youtube_api_get(
                    "commentThreads", videoId=v["id"], part="snippet", maxResults=20, order="relevance",
                )
            except Exception as e:
                log.info("Comments disabled or unavailable for video %s: %s", v["id"], e)
                continue
            with conn.cursor() as cur:
                for item in comments_resp.get("items", []):
                    c = item["snippet"]["topLevelComment"]["snippet"]
                    cur.execute(
                        """
                        insert into youtube_comments
                            (comment_id, video_id, author_handle, text, published_at, like_count)
                        values (%s,%s,%s,%s,%s,%s)
                        on conflict (comment_id) do update set like_count=excluded.like_count
                        """,
                        (item["id"], v["id"], c.get("authorDisplayName"), c.get("textDisplay"),
                         c.get("publishedAt"), c.get("likeCount")),
                    )
            conn.commit()
        log.info("YouTube: %s -> %d videos", handle, len(videos_resp.get("items", [])))


class InstagramWorker(PlatformWorker):
    platform_name = "instagram"

    def _handle_for(self, creator: Creator) -> str | None:
        return creator.instagram_handle

    def process_creator(self, creator: Creator, handle: str, conn) -> None:
        self.rate_limiter.wait()
        profile_resp = run_opencli("instagram", "profile", handle, "-f", "yaml")
        # `instagram profile` returns a 1-item list of a flat dict (bio/followers/...
        # keys directly) — NOT field/value rows like `reddit subreddit-info` uses.
        # Confirmed wrong on the first real run (KeyError: 'field') — different
        # OpenCLI commands use different YAML shapes, don't assume one fits all.
        prof = profile_resp[0] if isinstance(profile_resp, list) else profile_resp
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into instagram_profiles
                    (username, creator_id, full_name, bio, follower_count, following_count,
                     post_count, is_verified)
                values (%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (username) do update set
                    follower_count=excluded.follower_count, following_count=excluded.following_count,
                    post_count=excluded.post_count, fetched_at=now(), updated_at=now()
                """,
                (handle, creator.creator_id, prof.get("name"), prof.get("bio"),
                 prof.get("followers"), prof.get("following"), prof.get("posts"),
                 str(prof.get("verified")).lower() == "yes"),
            )
        conn.commit()

        self.rate_limiter.wait()
        session = f"orc_{handle}"
        run_opencli("browser", session, "open", f"https://www.instagram.com/{handle}/")
        run_opencli("browser", session, "wait", "time", "2")
        # The post grid is lazy-loaded and load timing is genuinely inconsistent —
        # observed anywhere from 0 to 2+ scrolls needed for the same account across
        # different runs (not just cold-vs-warm cache; re-ran kingjames twice in a
        # row and got different results). Padding the retry budget rather than
        # assuming a fixed scroll count is reliable.
        found = None
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                found = run_opencli("browser", session, "find", "--css",
                                     'a[href*="/reel/"], a[href*="/p/"]', "--limit", "8")
                break
            except RuntimeError:
                if attempt == max_attempts - 1:
                    raise
                run_opencli("browser", session, "scroll", "down")
                run_opencli("browser", session, "wait", "time", "3")
        post_paths = list(dict.fromkeys(e["attrs"]["href"] for e in found.get("entries", [])))

        for path in post_paths[:5]:
            post_url = f"https://www.instagram.com{path}"
            post_id = path.strip("/").split("/")[-1]
            self.rate_limiter.wait()
            run_opencli("browser", session, "open", post_url)
            run_opencli("browser", session, "wait", "time", "2")
            extracted = run_opencli("browser", session, "extract")
            markdown = extracted["content"] if isinstance(extracted, dict) else str(extracted)

            with conn.cursor() as cur:
                brand_id = brand_id_for_text(cur, markdown[:2000])  # caption is near the top
                cur.execute(
                    """
                    insert into instagram_posts (post_id, username, creator_id, brand_id)
                    values (%s,%s,%s,%s)
                    on conflict (post_id) do update set fetched_at=now(), brand_id=coalesce(excluded.brand_id, instagram_posts.brand_id)
                    """,
                    (post_id, handle, creator.creator_id, brand_id),
                )
                comments = parse_comments(markdown)
                for c in comments:
                    cur.execute(
                        """
                        insert into instagram_profiles (username) values (%s)
                        on conflict (username) do nothing
                        """,
                        (c.author_username,),
                    )
                    cur.execute(
                        """
                        insert into instagram_comments (comment_id, post_id, author_username, text, like_count)
                        values (%s,%s,%s,%s,%s)
                        on conflict (comment_id) do update set like_count=excluded.like_count
                        """,
                        (c.comment_id, post_id, c.author_username, c.text, c.like_count),
                    )
            conn.commit()
            log.info("Instagram: %s post %s -> %d comments", handle, post_id, len(comments))
        run_opencli("browser", session, "close")


def enrich_reddit_profile(cur, username: str) -> None:
    """Full profile enrichment via `opencli reddit user` — real command, confirmed
    working (2026-08-10). Note: `-f json` crashed on this account's emoji fields
    ("⭐ Yes"); `-f yaml` handles it fine, matching the encoding lesson from the
    Instagram pipeline (subprocess text decoding needs UTF-8, not assumed-safe ASCII).
    Falls back to a bare username stub on any fetch error (private/suspended/deleted
    accounts, rate limits) rather than failing the whole post.
    """
    try:
        rows = run_opencli("reddit", "user", username, "-f", "yaml")
        prof = {r["field"]: r["value"] for r in rows} if isinstance(rows, list) else {}
        created = prof.get("Account Created")
        cur.execute(
            """
            insert into reddit_profiles (username, account_created_at, comment_karma, link_karma)
            values (%s, nullif(%s,'-')::timestamptz, %s, %s)
            on conflict (username) do update set
                account_created_at = coalesce(excluded.account_created_at, reddit_profiles.account_created_at),
                comment_karma = coalesce(excluded.comment_karma, reddit_profiles.comment_karma),
                link_karma = coalesce(excluded.link_karma, reddit_profiles.link_karma),
                fetched_at = now()
            """,
            (username, created,
             int(prof["Comment Karma"]) if prof.get("Comment Karma", "").lstrip("-").isdigit() else None,
             int(prof["Post Karma"]) if prof.get("Post Karma", "").lstrip("-").isdigit() else None),
        )
    except Exception:
        log.warning("Reddit profile enrichment failed for u/%s — falling back to stub", username)
        cur.execute(
            "insert into reddit_profiles (username) values (%s) on conflict (username) do nothing",
            (username,),
        )


class RedditWorker(PlatformWorker):
    """Deliberately leaner than YouTube/Instagram — Reddit is community context here,
    not the primary sponsorship-disclosure source (see module docstring). Unlike
    Instagram, Reddit's OpenCLI backend already covers comment reading natively
    (`reddit read`, bundled in the same call as the post) — no browser-automation
    workaround needed here."""

    platform_name = "reddit"

    def _handle_for(self, creator: Creator) -> str | None:
        return creator.reddit_handles[0] if creator.reddit_handles else None

    def process_creator(self, creator: Creator, handle: str, conn) -> None:
        # Note on "target creator" profile depth for Reddit: unlike YouTube/Instagram,
        # `creators.reddit_handles` is a list of SUBREDDITS (fan/team communities
        # ABOUT the creator — see SCHEMA.md), not the creator's own Reddit username in
        # most cases (most athletes/influencers don't personally post on Reddit).
        # There is usually no personal account to profile-enrich for the target
        # itself. The closest meaningful analog with real bot-detection value: the
        # POST AUTHORS in the creator's subreddit(s) — a small, bounded set (<=5/run),
        # unlike comment authors (potentially 100+/run, correctly still stubs-only
        # for rate-limit/cost reasons per instruction).
        self.rate_limiter.wait()
        posts = run_opencli("reddit", "subreddit", handle, "-f", "yaml")
        if not isinstance(posts, list):
            return
        for post in posts[:5]:
            post_id = post.get("id")
            if not post_id:
                continue
            with conn.cursor() as cur:
                if post.get("author"):
                    self.rate_limiter.wait()
                    enrich_reddit_profile(cur, post["author"])
                brand_id = brand_id_for_text(cur, f"{post.get('title', '')} {post.get('selftext', '')}")
                cur.execute(
                    """
                    insert into reddit_posts
                        (post_id, subreddit, creator_id, author_username, title, body,
                         posted_at, score, num_comments, brand_id)
                    values (%s,%s,%s,%s,%s,%s,to_timestamp(%s),%s,%s,%s)
                    on conflict (post_id) do update set score=excluded.score, num_comments=excluded.num_comments,
                        brand_id=coalesce(excluded.brand_id, reddit_posts.brand_id), fetched_at=now()
                    """,
                    (post_id, handle, creator.creator_id, post.get("author"), post.get("title"),
                     post.get("selftext"), post.get("created_utc"), post.get("upvotes"),
                     post.get("comments"), brand_id),
                )
            conn.commit()

            self.rate_limiter.wait()
            self._fetch_comments(post_id, conn)
        log.info("Reddit: r/%s -> %d posts", handle, len(posts[:5]))

    def _fetch_comments(self, post_id: str, conn) -> None:
        rows = run_opencli("reddit", "read", post_id, "-f", "yaml")
        if not isinstance(rows, list):
            return
        n = 0
        with conn.cursor() as cur:
            for row in rows:
                # type=="POST" is the post itself (already captured); rows with no
                # author are truncation placeholders ("[+N more replies]"), not real
                # comments — Reddit's `read` output has NO comment-id field at all
                # (checked the raw JSON directly), so a content hash stands in as a
                # stable synthetic id, idempotent across reruns of the same comment.
                if row.get("type") == "POST" or not row.get("author"):
                    continue
                comment_id = hashlib.sha1(
                    f"{post_id}:{row['author']}:{row.get('text', '')}".encode("utf-8")
                ).hexdigest()[:24]
                score = row.get("score")
                score = score if isinstance(score, int) else None
                cur.execute(
                    "insert into reddit_profiles (username) values (%s) on conflict (username) do nothing",
                    (row["author"],),
                )
                cur.execute(
                    """
                    insert into reddit_comments (comment_id, post_id, author_username, body, score)
                    values (%s,%s,%s,%s,%s)
                    on conflict (comment_id) do update set score=excluded.score
                    """,
                    (comment_id, post_id, row["author"], row.get("text"), score),
                )
                n += 1
        conn.commit()
        log.info("Reddit: post %s -> %d comments", post_id, n)


WORKERS = {
    "youtube": YouTubeWorker,
    "instagram": InstagramWorker,
    "reddit": RedditWorker,
}


def get_connection():
    import psycopg2
    database_url = ENV.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set — copy .env.example to .env and fill it in")
    return psycopg2.connect(database_url)


def get_or_create_creator(conn, name: str, category: str, **handles) -> Creator:
    """Idempotent across ALL provided handles (youtube_handle, instagram_handle,
    reddit_handles), not just whichever one happened to be passed first.

    Real bug fixed here (2026-08-10, found because the new per-platform sub-agent
    architecture means YouTube/Instagram/Reddit workers each call this independently
    for the same real person): the previous version only ever wrote ONE handle column
    depending on which `if yt / elif ig` branch ran — passing both `youtube_handle`
    and `instagram_handle` together silently dropped `instagram_handle` entirely, and
    a creator scraped separately by each platform's worker got 3 unlinked rows.

    Now: look up an existing row by ANY provided handle first (so a platform worker
    reusing a handle from a pre-seeded multi-platform target list — see
    `seed_creators()` — finds the same row every other platform's worker uses), then
    MERGE any newly-provided handles into that row instead of dropping them. Only
    inserts a new row when no existing row matches any provided handle.
    """
    yt = handles.get("youtube_handle")
    ig = handles.get("instagram_handle")
    reddit_handles = handles.get("reddit_handles") or []

    with conn.cursor() as cur:
        row = None
        if yt:
            cur.execute("select creator_id from creators where youtube_handle = %s", (yt,))
            row = cur.fetchone()
        if row is None and ig:
            cur.execute("select creator_id from creators where instagram_handle = %s", (ig,))
            row = cur.fetchone()
        # Deliberately NOT matching on reddit_handles overlap — real bug found running
        # the actual target-list seed (2026-08-10): "badminton" is a generic
        # sport-wide subreddit both PV Sindhu and Saina Nehwal are (correctly)
        # associated with, and the `&&` overlap check merged Saina Nehwal into PV
        # Sindhu's row because they share that one community subreddit. Unlike
        # youtube_handle/instagram_handle (a unique account per real person),
        # reddit_handles is a list of communities ABOUT a creator, which multiple
        # different real people can legitimately share — never a valid identity key.

        if row is not None:
            creator_id = row[0]
            # Also refresh name/category, but ONLY when the existing row's category
            # is the 'other' placeholder ad-hoc `--handles` runs use (e.g. a prior
            # `--handles kingjames` test run named the row "kingjames" literally).
            # Real bug found seeding the curated target list (2026-08-10): merging
            # correctly combined LeBron James's handles onto the existing row, but
            # left name/category stale ("kingjames"/"other") since only handle
            # columns were updated — a curated seed's name/category is authoritative
            # and should win over an ad-hoc placeholder, but should NOT silently
            # overwrite a name a previous *curated* seed already set correctly.
            cur.execute(
                """
                update creators set
                    name = case when category = 'other' then %s else name end,
                    category = case when category = 'other' then %s else category end,
                    youtube_handle = coalesce(youtube_handle, %s),
                    instagram_handle = coalesce(instagram_handle, %s),
                    reddit_handles = (select array(select distinct unnest(reddit_handles || %s))),
                    updated_at = now()
                where creator_id = %s
                """,
                (name, category, yt, ig, reddit_handles, creator_id),
            )
        else:
            # No row matched any handle. Best-effort name-collision check before
            # creating — per instruction, flag for manual review rather than
            # auto-merge: a same-name row with different handles MIGHT be the same
            # real person found via another platform, or might just be a namesake.
            # Auto-merging a wrong guess would corrupt two different people's data
            # together, which is worse than a duplicate row waiting for review.
            cur.execute(
                "select creator_id, youtube_handle, instagram_handle, reddit_handles from creators where name = %s",
                (name,),
            )
            existing = cur.fetchall()
            if existing:
                log.warning(
                    "Possible duplicate creator by name %r — NOT auto-merged, flagging for "
                    "manual review. New handles: yt=%s ig=%s reddit=%s. Existing row(s): %s",
                    name, yt, ig, reddit_handles, existing,
                )
            cur.execute(
                """
                insert into creators (name, category, youtube_handle, instagram_handle, reddit_handles)
                values (%s,%s,%s,%s,%s)
                returning creator_id
                """,
                (name, category, yt, ig, reddit_handles),
            )
            creator_id = cur.fetchone()[0]
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            "select name, category, youtube_handle, instagram_handle, reddit_handles from creators where creator_id = %s",
            (creator_id,),
        )
        r_name, r_category, r_yt, r_ig, r_reddit = cur.fetchone()
    return Creator(creator_id=str(creator_id), name=r_name, category=r_category,
                    youtube_handle=r_yt, instagram_handle=r_ig, reddit_handles=r_reddit or [])


def seed_creators(conn, target_list: list[dict]) -> dict[str, Creator]:
    """Pre-populate `creators` with full cross-platform handle bundles BEFORE
    dispatching per-platform sub-agents — this is the primary defense against the
    3-unlinked-rows problem, not just the merge logic in get_or_create_creator above.
    Each entry: {"name", "category", "youtube_handle"?, "instagram_handle"?,
    "reddit_handles"?}. Returns {name: Creator} for the caller to inspect.
    """
    result = {}
    for entry in target_list:
        c = get_or_create_creator(
            conn, entry["name"], entry["category"],
            youtube_handle=entry.get("youtube_handle"),
            instagram_handle=entry.get("instagram_handle"),
            reddit_handles=entry.get("reddit_handles", []),
        )
        result[entry["name"]] = c
        log.info("Seeded creator %s -> %s (yt=%s ig=%s reddit=%s)",
                  entry["name"], c.creator_id, c.youtube_handle, c.instagram_handle, c.reddit_handles)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", help="Path to a curated target-list JSON to seed into `creators` "
                                        "(full cross-platform handle bundles) and exit. Run this ONCE "
                                        "before dispatching per-platform sub-agents.")
    parser.add_argument("--platform", choices=WORKERS.keys())
    parser.add_argument("--handles", nargs="+",
                         help="Ad-hoc handles to fetch for --platform (uses handle as name if not "
                              "pre-seeded). Prefer --target-list once a curated list exists, so "
                              "cross-platform handles for the same person are looked up, not guessed.")
    parser.add_argument("--target-list", help="Path to the curated target-list JSON (same file used "
                                               "with --seed) — looks creators up by THIS platform's "
                                               "handle, which should already exist from a prior --seed "
                                               "run, so all platform sub-agents share one creator_id "
                                               "per real person instead of each creating their own.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = None if args.dry_run else get_connection()

    if args.seed:
        with open(args.seed, encoding="utf-8") as f:
            target_list = json.load(f)
        seed_creators(conn, target_list)
        return

    if not args.platform:
        parser.error("--platform is required unless using --seed")

    creators = []
    if not args.dry_run and args.target_list:
        with open(args.target_list, encoding="utf-8") as f:
            target_list = json.load(f)
        handle_field = "reddit_handles" if args.platform == "reddit" else f"{args.platform}_handle"
        for entry in target_list:
            value = entry.get(handle_field)
            if not value:
                continue
            creators.append(get_or_create_creator(
                conn, entry["name"], entry["category"],
                youtube_handle=entry.get("youtube_handle"),
                instagram_handle=entry.get("instagram_handle"),
                reddit_handles=entry.get("reddit_handles", []),
            ))
    elif not args.dry_run and args.handles:
        for h in args.handles:
            kwargs = {f"{args.platform}_handle" if args.platform != "reddit" else "reddit_handles":
                      h if args.platform != "reddit" else [h]}
            creators.append(get_or_create_creator(conn, h, "other", **kwargs))

    worker = WORKERS[args.platform](RateLimiter(), dry_run=args.dry_run)
    worker.run_batch(creators, conn)


if __name__ == "__main__":
    main()
