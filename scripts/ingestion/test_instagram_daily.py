"""Tests for the pure parts of instagram_daily.py (no Instagram, no database)."""
import shutil

_real_which = shutil.which
shutil.which = lambda name, *a, **k: "stub" if name == "opencli" else _real_which(name, *a, **k)
import instagram_daily as d  # noqa: E402
shutil.which = _real_which


def test_nothing_is_planned_when_the_budget_is_gone():
    assert d.split_budget(0) == (0, 0)
    assert d.split_budget(-30) == (0, 0)


def test_the_plan_never_costs_more_than_the_budget():
    for budget in range(1, 140):
        refresh, new = d.split_budget(budget)
        assert refresh * d.LOADS_PER_REFRESH + new * d.LOADS_PER_NEW_CREATOR <= budget + 1e-9


def test_a_full_day_mixes_refreshes_and_new_creators():
    refresh, new = d.split_budget(100)
    assert refresh >= 10 and new >= 2


def test_a_creators_empty_page_is_not_a_block_but_instagram_pushing_back_is():
    assert d.is_block("HTTP 429 Too Many Requests") and d.is_block("Rate limit reached") and d.is_block("redirected to accounts/login/")
    assert d.is_block("chrome-error://chromewebdata") and d.is_block("Please try again later")
    assert not d.is_block("no post links found for corefitlabofficial after scrolling")
    assert not d.is_block("profile page is private or empty")


def test_a_failure_is_written_down_so_the_creator_can_be_skipped():
    class Cur:
        def __init__(self):
            self.sql = []
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def execute(self, sql, params):
            self.sql.append((sql, params))
    class Conn:
        def __init__(self):
            self.cur, self.commits = Cur(), 0
        def cursor(self):
            return self.cur
        def commit(self):
            self.commits += 1
    c = Conn()
    d.record_failure(c, "id-1", "somehandle", "x" * 900)
    assert "instagram_collect_failures" in c.cur.sql[0][0] and c.commits == 1
    assert c.cur.sql[0][1][0] == "id-1" and len(c.cur.sql[0][1][2]) == 500


def test_chrome_check_needs_the_extension_to_say_connected(monkeypatch):
    class Out:
        stdout = "[OK] Daemon: running\n[MISSING] Extension: not connected\n"
    monkeypatch.setattr(d.subprocess, "run", lambda *a, **k: Out())
    assert d.chrome_connected() is False
    Out.stdout = "[OK] Extension: connected (v1.0.24)\n"
    assert d.chrome_connected() is True


def test_backfill_only_reads_posts_that_still_lack_counts():
    import instagram_backfill_counts as b

    class Cur:
        def execute(self, sql, params):
            assert "like_count is null" in sql
            self.ids = params[0]
        def fetchall(self):
            return [("b",), ("c",)]          # the database says only b and c still have no counts
    wanted = [{"post_id": "a", "username": "x"}, {"post_id": "b", "username": "x"}, {"post_id": "c", "username": "y"}]
    assert [w["post_id"] for w in b.pending_posts(Cur(), wanted)] == ["b", "c"]


def test_budget_counts_snapshot_rows_and_audit_loads_together():
    class Cur:
        def __init__(self):
            self.n = 0
        def execute(self, sql, params=None):
            self.sql = sql
        def fetchone(self):
            return (53,) if "post_snapshots" in self.sql else (38,)
    assert d.done_today(Cur()) == 91


def test_extra_loads_are_logged_only_when_there_are_some():
    calls = []
    class Cur:
        def execute(self, sql, params):
            calls.append(params)
    d.log_extra_loads(Cur(), 0, "nothing")
    d.log_extra_loads(Cur(), 38, "ownership audit " + "x" * 300)
    assert len(calls) == 1 and calls[0][0] == 38 and len(calls[0][1]) == 200


def test_the_backfill_reads_the_true_owner_and_refuses_the_wrong_page():
    import instagram_backfill_counts as b
    assert b.owner_of('885 likes, 33 comments - kohli_fan.99 on May 9, 2026: "hello"') == "kohli_fan.99"
    assert b.owner_of("no owner in this text") is None and b.owner_of(None) is None
    assert b.same_page("DAbc123", "https://www.instagram.com/p/DAbc123/") is True
    assert b.same_page("DAbc123", "https://www.instagram.com/p/ZZZ999/") is False
    assert b.same_page("DAbc123", None) is False


def test_the_count_phase_takes_a_small_protected_share_of_the_day():
    assert d.backfill_reserve(pending=300, budget=130) == 25            # a normal day: 25 loads
    assert d.backfill_reserve(pending=7, budget=130) == 7               # never more than there are posts waiting
    assert d.backfill_reserve(pending=300, budget=30) == 10             # a small leftover budget: at most a third of it
    assert d.backfill_reserve(pending=0, budget=130) == 0 and d.backfill_reserve(pending=300, budget=0) == 0
    refresh, new = d.split_budget(130 - d.backfill_reserve(300, 130))
    assert refresh * d.LOADS_PER_REFRESH + new * d.LOADS_PER_NEW_CREATOR + 25 <= 130 + 1e-9   # the three phases together never exceed the cap
