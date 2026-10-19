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


def test_chrome_check_needs_the_extension_to_say_connected(monkeypatch):
    class Out:
        stdout = "[OK] Daemon: running\n[MISSING] Extension: not connected\n"
    monkeypatch.setattr(d.subprocess, "run", lambda *a, **k: Out())
    assert d.chrome_connected() is False
    Out.stdout = "[OK] Extension: connected (v1.0.24)\n"
    assert d.chrome_connected() is True
