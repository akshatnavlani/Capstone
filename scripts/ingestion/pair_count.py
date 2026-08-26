"""THE canonical computable-training-pair count. One definition, one implementation.

WHY THIS EXISTS. Independent recomputation has disagreed with the reported figure twice in a
row -- 38 vs 37, then 30 vs 27. Neither side was wrong; the query kept being hand-rolled
slightly differently each time, and the differences are invisible unless you diff the SQL.
Every count from here on comes from this file, and `loop_stats.py` imports it rather than
keeping a second copy.

THE DEFINITION, stated so it can be argued with rather than guessed at. A computable training
pair is one (EVENT, NEIGHBOUR) combination satisfying all three clauses:

  1. EVENT     -- a DATED sponsored post by creator A, on ANY platform. Instagram counts
                  `is_sponsored OR has_paid_partnership_label` (they are separate columns and
                  either alone is a real disclosure); YouTube and Reddit have only
                  `is_sponsored`. Undated posts are excluded -- without a date no straddle can
                  be evaluated, so they are not events for this purpose.
  2. EDGE      -- A and neighbour B are joined by a collaboration edge, i.e. a
                  `creator_related_accounts` handle that resolves to a DIFFERENT creator in
                  our set. Edges to accounts we do not track are not usable.
  3. STRADDLE  -- B has at least one dated activity STRICTLY BEFORE the event date and at
                  least one STRICTLY AFTER, counted across ALL THREE platforms. Cross-platform
                  matters: Kerala Blasters' only events are YouTube "brought to you by" reads,
                  and an Instagram-only straddle check silently excluded them.

FOUR THINGS THAT ARE *NOT* THE CANONICAL NUMBER, printed anyway because each is a plausible
reading of "how many pairs" and naming them is what stops the next disagreement:
  - distinct DIRECTED creator pairs (A,B) -- collapses an A/B pair that straddles 3 events to 1
  - distinct UNDIRECTED creator pairs     -- additionally collapses (A,B) with (B,A)
  - distinct events that yield >=1 pair   -- counts the events, not the training rows
  - collaboration edge pairs              -- the graph's size, no events involved at all

The canonical count is the (EVENT, NEIGHBOUR) row count, because that is what a training row
actually is: one event, one neighbour whose behaviour around it can be measured.

READ-ONLY. Writes nothing.

Run: python pair_count.py [--json] [--why]
"""

import json
import sys

import psycopg2

from orchestrator import ENV

# Clause 1. Kept as one CTE so every consumer sees the identical event set.
EVENTS = """
    select creator_id, post_id::text as item_id, posted_at, 'instagram' as platform
      from instagram_posts
     where (is_sponsored or has_paid_partnership_label) and posted_at is not null
       and creator_id is not null
    union all
    select creator_id, video_id::text, published_at, 'youtube'
      from youtube_videos where is_sponsored and published_at is not null
       and creator_id is not null
    union all
    select creator_id, post_id::text, posted_at, 'reddit'
      from reddit_posts where is_sponsored and posted_at is not null
       and creator_id is not null
"""

# Clause 2.
PAIRS = """
    select distinct x.creator_id as a, c2.creator_id as b
      from creator_related_accounts x
      join creators c2 on lower(c2.instagram_handle) = lower(x.handle)
                      and c2.creator_id <> x.creator_id
"""

# Clause 3, as two scalar counts so the two halves can be reported separately -- the reason
# a straddle fails is the actionable part, and "56 of 137 fail on the BEFORE side alone" is
# what identified the recency window as the binding constraint.
BEFORE = """
      (select count(*) from instagram_posts q
        where q.creator_id = pr.b and q.posted_at < e.posted_at)
    + (select count(*) from youtube_videos v
        where v.creator_id = pr.b and v.published_at < e.posted_at)
    + (select count(*) from reddit_posts r
        where r.creator_id = pr.b and r.posted_at < e.posted_at)
"""
AFTER = BEFORE.replace("<", ">")

CANDIDATES = f"""
    with events as ({EVENTS}), pairs as ({PAIRS})
    select e.creator_id, e.item_id, e.platform, e.posted_at, pr.b,
           ({BEFORE}) as n_before, ({AFTER}) as n_after
      from events e join pairs pr on pr.a = e.creator_id
"""


def compute(cur) -> dict:
    """The single implementation. Every reported pair count comes through here."""
    cur.execute(f"select * from ({CANDIDATES}) t")
    rows = cur.fetchall()
    good = [r for r in rows if r[5] > 0 and r[6] > 0]
    cur.execute(f"select count(*) from (select distinct least(a::text, b::text), "
                f"greatest(a::text, b::text) from ({PAIRS}) p) t")
    edge_pairs = cur.fetchone()[0]
    return {
        "computable_pairs": len(good),
        "checks_evaluated": len(rows),
        "distinct_directed_creator_pairs": len({(r[0], r[4]) for r in good}),
        "distinct_undirected_creator_pairs": len(
            {tuple(sorted((str(r[0]), str(r[4])))) for r in good}),
        "distinct_events_yielding_pairs": len({r[1] for r in good}),
        "events_total": len({r[1] for r in rows}),
        "collab_edge_pairs": edge_pairs,
        "fail_no_before_only": sum(1 for r in rows if r[5] == 0 and r[6] > 0),
        "fail_no_after_only": sum(1 for r in rows if r[6] == 0 and r[5] > 0),
        "fail_neighbour_silent": sum(1 for r in rows if r[5] == 0 and r[6] == 0),
        "_rows": rows,
    }


def main() -> None:
    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cur = conn.cursor()
    s = compute(cur)
    rows = s.pop("_rows")
    conn.close()

    if "--json" in sys.argv:
        print(json.dumps(s, default=str))
        return

    print(f"\nCOMPUTABLE TRAINING PAIRS   {s['computable_pairs']}   (target >= 20)")
    print("  = (event, neighbour) combinations where the neighbour is active both before "
          "and after\n")
    print(f"  event x neighbour checks evaluated  {s['checks_evaluated']:>5}")
    print(f"  dated sponsorship events            {s['events_total']:>5}")
    print(f"  events yielding at least one pair   {s['distinct_events_yielding_pairs']:>5}")
    print(f"  distinct directed creator pairs     {s['distinct_directed_creator_pairs']:>5}")
    print(f"  distinct undirected creator pairs   {s['distinct_undirected_creator_pairs']:>5}")
    print(f"  collaboration edge pairs (graph)    {s['collab_edge_pairs']:>5}")
    print("\nwhy the rest fail:")
    print(f"  neighbour has NO activity BEFORE    {s['fail_no_before_only']:>5}   "
          "<- what a narrow recency window causes")
    print(f"  neighbour has NO activity AFTER     {s['fail_no_after_only']:>5}")
    print(f"  neighbour has no dated activity     {s['fail_neighbour_silent']:>5}")

    if "--why" in sys.argv:
        print("\nper-check detail (a=event owner, b=neighbour):")
        for r in sorted(rows, key=lambda r: (str(r[3]), str(r[1]))):
            ok = "PAIR" if (r[5] > 0 and r[6] > 0) else "    "
            print(f"  {ok} {str(r[3])[:10]}  {r[2]:<9} {r[1][:14]:<14} "
                  f"before={r[5]:<4} after={r[6]:<4}")


if __name__ == "__main__":
    main()
