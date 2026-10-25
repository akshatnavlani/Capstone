"""P0: how many "sponsorship events" are real sponsorships?

WHY. Every training target is an engagement change measured around a
sponsorship event, and every exposure value sums over sponsored neighbours.
Both come from `is_sponsored` (plus Instagram's paid-partnership label in
Track A's `pair_count`). If that flag is mostly wrong, nothing downstream is
measuring spillover, however good the estimator is.

WHAT IT DOES
  1. Prints event counts per platform and by signal source.
  2. Checks one consistency hazard: `pair_count` treats Instagram's
     `has_paid_partnership_label` as an event, but `creator_sponsorship_events`
     (which `load_treatment` reads for the T vector) does not. A creator who is
     sponsored only by that label produces training pairs while having T = 0.
  3. Writes a CSV to hand-label:
       - group "training": every event behind a computable pair (these drive
         the 19 observations, so they matter most)
       - group "random":   a seeded random sample of the remaining events,
         stratified by platform

HOW TO LABEL. Open each link (or read the text column) and fill `label` with
  yes     -- a real paid / brand partnership
  no      -- not a sponsorship (false positive)
  unsure  -- cannot tell
Then run with --score to get precision per group and platform.

Run from the repo root, with DATABASE_URL set (same .env as training):
  python scripts/sample_sponsorship_labels.py            # write the CSV
  python scripts/sample_sponsorship_labels.py --score    # score a labelled CSV
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import os

import psycopg2


def load_env() -> Path | None:
    """Load .env into os.environ, using the same locations as train_prod_model.

    This MUST run before `import_pair_count`: `_track_a` snapshots os.environ
    when it installs its orchestrator stub, so a .env loaded afterwards is
    invisible to `pair_count`. Returns the file used, for the error message.
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / ".env",                                  # repo root
        here.parents[2] / "track-a-data-infra" / ".env",           # sibling worktree
        Path.cwd() / ".env",                                       # wherever you ran it
    ]
    for p in candidates:
        if p.exists():
            with open(p, encoding="utf-8-sig") as f:  # -sig: tolerate a Windows BOM
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip().removeprefix("export ").strip()
                    v = v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)
            return p
    return None


ENV_FILE = load_env()

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _track_a import import_pair_count  # noqa: E402

_pair_count = import_pair_count()
ENV, compute = _pair_count.ENV, _pair_count.compute

OUT = Path("sponsorship_label_sample.csv")
RANDOM_PER_PLATFORM = 10
SEED = 20261024
TEXT_CHARS = 500

# Same event definition as Track A's pair_count (Clause 1), with the text and
# signal columns a human needs to judge each row.
EVENTS_SQL = """
    select 'instagram', p.post_id::text, p.creator_id::text, c.name, p.posted_at,
           coalesce(p.caption, ''), p.sponsorship_raw_matches::text,
           p.is_sponsored, p.has_paid_partnership_label
      from instagram_posts p left join creators c using (creator_id)
     where (p.is_sponsored or p.has_paid_partnership_label)
       and p.posted_at is not null and p.creator_id is not null
    union all
    select 'youtube', v.video_id::text, v.creator_id::text, c.name, v.published_at,
           coalesce(v.title, '') || ' || ' || coalesce(v.description, ''),
           v.sponsorship_raw_matches::text, v.is_sponsored, null
      from youtube_videos v left join creators c using (creator_id)
     where v.is_sponsored and v.published_at is not null and v.creator_id is not null
    union all
    select 'reddit', r.post_id::text, r.creator_id::text, c.name, r.posted_at,
           coalesce(r.title, '') || ' || ' || coalesce(r.body, ''),
           r.sponsorship_raw_matches::text, r.is_sponsored, null
      from reddit_posts r left join creators c using (creator_id)
     where r.is_sponsored and r.posted_at is not null and r.creator_id is not null
"""

FIELDS = [
    "group", "platform", "content_id", "creator", "posted_at", "link",
    "signal", "raw_matches", "text", "label", "notes",
]


def link_for(platform: str, content_id: str) -> str:
    if platform == "youtube":
        return f"https://www.youtube.com/watch?v={content_id}"
    if platform == "reddit":
        return f"https://www.reddit.com/comments/{content_id.removeprefix('t3_')}"
    # Instagram post_id is a shortcode only if it is not purely numeric.
    if not content_id.isdigit():
        return f"https://www.instagram.com/p/{content_id}/"
    return ""


def signal_of(is_sponsored, paid_label) -> str:
    if is_sponsored and paid_label:
        return "caption+paid_label"
    if paid_label:
        return "paid_label_only"
    return "caption_only"


def write_sample(cur) -> int:
    cur.execute(EVENTS_SQL)
    events = cur.fetchall()
    print(f"Events (pair_count definition): {len(events)}")

    by_platform = Counter(e[0] for e in events)
    by_signal = Counter(signal_of(e[7], e[8]) for e in events)
    for p, n in sorted(by_platform.items()):
        print(f"  {p:<10} {n}")
    print("By signal:")
    for s, n in by_signal.most_common():
        print(f"  {s:<20} {n}")

    # Consistency hazard: events the training pairs use but T never sees.
    label_only = {e[2] for e in events if e[8] and not e[7]}
    cur.execute("select distinct creator_id::text from creator_sponsorship_events")
    in_t = {r[0] for r in cur.fetchall()}
    missing = label_only - in_t
    print(f"\nCreators sponsored ONLY via paid-partnership label: {len(label_only)}")
    print(f"  ...of which have T = 0 in load_treatment: {len(missing)}"
          + ("   <-- mismatch between pair events and T" if missing else ""))

    # Events behind computable pairs are the ones that become training targets.
    rows = compute(cur)["_rows"]
    training_ids = {r[1] for r in rows if r[5] > 0 and r[6] > 0}
    print(f"\nDistinct events behind computable pairs: {len(training_ids)}")

    training = [e for e in events if e[1] in training_ids]
    rest = defaultdict(list)
    for e in events:
        if e[1] not in training_ids:
            rest[e[0]].append(e)
    rng = random.Random(SEED)
    sampled = []
    for platform in sorted(rest):
        pool = rest[platform]
        sampled += rng.sample(pool, min(RANDOM_PER_PLATFORM, len(pool)))

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for group, batch in (("training", training), ("random", sampled)):
            for e in batch:
                w.writerow({
                    "group": group,
                    "platform": e[0],
                    "content_id": e[1],
                    "creator": e[3] or e[2],
                    "posted_at": e[4].date().isoformat() if e[4] else "",
                    "link": link_for(e[0], e[1]),
                    "signal": signal_of(e[7], e[8]),
                    "raw_matches": e[6] or "",
                    "text": " ".join(e[5].split())[:TEXT_CHARS],
                    "label": "",
                    "notes": "",
                })
    print(f"\nWrote {len(training)} training + {len(sampled)} random rows to {OUT}")
    print("Fill the `label` column (yes / no / unsure), then rerun with --score.")
    return 0


def score() -> int:
    if not OUT.exists():
        print(f"{OUT} not found. Run without --score first.")
        return 1
    with OUT.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    def report(name: str, subset: list[dict]) -> None:
        c = Counter((r["label"] or "").strip().lower() for r in subset)
        judged = c["yes"] + c["no"]
        prec = f"{c['yes'] / judged:.0%}" if judged else "n/a"
        print(f"  {name:<28} yes={c['yes']:<3} no={c['no']:<3} unsure={c['unsure']:<3} "
              f"blank={c['']:<3} precision={prec}")

    print("Precision = yes / (yes + no); unsure and blank excluded.")
    for group in ("training", "random"):
        sub = [r for r in rows if r["group"] == group]
        report(group, sub)
        for platform in sorted({r["platform"] for r in sub}):
            report(f"  {group}/{platform}", [r for r in sub if r["platform"] == platform])
        for signal in sorted({r["signal"] for r in sub}):
            report(f"  {group}/{signal}", [r for r in sub if r["signal"] == signal])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--score", action="store_true", help="score a labelled CSV")
    args = ap.parse_args()
    if args.score:
        return score()

    database_url = ENV.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        print(f".env used: {ENV_FILE or 'none found'}")
        print("DATABASE_URL not set. Looked for .env in the repo root, a sibling "
              "track-a-data-infra folder, and the current directory.")
        return 1
    conn = psycopg2.connect(database_url)
    try:
        return write_sample(conn.cursor())
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
