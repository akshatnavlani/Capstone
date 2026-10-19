"""Tests for db_retry.py (no database, no waiting)."""
import psycopg2
import pytest

import db_retry


def test_a_connection_that_works_on_the_third_try_is_returned(monkeypatch):
    monkeypatch.setattr(db_retry.time, "sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise psycopg2.OperationalError("could not translate host name")
        return "connection"

    assert db_retry.connect_with_retry(flaky) == "connection"
    assert len(calls) == 3


def test_it_gives_up_after_the_last_attempt(monkeypatch):
    monkeypatch.setattr(db_retry.time, "sleep", lambda s: None)
    calls = []

    def never():
        calls.append(1)
        raise psycopg2.OperationalError("down")

    with pytest.raises(psycopg2.OperationalError):
        db_retry.connect_with_retry(never, attempts=4)
    assert len(calls) == 4


def test_the_error_text_is_never_logged(monkeypatch, caplog):
    monkeypatch.setattr(db_retry.time, "sleep", lambda s: None)

    def leaky():
        raise psycopg2.OperationalError("postgresql://user:SECRETPASSWORD@host/db failed")

    with caplog.at_level("WARNING"):
        with pytest.raises(psycopg2.OperationalError):
            db_retry.connect_with_retry(leaky, attempts=2)
    assert "SECRETPASSWORD" not in caplog.text
