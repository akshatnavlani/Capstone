"""Identity-key tests for get_or_create_creator, against the REAL database.

Two behaviours are asserted together because they pull in opposite directions, and the reason
the hole existed for so long is that fixing one had previously broken the other:

  1. A Reddit-only creator (no Instagram, no YouTube handle) must be found again on a second
     call instead of being re-created. This is the "Athletics" defect: a run on 2026-08-20
     minted a duplicate and split that creator's content across two identities.

  2. Two DIFFERENT creators who merely share a subreddit must stay separate. This is the
     PV Sindhu / Saina Nehwal collision from 2026-08-10, caused by matching on
     reddit_handles overlap -- both are legitimately in r/badminton.

Test 2 is the regression guard. It passes for a specific reason worth stating: the new key is
the creator's NAME, and those two creators have different names, so shared community
membership can no longer merge them.

Cleans up after itself, and asserts the cleanup landed rather than assuming it.

Run: python test_get_or_create_identity.py
"""

import psycopg2

from orchestrator import ENV, get_or_create_creator

MARK = "__identitytest__"


def cleanup(conn):
    with conn.cursor() as cur:
        cur.execute("delete from creators where name like %s", (MARK + "%",))
        removed = cur.rowcount
    conn.commit()
    return removed


def main() -> None:
    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cleanup(conn)
    failures = []

    # 1. Reddit-only creator is reused, not duplicated.
    a = get_or_create_creator(conn, MARK + "RedditOnly", "athlete",
                               reddit_topic_subs=["Cricket"])
    b = get_or_create_creator(conn, MARK + "RedditOnly", "athlete",
                               reddit_topic_subs=["Cricket", "ipl"])
    if a.creator_id != b.creator_id:
        failures.append(f"FAIL reddit-only creator duplicated: {a.creator_id} != {b.creator_id}")
    else:
        print(f"PASS reddit-only creator reused ({a.creator_id})")

    # 2. THE REGRESSION GUARD. Different names, shared subreddit -> must stay separate.
    s1 = get_or_create_creator(conn, MARK + "PV Sindhu", "athlete",
                                reddit_topic_subs=["badminton"])
    s2 = get_or_create_creator(conn, MARK + "Saina Nehwal", "athlete",
                                reddit_topic_subs=["badminton"])
    if s1.creator_id == s2.creator_id:
        failures.append("FAIL Saina/Sindhu collision REINTRODUCED -- a shared subreddit "
                         "merged two different creators")
    else:
        print("PASS shared subreddit did NOT merge two differently-named creators")

    # 3. A name match must not absorb a creator that HAS handles.
    h = get_or_create_creator(conn, MARK + "HasHandle", "athlete",
                               instagram_handle=MARK + "ig_handle")
    r = get_or_create_creator(conn, MARK + "HasHandle", "athlete",
                               reddit_topic_subs=["Cricket"])
    if h.creator_id == r.creator_id:
        failures.append("FAIL a handle-less lookup absorbed a creator that has an "
                         "Instagram handle -- the guard on the ROW side is not holding")
    else:
        print("PASS handle-holding creator not absorbed by a same-name Reddit-only lookup")

    removed = cleanup(conn)
    with conn.cursor() as cur:
        cur.execute("select count(*) from creators where name like %s", (MARK + "%",))
        leftover = cur.fetchone()[0]
    conn.close()
    print(f"cleanup: {removed} test rows removed, {leftover} left behind")
    if leftover:
        failures.append(f"FAIL cleanup left {leftover} test rows in creators")

    print()
    for f in failures:
        print(f)
    print("ALL PASS" if not failures else f"{len(failures)} FAILURE(S)")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
