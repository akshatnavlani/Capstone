"""Ingestion orchestrator skeleton — Track A (Data/Infra).

Design + rationale: see ORCHESTRATION.md at repo root.
Schema this writes into: see SCHEMA.md at repo root.

This is NOT wired to real platform calls yet (Weeks 3-4 scope) — the platform
workers below have `# TODO` markers where the actual agent-reach/OpenCLI/YouTube
Data API calls and response parsing go. What IS real:
  - the rate-limiting shape (one gate per platform, since throughput is capped by
    a single logged-in session, not by how many workers you run — see
    DATA_COLLECTION_STATUS.md Section 4)
  - the DB upsert shape (idempotent on platform-native IDs)
  - the per-creator failure isolation (one bad handle doesn't kill the batch)

Run: python scripts/ingestion/orchestrator.py --platform youtube --dry-run
Requires DATABASE_URL in .env once Supabase is provisioned (see .env.example).
"""

import argparse
import logging
import os
import time
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("orchestrator")


@dataclass
class Creator:
    creator_id: str
    name: str
    youtube_handle: str | None
    instagram_handle: str | None
    reddit_handles: list[str]


class RateLimiter:
    """Enforces a minimum interval between calls for one platform's single session.

    Tune min_interval_seconds against real observed behavior once scraping starts —
    the 2-3s figure in DATA_COLLECTION_STATUS.md is agent-reach's stated guidance,
    not something we've validated against sustained real traffic yet.
    """

    def __init__(self, min_interval_seconds: float = 2.5):
        self.min_interval = min_interval_seconds
        self._last_call = 0.0

    def wait(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()


class PlatformWorker:
    platform_name = "base"

    def __init__(self, rate_limiter: RateLimiter, dry_run: bool = False):
        self.rate_limiter = rate_limiter
        self.dry_run = dry_run

    def fetch_creator(self, creator: Creator) -> dict | None:
        raise NotImplementedError

    def upsert(self, creator: Creator, data: dict, conn) -> None:
        raise NotImplementedError

    def run_batch(self, creators: list[Creator], conn) -> None:
        for creator in creators:
            handle = self._handle_for(creator)
            if not handle:
                continue
            self.rate_limiter.wait()
            try:
                data = self.fetch_creator(creator)
            except Exception:
                log.exception("Fetch failed for %s (%s) on %s — skipping, continuing batch",
                               creator.name, handle, self.platform_name)
                continue
            if data is None:
                continue
            if self.dry_run:
                log.info("[dry-run] would upsert %s data for %s", self.platform_name, creator.name)
                continue
            self.upsert(creator, data, conn)

    def _handle_for(self, creator: Creator) -> str | None:
        raise NotImplementedError


class YouTubeWorker(PlatformWorker):
    platform_name = "youtube"

    def _handle_for(self, creator: Creator) -> str | None:
        return creator.youtube_handle

    def fetch_creator(self, creator: Creator) -> dict | None:
        # TODO (Weeks 3-4): call the YouTube Data API (channels.list, search.list,
        # playlistItems.list for uploads, commentThreads.list). Requires
        # YOUTUBE_API_KEY in .env. Not session-bottlenecked like IG/Reddit — see
        # DATA_COLLECTION_STATUS.md Section 4 for the quota budget.
        raise NotImplementedError

    def upsert(self, creator: Creator, data: dict, conn) -> None:
        # TODO: upsert into youtube_channels / youtube_videos / youtube_comments,
        # keyed on channel_id / video_id / comment_id (see SCHEMA.md).
        raise NotImplementedError


class InstagramWorker(PlatformWorker):
    platform_name = "instagram"

    def _handle_for(self, creator: Creator) -> str | None:
        return creator.instagram_handle

    def fetch_creator(self, creator: Creator) -> dict | None:
        # TODO (Weeks 3-4): shell out to `opencli instagram user HANDLE --limit N -f yaml`
        # (requires the OpenCLI Chrome extension + a logged-in instagram.com session —
        # see DATA_COLLECTION_STATUS.md Section 3). Parse the YAML output.
        raise NotImplementedError

    def upsert(self, creator: Creator, data: dict, conn) -> None:
        # TODO: upsert into instagram_profiles / instagram_posts / instagram_comments.
        raise NotImplementedError


class RedditWorker(PlatformWorker):
    platform_name = "reddit"

    def _handle_for(self, creator: Creator) -> str | None:
        return creator.reddit_handles[0] if creator.reddit_handles else None

    def fetch_creator(self, creator: Creator) -> dict | None:
        # TODO (Weeks 3-4): shell out to `opencli reddit subreddit HANDLE -f yaml` (or
        # `rdt sub HANDLE --limit N` for the headless backend — see
        # DATA_COLLECTION_STATUS.md Section 3/4 for the OpenCLI-vs-rdt-cli tradeoff).
        raise NotImplementedError

    def upsert(self, creator: Creator, data: dict, conn) -> None:
        # TODO: upsert into reddit_profiles / reddit_posts / reddit_comments.
        raise NotImplementedError


WORKERS = {
    "youtube": YouTubeWorker,
    "instagram": InstagramWorker,
    "reddit": RedditWorker,
}


def load_target_creators(conn) -> list[Creator]:
    # TODO: SELECT from creators (and join whichever *_profiles table to find rows
    # whose fetched_at is null or stale, for gap-filling passes — see ORCHESTRATION.md).
    raise NotImplementedError


def get_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set — copy .env.example to .env and fill it in")
    import psycopg2  # local import: only needed once a real DB is wired up
    return psycopg2.connect(database_url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=WORKERS.keys(), required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = None if args.dry_run else get_connection()
    creators = [] if args.dry_run else load_target_creators(conn)

    worker = WORKERS[args.platform](RateLimiter(), dry_run=args.dry_run)
    worker.run_batch(creators, conn)


if __name__ == "__main__":
    main()
