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
    assert refresh >= 5 and new >= 3   # 11 Nov 2026: REFRESH_SHARE 0.7 until 20 Nov (collaboration tags); was new >= 5 at 0.3-0.4


class _Cur:
    """Stands in for a database cursor: the verified-creator query returns two rows."""
    connection = None

    def execute(self, *a, **k):
        pass

    def fetchall(self):
        return [("v1", "verified_one"), ("v2", "verified_two")]


def test_creators_that_block_training_pairs_come_first_and_are_not_repeated(monkeypatch):
    monkeypatch.setattr(d, "exposure_targets", lambda cur, n: [("t1", "target_one"), ("v2", "verified_two")])
    got = d.new_creators(_Cur(), 3)
    assert got == [("t1", "target_one"), ("v1", "verified_one"), ("v2", "verified_two")]   # alternates: a blocking creator, then a verified one
    assert d.new_creators(_Cur(), 1) == [("t1", "target_one")]


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


def test_posts_that_gave_no_counts_are_not_asked_for_again(monkeypatch):
    import instagram_backfill_counts as b

    class Cur:
        def execute(self, sql, params=None):
            pass
        def fetchall(self):
            return [("a", "u1"), ("b", "u2"), ("c", "u3")]
    monkeypatch.setattr(b, "load_seen", lambda: {"b": {"stored": "u2", "real": None, "no_counts": True}})
    assert [w["post_id"] for w in b.posts_to_fill(Cur(), 10)] == ["a", "c"]


def test_the_count_phase_takes_a_small_protected_share_of_the_day():
    assert d.backfill_reserve(pending=300, budget=130) == d.BACKFILL_LOADS_PER_DAY == 30   # a normal day (60 until 30 Oct 2026, then 30 so the new-creator share can reach the creators that block training pairs)
    assert d.backfill_reserve(pending=7, budget=130) == 7               # never more than there are posts waiting
    assert d.backfill_reserve(pending=300, budget=30) == 15             # a small leftover budget: at most half of it
    assert d.backfill_reserve(pending=0, budget=130) == 0 and d.backfill_reserve(pending=300, budget=0) == 0
    refresh, new = d.split_budget(130 - d.backfill_reserve(300, 130))
    assert refresh * d.LOADS_PER_REFRESH + new * d.LOADS_PER_NEW_CREATOR + 25 <= 130 + 1e-9   # the three phases together never exceed the cap


def test_refresh_skips_out_of_scope_accounts(monkeypatch):
    class Cur:
        def execute(self, sql, params=None):
            pass
        def fetchall(self):
            return [("sixers", "c_sixers", False), ("fitnessmallu_", "c_fm", False), ("lebron", "c_lb", False), ("yogawithx", "c_yx", False)]
    monkeypatch.setattr(d, "in_scope_ids", lambda cur: {"c_fm", "c_yx"})
    assert d.refresh_handles(Cur(), 5) == ["fitnessmallu_", "yogawithx"]
    assert d.refresh_handles(Cur(), 1) == ["fitnessmallu_"]


def test_refresh_puts_urgent_first_then_past_taggers(monkeypatch):
    class Cur:
        def execute(self, sql, params=None):
            pass
        def fetchall(self):
            return [("plain", "c1", False), ("tagger", "c2", False), ("urgent", "c3", True)]
    monkeypatch.setattr(d, "in_scope_ids", lambda cur: {"c1", "c2", "c3"})
    monkeypatch.setattr(d.Path, "read_text", lambda self, encoding=None: '[["c2", "b", "2026-01-01"]]')
    assert d.refresh_handles(Cur(), 3) == ["urgent", "tagger", "plain"]
