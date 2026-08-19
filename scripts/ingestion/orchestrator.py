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
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import yaml

from brand_extraction import extract_brand_mentions
from instagram_comment_extract import parse_caption, parse_comments

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("orchestrator")

# Per-creator post cap. Was hardcoded at 5 through Weeks 5-8, which was the real
# reason every creator sat at 10-29% of the 1,000-datapoint floor — NOT the
# session/throughput ceiling (real call volume never came close to it). Raised on
# explicit user sign-off 2026-08-10 to close the volume gap.
DEFAULT_POST_CAP = 40

# Recency window. PROJECT_PLAN.md/the original doc scoped "last 6 months" and stated
# the principle "the newer the data the better" — treated as a ROLLING window relative
# to today, not the literal Jan-Jun 2026 dates from the original doc (it's August now,
# so those fixed dates would already be going stale). Posts older than this are skipped
# rather than counted toward the cap, so raising the cap doesn't pad the dataset with
# stale content.
DEFAULT_RECENCY_DAYS = 183


def recency_cutoff(days: int = DEFAULT_RECENCY_DAYS) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


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
    # CREATOR-SPECIFIC subreddits (r/ViratKohli) — feed can be taken broadly.
    reddit_handles: list[str] = field(default_factory=list)
    # GENERAL/TOPIC subreddits (r/ipl, r/tennis) — must be SEARCHED for the creator's
    # name, never taken as a whole feed. See migration 20260810000000 for the measured
    # 0%-relevance evidence behind this split.
    reddit_topic_subs: list[str] = field(default_factory=list)


# Tokens that identify NOBODY on their own. A creator name built only from these (e.g.
# "Fitness Standards Council", "Indian Super League") cannot be matched token-wise without
# dragging in unrelated posts -- see mentions_creator.
_GENERIC_NAME_TOKENS = {
    "fitness", "standards", "council", "club", "team", "sports", "sport", "academy",
    "institute", "foundation", "association", "official", "india", "indian", "super",
    "league", "premier", "cricket", "football", "soccer", "national", "series", "world",
    "champions", "championship", "united", "city", "state", "school", "centre", "center",
    "group", "media", "network", "channel", "studio", "productions", "entertainment",
    "singer", "coach", "trainer", "vlogs", "views", "fan", "fans",
}


def mentions_creator(text: str, creator_name: str) -> bool:
    """Does this text plausibly refer to this creator?

    Deliberately lenient (any distinctive name token, not the full name) — real posts
    say "Kohli", "Sindhu", "CarryMinati" far more often than the full formal name.
    Short tokens are dropped so initials/particles ("MC", "PV") don't match everything.

    ⚠️ GENERIC TOKENS ARE EXCLUDED (added 2026-08-18). Leniency is right for a distinctive
    surname and catastrophic for a generic organisation name. Real damage this caused: the
    creator "Fitness Standards Council" (a name harvested from a YouTube channel title)
    matched 11 r/india posts on the bare token "standards"/"council"/"fitness" — including
    "Democracy is a true Kaliyug construct" and "Bell jar". That is the same false-positive
    class as the 88% Reddit purge, resurfacing because real-name backfill introduced
    multi-word generic names that did not exist in the curated set.

    A name made ENTIRELY of generic tokens cannot be matched token-wise at all; it requires
    the full phrase, which is the only signal that actually identifies it.
    """
    hay = (text or "").lower()
    tokens = [t.lower().strip(".") for t in creator_name.split() if len(t) > 3]
    distinctive = [t for t in tokens if t not in _GENERIC_NAME_TOKENS]
    if distinctive:
        return any(t in hay for t in distinctive)
    # Every token is generic -> demand the whole name as a phrase.
    full = " ".join(creator_name.lower().split())
    return bool(full) and full in hay


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


_OPENCLI_STATS = {"retried": 0, "recovered": 0, "exhausted": 0}

# Adapter calls fail transiently often enough to matter -- measured ~4 of 6 succeeding in one
# round, 9 of 9 in another. Two extra attempts with a short backoff cost nothing when the first
# succeeds and recover the whole creator when it doesn't.
_OPENCLI_TRIES = 3
_OPENCLI_BACKOFF = [5, 15]

# og:description parsing (2026-08-19). The post permalink page carries
#     "885 likes, 33 comments - nasimamirza on May 9, 2026: "caption...""
# in <meta property="og:description">. Unlike the profile listing, this is fetched from the
# post's OWN url, so whatever it says is BY CONSTRUCTION about the post_id we navigated to --
# it cannot be misattributed the way a positional match can.
#
# Counts here are abbreviated by Instagram ("1M likes" for a true 1,416,111), so they are used
# only when they carry no K/M suffix. Dates carry +/-1 day (viewer-local rendering); immaterial
# for straddle analysis but never present them as exact.
_OG_JS = ('JSON.stringify(document.querySelector('
          '\'meta[property="og:description"]\')?.content)')
_OG_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_OG_DATE_RE = re.compile(r"on\s+(" + "|".join(_OG_MONTHS) + r")\s+(\d{1,2}),\s*(\d{4})", re.I)
_OG_COUNT_RE = re.compile(r"([\d.,]+\s*[KM]?)\s+likes?,\s*([\d.,]+\s*[KM]?)\s+comments?", re.I)


def _og_exact_int(tok: str):
    """Only EXACT counts. An abbreviated '76K' is rounded by Instagram -- writing it would
    overwrite a real value with a wrong one, so it is discarded rather than approximated."""
    tok = tok.replace(",", "").strip()
    if not tok or tok[-1].upper() in ("K", "M"):
        return None
    try:
        return int(float(tok))
    except ValueError:
        return None


def parse_og_description(desc):
    """-> {'date': 'M/D/YYYY'|None, 'likes': int|None, 'comments': int|None}."""
    out = {"date": None, "likes": None, "comments": None}
    if not desc:
        return out
    m = _OG_DATE_RE.search(desc)
    if m:
        out["date"] = f"{_OG_MONTHS[m.group(1).lower()]}/{int(m.group(2))}/{m.group(3)}"
    c = _OG_COUNT_RE.search(desc)
    if c:
        out["likes"] = _og_exact_int(c.group(1))
        out["comments"] = _og_exact_int(c.group(2))
    return out


def _norm_caption(text):
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def own_post_paths(paths, handle):
    """Keep only grid links that belong to `handle`.

    Found live 2026-08-19 and it is NOT a subtlety: a profile grid mixes in posts owned by
    OTHER accounts (tagged/collab posts). On `mostlysane`, 4 of 12 grid links belonged to
    `netflix_in` and `exhibitmagazine`. The old selector took every `/p/` and `/reel/` link and
    wrote them all with `username=<handle>, creator_id=<this creator>` -- attributing another
    account's post, and its engagement counts, to this creator.

    It also GUARANTEED the positional metadata match was wrong: the listing returns only the
    creator's own posts by recency, while the grid interleaves foreign ones, so every pairing
    after the first foreign link was offset.

    Instagram serves both `/p/<id>/` (bare, always the profile owner's) and
    `/<username>/p/<id>/`. Only the second form can be foreign, so only it is checked.
    """
    keep = []
    for p in paths:
        parts = [x for x in p.split("/") if x]
        if len(parts) >= 3 and parts[1] in ("p", "reel"):
            if parts[0].lower() != handle.lower():
                continue                     # another account's post, not this creator's
        keep.append(p)
    return keep


def match_listing_meta(page_caption, listing):
    """Join a post's listing metadata by CAPTION CONTENT, not list position.

    Replaces `posts_meta[i]` (orchestrator.py, flagged 3 rounds running). The adapter's
    documented output columns are `index, caption, likes, comments, type, date` -- there is no
    url, shortcode or id to join on, verified against `instagram user --help` and real json
    output on 2026-08-19. So content is the only available key.

    Instagram pins up to 3 posts to the top of a grid; pinned posts lead `browser find` order
    but are NOT newest, while the listing is ordered by recency. On any creator that pins, the
    two lists are offset and positional matching writes post N's date onto post M -- silent
    cross-post contamination that nothing downstream can catch.

    The listing truncates captions to 100 raw chars while the page extract has the full text,
    so the comparison is a symmetric prefix over whichever is shorter. Returns
    (meta, status); an AMBIGUOUS or absent match returns None rather than a guess -- a missing
    date is recoverable, a confidently wrong one is not.
    """
    pk = _norm_caption(page_caption)
    if len(pk) < 12:
        return None, "page caption too short to identify"
    hits = []
    for m in listing:
        lk = _norm_caption(m.get("caption"))
        if len(lk) < 12:
            continue
        n = min(len(pk), len(lk), 60)
        if pk[:n] == lk[:n]:
            hits.append(m)
    if len(hits) == 1:
        return hits[0], "matched"
    if not hits:
        return None, "no listing match"
    return None, f"ambiguous ({len(hits)} listing entries share this caption prefix)"


_OPENCLI_STATS = {"retried": 0, "recovered": 0, "exhausted": 0}

# Adapter calls fail transiently often enough to matter -- measured ~4 of 6 succeeding in one
# round, 9 of 9 in another. Two extra attempts with a short backoff cost nothing when the first
# succeeds and recover the whole creator when it doesn't.
_OPENCLI_TRIES = 3
_OPENCLI_BACKOFF = [5, 15]

# og:description parsing (2026-08-19). The post permalink page carries
#     "885 likes, 33 comments - nasimamirza on May 9, 2026: "caption...""
# in <meta property="og:description">. Unlike the profile listing, this is fetched from the
# post's OWN url, so whatever it says is BY CONSTRUCTION about the post_id we navigated to --
# it cannot be misattributed the way a positional match can.
#
# Counts here are abbreviated by Instagram ("1M likes" for a true 1,416,111), so they are used
# only when they carry no K/M suffix. Dates carry +/-1 day (viewer-local rendering); immaterial
# for straddle analysis but never present them as exact.
_OG_JS = ('JSON.stringify(document.querySelector('
          '\'meta[property="og:description"]\')?.content)')
_OG_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_OG_DATE_RE = re.compile(r"on\s+(" + "|".join(_OG_MONTHS) + r")\s+(\d{1,2}),\s*(\d{4})", re.I)
_OG_COUNT_RE = re.compile(r"([\d.,]+\s*[KM]?)\s+likes?,\s*([\d.,]+\s*[KM]?)\s+comments?", re.I)


def _og_exact_int(tok: str):
    """Only EXACT counts. An abbreviated '76K' is rounded by Instagram -- writing it would
    overwrite a real value with a wrong one, so it is discarded rather than approximated."""
    tok = tok.replace(",", "").strip()
    if not tok or tok[-1].upper() in ("K", "M"):
        return None
    try:
        return int(float(tok))
    except ValueError:
        return None


def parse_og_description(desc):
    """-> {'date': 'M/D/YYYY'|None, 'likes': int|None, 'comments': int|None}."""
    out = {"date": None, "likes": None, "comments": None}
    if not desc:
        return out
    m = _OG_DATE_RE.search(desc)
    if m:
        out["date"] = f"{_OG_MONTHS[m.group(1).lower()]}/{int(m.group(2))}/{m.group(3)}"
    c = _OG_COUNT_RE.search(desc)
    if c:
        out["likes"] = _og_exact_int(c.group(1))
        out["comments"] = _og_exact_int(c.group(2))
    return out


def caption_key(text):
    """Join key shared by the listing and the post page -- replaces positional matching.

    `instagram user` truncates captions to exactly 100 chars while the page extract has the
    full text, so the key is a 60-char prefix of collapsed-lowercase alphanumerics: short
    enough to survive truncation, long enough to identify a post. Returns None for captions
    too short to identify anything (empty/emoji-only), which are left UNMATCHED rather than
    guessed at.
    """
    if not text:
        return None
    norm = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return norm[:60] if len(norm) >= 12 else None


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
    # RETRY (2026-08-19). Until now this was a single shot: any transient failure raised
    # immediately and the caller fell back to the browser-only path, losing the adapter's
    # structured metadata for that creator entirely. Nobody ever retried.
    #
    # A 429 is deliberately NOT retried. It is a real platform throttle, and hammering it is
    # how the multi-hour Instagram blocks recorded in HANDOFF.md were earned. Retry is for
    # transport flakiness (chrome-error://, daemon hiccups, timeouts), not for being told to stop.
    last = None
    for attempt in range(_OPENCLI_TRIES):
        try:
            result = subprocess.run(
                [_OPENCLI_BIN, *args], capture_output=True, text=True, timeout=timeout,
                env=env, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired:
            last = RuntimeError(f"opencli {' '.join(args)} timed out after {timeout}s")
        else:
            if result.returncode == 0:
                if attempt:
                    log.info("opencli %s recovered on attempt %d", args[0], attempt + 1)
                    _OPENCLI_STATS["recovered"] += 1
                return yaml.safe_load(result.stdout)
            blob = f"{result.stdout}{result.stderr}"
            last = RuntimeError(f"opencli {' '.join(args)} failed: {blob}")
            if "429" in blob or "rate limit" in blob.lower():
                raise last          # throttle -- back off entirely, do not retry
        _OPENCLI_STATS["retried"] += 1
        if attempt < _OPENCLI_TRIES - 1:
            time.sleep(_OPENCLI_BACKOFF[attempt])
    _OPENCLI_STATS["exhausted"] += 1
    raise last


# YouTube quota rotation (2026-08-18). search().list costs 100 units against a 10k/day
# budget PER KEY, so handle discovery burns a key in ~95 searches -- last round exhausted
# one mid-backlog. Each additional key is its own GCP project with an independent pool.
#
# SEQUENTIAL, not round-robin: exhaust key 1, then move to key 2, then key 3. Round-robin
# would spread every run across all three and burn them out simultaneously, leaving no
# reserve. Keys come from .env only -- never hardcoded here.
_YT_KEYS = [k for k in (ENV.get("YOUTUBE_API_KEY"), ENV.get("YOUTUBE_API_KEY_2"),
                         ENV.get("YOUTUBE_API_KEY_3")) if k]
_yt_key_idx = 0


def youtube_quota_state() -> str:
    return f"key {_yt_key_idx + 1} of {len(_YT_KEYS)}"


def youtube_api_get(endpoint: str, **params) -> dict:
    """GET a YouTube Data API endpoint, rotating to the next key on quota exhaustion.

    Only 'quota exceeded' triggers rotation. Any other 403 (bad key, API disabled, referer
    restriction) is re-raised: silently rotating past a misconfigured key would hide a real
    setup problem behind a confusing 'all keys exhausted'.
    """
    global _yt_key_idx
    if not _YT_KEYS:
        raise RuntimeError("no YOUTUBE_API_KEY* found in .env")
    last_err = None
    while _yt_key_idx < len(_YT_KEYS):
        params["key"] = _YT_KEYS[_yt_key_idx]
        url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            # HTTPError's body is a STREAM and read() consumes it. Reading it here and
            # re-raising left callers with an empty body, so their own quota checks
            # silently failed and logged blank warnings for 137 creators. Stash the
            # decoded text on the exception so a caller can still diagnose.
            body = e.read().decode("utf-8", "replace")
            e.body_text = body

            # Rotate on BOTH exhaustion shapes. Measured 2026-08-18: an exhausted search
            # quota surfaces as **HTTP 429 rateLimitExceeded**, NOT the 403 'quota' this
            # originally checked for -- so rotation never fired and two entirely healthy
            # keys went unused while every request failed.
            exhausted = (e.code == 429) or (e.code == 403 and "quota" in body.lower())
            if exhausted:
                log.warning("YouTube key %d/%d exhausted (HTTP %d) — rotating",
                             _yt_key_idx + 1, len(_YT_KEYS), e.code)
                _yt_key_idx += 1
                last_err = e
                continue
            raise
    raise last_err if last_err else RuntimeError("all YouTube keys exhausted")


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

    def __init__(self, rate_limiter: RateLimiter, dry_run: bool = False,
                  post_cap: int = DEFAULT_POST_CAP, recency_days: int = DEFAULT_RECENCY_DAYS):
        self.rate_limiter = rate_limiter
        self.dry_run = dry_run
        self.post_cap = post_cap
        self.cutoff = recency_cutoff(recency_days)
        self.skipped_stale = 0
        # How each post's metadata was joined. Reported per creator so a run that silently
        # stops matching (adapter down, caption format change) is visible instead of just
        # producing quietly emptier rows.
        self.meta_match: dict[str, int] = {}

    def _is_stale(self, raw_date: str) -> bool:
        """True if an "M/D/YYYY" date predates the recency cutoff. An unparseable date is
        NOT stale -- we can't prove it, so the post is kept rather than silently dropped."""
        try:
            return (datetime.strptime(raw_date, "%m/%d/%Y").replace(tzinfo=timezone.utc)
                    < self.cutoff)
        except (ValueError, TypeError):
            return False

    def _release_on_failure(self, handle: str) -> None:
        """No-op by default; only browser-backed workers hold tab leases."""
        return

    def run_batch(self, creators: list[Creator], conn) -> None:
        for creator in creators:
            handle = self._handle_for(creator)
            if not handle:
                continue
            # Reset per-creator so the log line reports THIS creator's skips, not a
            # running total across the batch (real reporting bug found reading the
            # first full run's output — "29 skipped" repeated for creators that had
            # skipped nothing).
            self.skipped_stale = 0
            self.meta_match = {}
            try:
                self.process_creator(creator, handle, conn)
            except Exception:
                log.exception("Failed for %s (%s) on %s — skipping, continuing batch",
                               creator.name, handle, self.platform_name)
                # Backstop for the tab-lease leak: process_creator may raise from any
                # browser call after the session is opened, not just the known
                # no-post-links path. The session name is deterministic
                # (orc_<handle>), so releasing it here covers every failure route
                # without restructuring the worker. Harmless when nothing is held.
                self._release_on_failure(handle)

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
        # maxResults caps at 50 per YouTube API; post_cap above that would need
        # pageToken paging (not implemented — 40 fits in one page).
        playlist_resp = youtube_api_get(
            "playlistItems", playlistId=uploads_playlist, part="contentDetails",
            maxResults=min(self.post_cap, 50),
        )
        video_ids = [i["contentDetails"]["videoId"] for i in playlist_resp.get("items", [])]
        if not video_ids:
            return

        self.rate_limiter.wait()
        videos_resp = youtube_api_get(
            "videos", id=",".join(video_ids), part="snippet,statistics,contentDetails",
        )
        kept = 0
        for v in videos_resp.get("items", []):
            vs, vstats = v["snippet"], v["statistics"]
            # Recency filter — skip (don't count toward the cap) anything older than
            # the rolling window, so a raised cap pulls MORE RECENT posts rather than
            # padding with stale ones. publishedAt is RFC3339 ("2026-08-04T19:48:02Z").
            published = vs.get("publishedAt")
            if published:
                try:
                    if datetime.fromisoformat(published.replace("Z", "+00:00")) < self.cutoff:
                        self.skipped_stale += 1
                        continue
                except ValueError:
                    pass  # unparseable date — keep rather than silently drop
            kept += 1
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
                # 100 is the API max per page. Raised from 20 — comments are the
                # single biggest contributor to per-creator datapoint counts, and
                # commentThreads costs 1 quota unit regardless of maxResults, so
                # this is a 5x yield increase for zero extra quota cost.
                comments_resp = youtube_api_get(
                    "commentThreads", videoId=v["id"], part="snippet", maxResults=100, order="relevance",
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
        log.info("YouTube: %s -> %d videos kept (%d skipped as older than the %s cutoff)",
                  handle, kept, self.skipped_stale, self.cutoff.date())


class InstagramWorker(PlatformWorker):
    platform_name = "instagram"

    def _handle_for(self, creator: Creator) -> str | None:
        return creator.instagram_handle

    def _release_on_failure(self, handle: str) -> None:
        # Mirrors the session name built in process_creator.
        _release_session(f"orc_{handle}")

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
                    -- full_name/bio were NOT in this update clause, which made them
                    -- unfillable for any creator whose username had already been inserted
                    -- by the comment-author path below (username only, ON CONFLICT DO
                    -- NOTHING). Measured 2026-08-17: 130 of 231 handle-named creators had
                    -- an instagram_profiles row with an EMPTY full_name, and only 15 of
                    -- 13,746 profile rows carried a name at all. That empty full_name is
                    -- what blocks the Reddit topic-sub search, which queries by name.
                    -- coalesce(excluded, existing) so a later listing-sourced write with a
                    -- NULL name cannot wipe a good one.
                    full_name=coalesce(excluded.full_name, instagram_profiles.full_name),
                    bio=coalesce(excluded.bio, instagram_profiles.bio),
                    follower_count=excluded.follower_count, following_count=excluded.following_count,
                    post_count=excluded.post_count, fetched_at=now(), updated_at=now()
                """,
                (handle, creator.creator_id, prof.get("name"), prof.get("bio"),
                 prof.get("followers"), prof.get("following"), prof.get("posts"),
                 str(prof.get("verified")).lower() == "yes"),
            )
        conn.commit()

        # Real bug found+fixed 2026-08-10, after 40 real posts across 8 real creators
        # all came back with ZERO brand hits: instagram_posts was never storing
        # caption/likes/comment_count/media_type at all (only post_id/username/
        # creator_id/brand_id), and brand extraction ran against the first 2000 chars
        # of RAW `browser extract` markdown — which starts with the avatar image's
        # (very long) CDN URL and nav boilerplate, not the caption. The caption could
        # easily fall outside that window, or get diluted by irrelevant alt-text.
        # `opencli instagram user` gives clean, structured caption/likes/comments/type/
        # date directly — use THAT for post metadata and brand extraction, and use
        # `browser extract` only for what it's uniquely good for: comment text.
        self.rate_limiter.wait()
        listing = run_opencli("instagram", "user", handle, "--limit", str(self.post_cap),
                               "-f", "yaml", timeout=90)
        posts_meta = listing if isinstance(listing, list) else []

        self.rate_limiter.wait()
        session = f"orc_{handle}"
        run_opencli("browser", session, "open", f"https://www.instagram.com/{handle}/")
        run_opencli("browser", session, "wait", "time", "2")
        # The post grid is lazy-loaded and load timing is genuinely inconsistent —
        # observed anywhere from 0 to 2+ scrolls needed for the same account across
        # different runs (not just cold-vs-warm cache; re-ran kingjames twice in a
        # row and got different results). Padding the retry budget rather than
        # assuming a fixed scroll count is reliable.
        #
        # With the cap raised from 5 to 40, one screenful is no longer enough — the
        # grid only renders ~8-12 links initially, so keep scrolling until we have
        # post_cap distinct links or the count stops growing (hit the end of the
        # profile, or lazy-load stalled). Bounded so a stalled grid can't loop forever.
        post_paths: list[str] = []
        stalls = 0
        for _ in range(self.post_cap):  # generous upper bound on scroll rounds
            try:
                found = run_opencli("browser", session, "find", "--css",
                                     'a[href*="/reel/"], a[href*="/p/"]',
                                     "--limit", str(self.post_cap * 2))
                entries = [e["attrs"]["href"] for e in found.get("entries", [])]
            except RuntimeError:
                entries = []
            before = len(post_paths)
            # Drop other accounts' posts BEFORE they count toward the cap -- see
            # own_post_paths(). Filtering here (not at write time) means the scroll loop
            # keeps going until we have post_cap of the creator's OWN posts.
            post_paths = list(dict.fromkeys(post_paths + own_post_paths(entries, handle)))
            if len(post_paths) >= self.post_cap:
                break
            stalls = stalls + 1 if len(post_paths) == before else 0
            if stalls >= 3:
                log.info("Instagram: %s grid stopped growing at %d links", handle, len(post_paths))
                break
            run_opencli("browser", session, "scroll", "down")
            run_opencli("browser", session, "wait", "time", "3")
        if not post_paths:
            # Release the tab lease before bailing. Real bug found 2026-08-14 by
            # pattern-matching 3 days of unattended scheduled-run logs: this raise sits
            # BEFORE the `browser close` at the end of the method, and `session` is a
            # NEW named session per creator (orc_<handle>), so every creator that failed
            # here leaked a held tab lease and an orphaned tab for the rest of the run.
            # Across a 13-creator pass that was up to 8 leaked leases. Independently
            # confirmed the same class of leak by hand: a killed collab run left a stale
            # `collabx` lease that had to be released manually before Reddit could work.
            _release_session(session)
            raise RuntimeError(f"no post links found for {handle} after scrolling")

        # METADATA IS NO LONGER MATCHED BY POSITION (fixed 2026-08-19; flagged 3 rounds).
        #
        # The old code did `meta = posts_meta[i]`, pairing the i-th grid URL with the i-th
        # listing entry. Two independent defects:
        #   1. The listing returns exactly 12 rows no matter what `--limit` says (verified
        #      2026-08-19 across 3 handles at 12/15/20/25/40; the flag DOES work downward,
        #      3->3 and 5->5, so it is a truncation of a 12-post first-paint scrape, not a
        #      broken flag). Past index 11 every field landed NULL.
        #   2. Instagram pins up to 3 posts to the top of a grid, so grid order != recency
        #      order and the two lists are offset on any creator that pins -- writing one
        #      post's date and likes onto another, silently.
        #
        # Now: the post's own og:description supplies date/likes/comments (fetched from the
        # post url itself, so it cannot be misattributed), and the listing is joined by
        # CAPTION CONTENT with ambiguity refused. Neither path can attach metadata to a post
        # it does not belong to.
        kept = 0
        for path in post_paths[:self.post_cap]:
            post_url = f"https://www.instagram.com{path}"
            post_id = path.strip("/").split("/")[-1]
            self.rate_limiter.wait()
            run_opencli("browser", session, "open", post_url)
            run_opencli("browser", session, "wait", "time", "2")

            try:
                raw_og = run_opencli("browser", session, "eval", _OG_JS)
            except RuntimeError:
                raw_og = None
            og = parse_og_description(raw_og if isinstance(raw_og, str) else "")

            # Recency filter, now driven by the post's OWN date rather than a positionally
            # guessed one. Checked before `extract` so a stale post costs one navigation
            # instead of a full page pull. Posts with no usable date are kept (can't prove
            # they're stale) rather than silently dropped.
            if og["date"] and self._is_stale(og["date"]):
                self.skipped_stale += 1
                continue

            extracted = run_opencli("browser", session, "extract")
            markdown = extracted["content"] if isinstance(extracted, dict) else str(extracted)
            caption = parse_caption(markdown, handle)

            meta, match_status = match_listing_meta(caption, posts_meta)
            self.meta_match[("matched" if meta else match_status.split(" (")[0])] = (
                self.meta_match.get("matched" if meta else match_status.split(" (")[0], 0) + 1)
            meta = meta or {}
            if not caption:
                caption = meta.get("caption")

            # Listing values win where present -- they are exact and carry no timezone shift.
            # og:description backfills everything past the 12-row ceiling, and contributes
            # counts ONLY when Instagram did not abbreviate them (see _og_exact_int).
            post_date = meta.get("date") or og["date"]
            like_count = meta.get("likes") if meta.get("likes") is not None else og["likes"]
            comment_count = (meta.get("comments") if meta.get("comments") is not None
                             else og["comments"])
            if post_date and self._is_stale(post_date):
                self.skipped_stale += 1
                continue
            kept += 1

            with conn.cursor() as cur:
                # `opencli instagram user` truncates captions to exactly 100 chars.
                # The page extract we already fetched for comments has the full text —
                # prefer it, fall back to the truncated listing value. Track C hit this
                # directly: the Kohli/Agilitas caption was cut mid-sentence while they
                # were deciding whether it's a valid sponsorship training pair, and
                # brand extraction was only ever seeing the first 100 chars.
                brand_id = brand_id_for_text(cur, caption)
                # meta["date"] is "M/D/YYYY" (e.g. "8/3/2026") — to_date with an
                # explicit format string, not implicit cast, since Postgres's default
                # date parsing assumes DMY/YMD depending on server locale and would
                # silently misread US-style M/D/Y for some dates (e.g. 8/3 could be
                # read as day=8 month=3 instead of month=8 day=3).
                cur.execute(
                    """
                    insert into instagram_posts
                        (post_id, username, creator_id, caption, media_type, like_count,
                         comment_count, posted_at, brand_id)
                    values (%s,%s,%s,%s,%s,%s,%s,to_date(%s,'MM/DD/YYYY'),%s)
                    on conflict (post_id) do update set
                        caption=case when length(coalesce(excluded.caption,'')) >
                                          length(coalesce(instagram_posts.caption,''))
                                     then excluded.caption else instagram_posts.caption end,
                        media_type=coalesce(excluded.media_type, instagram_posts.media_type),
                        posted_at=coalesce(excluded.posted_at, instagram_posts.posted_at),
                        like_count=excluded.like_count, comment_count=excluded.comment_count,
                        fetched_at=now(), brand_id=coalesce(excluded.brand_id, instagram_posts.brand_id)
                    """,
                    (post_id, handle, creator.creator_id, caption, meta.get("type"),
                     like_count, comment_count, post_date, brand_id),
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
        log.info("Instagram: %s -> %d posts kept (%d skipped as older than the %s cutoff, "
                  "%d links found) | metadata join: %s",
                  handle, kept, self.skipped_stale, self.cutoff.date(), len(post_paths),
                  self.meta_match or "none")
        run_opencli("browser", session, "close")


def _release_session(session: str) -> None:
    """Best-effort tab-lease release. Never raises — a cleanup failure must not mask the
    real error that triggered it, and must not abort the rest of the batch."""
    try:
        run_opencli("browser", session, "close", timeout=20)
    except Exception:
        pass


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
        # A creator is workable on Reddit if it has EITHER kind of source.
        if creator.reddit_handles:
            return creator.reddit_handles[0]
        return creator.reddit_topic_subs[0] if creator.reddit_topic_subs else None

    def process_creator(self, creator: Creator, handle: str, conn) -> None:
        # Two collection modes (Weeks 11-13 change — see migration 20260810000000):
        #
        #  1. reddit_handles     = CREATOR-SPECIFIC subs (r/ViratKohli). The sub exists
        #     because of this creator, so the feed is taken broadly — and deliberately
        #     NOT name-filtered, since posts there often say "he"/"the king" rather
        #     than the creator's name, and filtering would discard real signal.
        #  2. reddit_topic_subs  = GENERAL subs (r/ipl, r/tennis). Taking these feeds
        #     broadly was measured at ~0% creator relevance (0/41 r/tennis posts
        #     mentioned Sania Mirza, etc.), so instead SEARCH the sub for the creator's
        #     name and additionally verify each hit really mentions them — search
        #     relevance ranking alone returns loose matches.
        collected = 0
        for sub in creator.reddit_handles:
            collected += self._collect(creator, sub, conn, mode="creator_sub")
        for sub in creator.reddit_topic_subs:
            collected += self._collect(creator, sub, conn, mode="topic_search")
        log.info("Reddit: %s -> %d posts across %d creator-sub(s) + %d topic sub(s)",
                  creator.name, collected, len(creator.reddit_handles),
                  len(creator.reddit_topic_subs))

    def _search_retry_empty(self, query: str, sub: str, tries: int = 3):
        """`reddit search`, retried when it returns EMPTY -- not when it errors.

        Observed 2026-08-19: "Sunrisers Hyderabad" and "Royal Challengers Bengaluru" each
        returned 0 results, then 15 on retest with the query unchanged. The command exits 0
        and yields an empty list, so it is a "success" -- run_opencli's retry never sees it,
        and a flake is indistinguishable from a creator genuinely having no Reddit presence.

        ⚠️ SCOPE CORRECTION, same day. A follow-up measurement could NOT reproduce it:
        0 empties in 36 paced calls (20 subreddit-scoped, 16 site-wide), including those two
        exact queries. The original zeros occurred inside a 12-query burst spaced ~4s apart,
        so they look burst-induced rather than a standing defect. The earlier inference --
        that an unknown share of the 77% no-content population might be flakes -- is
        RETRACTED; there is no evidence for it.

        This retry is kept anyway because it is nearly free (it only fires on an empty
        result, which is exactly when a retry is cheap) and it makes any recurrence visible
        in the log instead of silently becoming a "real negative". It is a safety net, not
        a fix for a proven bug.

        A still-empty result after `tries` attempts is accepted as a real negative.
        """
        for attempt in range(tries):
            posts = run_opencli("reddit", "search", query, "--subreddit", sub, "--sort", "new",
                                 "--limit", str(self.post_cap), "-f", "yaml", timeout=90)
            if isinstance(posts, list) and posts:
                if attempt:
                    log.info("Reddit: r/%s '%s' returned empty %dx, then %d results — flake, "
                              "not a real negative", sub, query, attempt, len(posts))
                return posts
            if attempt < tries - 1:
                time.sleep(4)
        return posts

    def _collect(self, creator: Creator, sub: str, conn, mode: str) -> int:
        self.rate_limiter.wait()
        try:
            if mode == "creator_sub":
                # --sort new (not the default "hot"): with a recency window in play,
                # "hot" surfaces highly-upvoted posts of any age which the filter then
                # discards — new makes cap and window pull the same direction.
                posts = run_opencli("reddit", "subreddit", sub, "--sort", "new",
                                     "--limit", str(self.post_cap), "-f", "yaml", timeout=90)
            else:
                posts = self._search_retry_empty(creator.name, sub)
        except RuntimeError as e:
            log.warning("Reddit %s r/%s for %s failed: %s", mode, sub, creator.name,
                         str(e)[:120])
            return 0
        if not isinstance(posts, list):
            return 0

        kept = 0
        irrelevant = 0
        for post in posts[:self.post_cap]:
            post_id = post.get("id")
            if not post_id:
                continue
            # Relevance gate — topic-sub hits only. Reddit search ranks by relevance
            # but still returns loose matches, so verify the creator is actually named.
            if mode == "topic_search":
                blob = f"{post.get('title','')} {post.get('selftext','')}"
                if not mentions_creator(blob, creator.name):
                    irrelevant += 1
                    continue
            # Recency filter — created_utc is an epoch int.
            created = post.get("created_utc")
            if isinstance(created, (int, float)):
                if datetime.fromtimestamp(created, timezone.utc) < self.cutoff:
                    self.skipped_stale += 1
                    continue
            kept += 1
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
                    (post_id, sub, creator.creator_id, post.get("author"), post.get("title"),
                     post.get("selftext"), post.get("created_utc"), post.get("upvotes"),
                     post.get("comments"), brand_id),
                )
                # reddit_posts.creator_id is single-valued and can only ever credit
                # whichever creator's worker wrote the row first — real bug found
                # 2026-08-10 when PV Sindhu and Saina Nehwal both map to r/badminton
                # and Saina silently got zero posts. reddit_post_creators is the real
                # many-to-many source of truth; always insert here regardless of
                # whether this post_id already existed under a different creator.
                cur.execute(
                    """
                    insert into reddit_post_creators (post_id, creator_id)
                    values (%s,%s) on conflict do nothing
                    """,
                    (post_id, creator.creator_id),
                )
            conn.commit()

            self.rate_limiter.wait()
            self._fetch_comments(post_id, conn)
        log.info("Reddit[%s] r/%s for %s -> %d kept (%d off-topic, %d stale, %d returned)",
                  mode, sub, creator.name, kept, irrelevant, self.skipped_stale, len(posts))
        return kept

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


def get_or_create_creator(conn, name: str, category: str, replace_reddit: bool = False, **handles) -> Creator:
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
    topic_subs = handles.get("reddit_topic_subs") or []

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
                    reddit_handles = case when %s then %s
                        else (select array(select distinct unnest(reddit_handles || %s))) end,
                    reddit_topic_subs = case when %s then %s
                        else (select array(select distinct unnest(reddit_topic_subs || %s))) end,
                    updated_at = now()
                where creator_id = %s
                """,
                (name, category, yt, ig,
                 replace_reddit, reddit_handles, reddit_handles,
                 replace_reddit, topic_subs, topic_subs, creator_id),
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
                insert into creators (name, category, youtube_handle, instagram_handle, reddit_handles, reddit_topic_subs)
                values (%s,%s,%s,%s,%s,%s)
                returning creator_id
                """,
                (name, category, yt, ig, reddit_handles, topic_subs),
            )
            creator_id = cur.fetchone()[0]
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            "select name, category, youtube_handle, instagram_handle, reddit_handles, reddit_topic_subs from creators where creator_id = %s",
            (creator_id,),
        )
        r_name, r_category, r_yt, r_ig, r_reddit, r_topic = cur.fetchone()
    return Creator(creator_id=str(creator_id), name=r_name, category=r_category,
                    youtube_handle=r_yt, instagram_handle=r_ig, reddit_handles=r_reddit or [],
                    reddit_topic_subs=r_topic or [])


def seed_creators(conn, target_list: list[dict]) -> dict[str, Creator]:
    """Pre-populate `creators` with full cross-platform handle bundles BEFORE
    dispatching per-platform sub-agents — this is the primary defense against the
    3-unlinked-rows problem, not just the merge logic in get_or_create_creator above.
    Each entry: {"name", "category", "youtube_handle"?, "instagram_handle"?,
    "reddit_handles"?}. Returns {name: Creator} for the caller to inspect.
    """
    result = {}
    for entry in target_list:
        # Curated list is AUTHORITATIVE for Reddit sources — replace, don't merge.
        # Merge-only semantics made it impossible to RECLASSIFY a sub from
        # creator-specific to topic (real bug: after the Weeks 11-13 split, Sania
        # Mirza still had r/tennis listed as creator-specific from the old seeding).
        c = get_or_create_creator(
            conn, entry["name"], entry["category"], replace_reddit=True,
            youtube_handle=entry.get("youtube_handle"),
            instagram_handle=entry.get("instagram_handle"),
            reddit_handles=entry.get("reddit_handles", []),
            reddit_topic_subs=entry.get("reddit_topic_subs", []),
        )
        result[entry["name"]] = c
        log.info("Seeded creator %s -> %s (yt=%s ig=%s reddit=%s)",
                  entry["name"], c.creator_id, c.youtube_handle, c.instagram_handle, c.reddit_handles)
    return result


def load_creator_by_instagram_handle(conn, handle: str) -> Creator | None:
    """Existing creator with this Instagram handle, with its real Reddit config loaded."""
    with conn.cursor() as cur:
        cur.execute("""
            select creator_id, name, category, youtube_handle, instagram_handle,
                   coalesce(reddit_handles, '{}'), coalesce(reddit_topic_subs, '{}')
            from creators where lower(instagram_handle) = lower(%s) limit 1
        """, (handle,))
        row = cur.fetchone()
    if not row:
        return None
    return Creator(creator_id=row[0], name=row[1], category=row[2], youtube_handle=row[3],
                    instagram_handle=row[4], reddit_handles=list(row[5]),
                    reddit_topic_subs=list(row[6]))


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
    parser.add_argument("--post-cap", type=int, default=DEFAULT_POST_CAP,
                         help=f"Max posts fetched per creator (default {DEFAULT_POST_CAP}). Posts "
                              "outside the recency window are skipped without consuming this budget.")
    parser.add_argument("--recency-days", type=int, default=DEFAULT_RECENCY_DAYS,
                         help=f"Rolling recency window in days (default {DEFAULT_RECENCY_DAYS} "
                              "≈ 6 months). Posts older than this are skipped.")
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
            if args.platform == "reddit":
                # Reddit creators are workable from EITHER source kind.
                value = value or entry.get("reddit_topic_subs")
            if not value:
                continue
            creators.append(get_or_create_creator(
                conn, entry["name"], entry["category"],
                youtube_handle=entry.get("youtube_handle"),
                instagram_handle=entry.get("instagram_handle"),
                reddit_handles=entry.get("reddit_handles", []),
                reddit_topic_subs=entry.get("reddit_topic_subs", []),
            ))
    elif not args.dry_run and args.handles:
        for h in args.handles:
            # PREFER AN EXISTING CREATOR. This branch used to go straight to
            # get_or_create_creator(conn, h, ...), which keys on NAME -- so passing an
            # Instagram handle minted a brand-new creator row named after the handle,
            # instagram_handle NULL, sitting alongside the real one. Running
            # `--platform reddit --handles <ig_handle>` on 6 creators created 8 junk rows
            # (259 -> 267) and split one creator's Reddit data onto a row its Instagram data
            # could never reach. Found and cleaned up 2026-08-19.
            #
            # For reddit specifically the old code was doubly wrong: it set
            # reddit_handles=[<instagram handle>], making the worker search r/<ig_handle> --
            # a subreddit that does not exist -- instead of the creator's assigned topic subs.
            existing = load_creator_by_instagram_handle(conn, h)
            if existing:
                creators.append(existing)
                continue
            kwargs = {f"{args.platform}_handle" if args.platform != "reddit" else "reddit_handles":
                      h if args.platform != "reddit" else [h]}
            creators.append(get_or_create_creator(conn, h, "other", **kwargs))

    worker = WORKERS[args.platform](RateLimiter(), dry_run=args.dry_run,
                                     post_cap=args.post_cap, recency_days=args.recency_days)
    log.info("Running %s with post_cap=%d, recency cutoff=%s",
              args.platform, worker.post_cap, worker.cutoff.date())
    worker.run_batch(creators, conn)


if __name__ == "__main__":
    main()
