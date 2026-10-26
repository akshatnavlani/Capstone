"""How many of the discarded cross-platform straddles are actually recoverable?

THE SITUATION. Of 75 canonical computable pairs, only 26 produce a same-platform
engagement lift. The other 49 are "cross-platform-only straddles": the neighbour
has activity before the event and after it, but no single platform has BOTH sides
inside the +/- 30-day window, so there is nothing to compare like for like.
Those 49 are 65% of the data, and effective sample size (19 independent
observations) is now the binding constraint on the whole project -- a better
estimator does not add a single observation.

THE HYPOTHESIS. Posting is bursty. A creator may have no YouTube video in the 30
days before an event and several in the 90 days before. If the missing side is
usually the BEFORE side, widening the baseline window -- while holding the after
window at 30 days, because that is the causal window and must not be stretched --
would recover real pairs without comparing incompatible units. The lift is already
a unitless ratio, so nothing about this requires mixing likes with views.

WHY COUNT BEFORE CODING. An asymmetric window is a real methodological cost: the
baseline would be measured over a longer, older stretch than the outcome, which
invites exactly the kind of secular-trend confounding the window was bounding away.
That cost is worth paying for 20 recovered pairs and not for 3. This script
produces the number so the decision is evidence-led.

WHAT IT REPORTS.

  1. A breakdown of why each uncomputable pair is uncomputable, per platform:
     before-only, after-only, or no activity at all in the window. This says
     whether the asymmetry should favour the before side, the after side, or
     whether the data is simply absent.

  2. How many pairs become computable at each candidate baseline width, with the
     after window held at 30 days throughout.

READ-ONLY. Writes nothing, to the database or to disk.

Run from the repo root, with DATABASE_URL set:
    PYTHONPATH=. python scripts/straddle_recovery.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2



def _load_dotenv() -> None:
    """Read the repo-root .env into os.environ (train_prod_model.py does the same).

    Without this the script only saw DATABASE_URL if it was already exported in
    the shell, so it failed where training succeeded.
    """
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)


_load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _track_a import import_pair_count  # noqa: E402

_pair_count = import_pair_count()
ENV, compute = _pair_count.ENV, _pair_count.compute

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.target_clustering import DEFAULT_WINDOW_DAYS  # noqa: E402


def _as_date(value):
    """Postgres returns timestamps; the windows are reasoned about in days."""
    return value.date() if isinstance(value, datetime) else value

PLATFORM_TABLES = {
    "instagram": ("instagram_posts", "posted_at", "like_count", "comment_count"),
    "youtube": ("youtube_videos", "published_at", "view_count", "like_count"),
    "reddit": ("reddit_posts", "posted_at", "score", "num_comments"),
}

# The after window never moves. It is the causal window: engagement that follows
# the sponsorship. Widening it would start counting unrelated later activity as
# the event's effect.
AFTER_DAYS = DEFAULT_WINDOW_DAYS

# Baseline widths to test. 30 is the status quo; None means unbounded, included
# as a ceiling -- the most pairs this approach could ever recover, not a proposal.
BASELINE_WIDTHS = [30, 60, 90, 180, 365, None]


def fetch_dated_posts(cur, creator_id: str, platform: str) -> list:
    """Fully-measured posts for one creator on one platform, as dates.

    The both-columns-non-null requirement is carried over from
    compute_training_pair_deltas.py: a post measured on only one engagement
    column biases whichever side holds more of them. Engagement values are not
    needed here -- this script counts availability, not lift.
    """
    table, date_col, e1, e2 = PLATFORM_TABLES[platform]
    cur.execute(
        f"select {date_col} from {table} "
        f"where creator_id::text = %s and {date_col} is not null "
        f"and {e1} is not null and {e2} is not null",
        (creator_id,),
    )
    return [_as_date(r[0]) for r in cur.fetchall()]


def sides_available(post_dates, event_date, before_days, after_days) -> tuple[bool, bool]:
    """Whether the before and after windows each hold at least one post."""
    anchor = _as_date(event_date)
    after_hi = anchor + timedelta(days=after_days)
    before_lo = None if before_days is None else anchor - timedelta(days=before_days)

    has_before = any(
        d < anchor and (before_lo is None or d >= before_lo) for d in post_dates
    )
    has_after = any(anchor < d <= after_hi for d in post_dates)
    return has_before, has_after


def main() -> int:
    database_url = ENV.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not set. See .env in the repo root.")
        return 1

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    rows = [r for r in compute(cur)["_rows"] if r[5] > 0 and r[6] > 0]
    print(f"Canonical computable pairs: {len(rows)}\n")

    # Cache per (creator, platform): the same neighbour appears in many pairs.
    post_cache: dict[tuple[str, str], list] = {}

    def posts(creator_id: str, platform: str):
        key = (creator_id, platform)
        if key not in post_cache:
            post_cache[key] = fetch_dated_posts(cur, creator_id, platform)
        return post_cache[key]

    # --- why are the uncomputable pairs uncomputable? -------------------------
    reasons: Counter = Counter()
    baseline_gaps: list[int] = []
    uncomputable = []

    for row in rows:
        _, _, _, event_date, neighbour_id, _, _ = row
        computable_now = False
        per_platform = {}
        for platform in PLATFORM_TABLES:
            dates = posts(neighbour_id, platform)
            has_b, has_a = sides_available(dates, event_date, AFTER_DAYS, AFTER_DAYS)
            per_platform[platform] = (has_b, has_a, dates)
            if has_b and has_a:
                computable_now = True

        if computable_now:
            continue
        uncomputable.append((row, per_platform))

        # Classify by the best case across platforms: a pair needing only a
        # wider baseline is more recoverable than one with no activity at all.
        if any(a and not b for b, a, _ in per_platform.values()):
            reasons["after-side present, baseline missing"] += 1
            # How far back is this neighbour's nearest prior post?
            anchor = _as_date(event_date)
            gaps = [
                (anchor - d).days
                for platform, (b, a, dates) in per_platform.items()
                if a
                for d in dates
                if d < anchor
            ]
            if gaps:
                baseline_gaps.append(min(gaps))
        elif any(b and not a for b, a, _ in per_platform.values()):
            reasons["baseline present, after-side missing"] += 1
        else:
            reasons["neither side in window on any platform"] += 1

    print(f"Uncomputable pairs: {len(uncomputable)}")
    print("Why:")
    for reason, count in reasons.most_common():
        print(f"  {count:>4}  {reason}")

    if baseline_gaps:
        baseline_gaps.sort()
        mid = baseline_gaps[len(baseline_gaps) // 2]
        print(
            f"\nFor pairs whose after-side exists, the nearest prior post is "
            f"{baseline_gaps[0]}d away at best, {mid}d at the median, "
            f"{baseline_gaps[-1]}d at worst."
        )
        print("That median is what a baseline window would have to reach.")

    # --- what does widening the baseline actually recover? --------------------
    print(f"\n\nPairs computable, after window fixed at {AFTER_DAYS}d:\n")
    print(f"  {'baseline':>10}  {'computable':>10}  {'recovered':>9}")
    print("  " + "-" * 34)

    baseline_counts = {}
    for width in BASELINE_WIDTHS:
        count = 0
        for row in rows:
            _, _, _, event_date, neighbour_id, _, _ = row
            for platform in PLATFORM_TABLES:
                has_b, has_a = sides_available(
                    posts(neighbour_id, platform), event_date, width, AFTER_DAYS
                )
                if has_b and has_a:
                    count += 1
                    break
        baseline_counts[width] = count
        label = "unbounded" if width is None else f"{width}d"
        recovered = count - baseline_counts[BASELINE_WIDTHS[0]]
        print(f"  {label:>10}  {count:>10}  {recovered:>+9}")

    conn.close()

    ceiling = baseline_counts[None] - baseline_counts[30]
    print(
        f"\nCeiling: an unbounded baseline recovers {ceiling} of {len(uncomputable)} "
        f"uncomputable pairs.\nAnything a bounded window recovers is less than that."
    )
    print(
        "\nReading it: recovery concentrated at 60-90d is worth taking -- the "
        "baseline\nstays recent enough that secular trends are not being mistaken "
        "for the effect.\nRecovery that only appears at 365d or unbounded is not: "
        "that is comparing this\nmonth against last year, which is the confounding "
        "the window existed to prevent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())