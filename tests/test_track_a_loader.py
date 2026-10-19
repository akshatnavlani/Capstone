"""Tests for scripts/_track_a.py.

This shim sits between the training scripts and Track A's canonical
`pair_count`. If it misbehaves the failure shows up as a confusing import error
during a real training run, so the contract is pinned here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from _track_a import (  # noqa: E402
    find_ingestion_dir,
    import_pair_count,
    install_orchestrator_stub,
)


@pytest.fixture(autouse=True)
def _clean_orchestrator():
    """Each test starts without an `orchestrator` module registered."""
    saved = sys.modules.pop("orchestrator", None)
    yield
    sys.modules.pop("orchestrator", None)
    if saved is not None:
        sys.modules["orchestrator"] = saved


def test_stub_exposes_env():
    install_orchestrator_stub({"DATABASE_URL": "postgresql://example"})
    import orchestrator

    assert orchestrator.ENV["DATABASE_URL"] == "postgresql://example"


def test_stub_defaults_to_process_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://from-env")
    install_orchestrator_stub()
    import orchestrator

    assert orchestrator.ENV["DATABASE_URL"] == "postgresql://from-env"


def test_stub_does_not_replace_a_real_orchestrator():
    """Inside Track A's own environment the real module must win.

    `sys.modules.setdefault` is what guarantees this; a plain assignment would
    silently shadow the real orchestrator and change behaviour there.
    """
    import types

    real = types.ModuleType("orchestrator")
    real.ENV = {"DATABASE_URL": "the-real-one"}
    real.marker = "real"
    sys.modules["orchestrator"] = real

    install_orchestrator_stub({"DATABASE_URL": "the-stub"})

    import orchestrator

    assert getattr(orchestrator, "marker", None) == "real"
    assert orchestrator.ENV["DATABASE_URL"] == "the-real-one"


def test_missing_ingestion_dir_raises_with_the_paths_searched():
    """A clear failure beats a silently re-derived pair definition."""
    if find_ingestion_dir() is not None:
        pytest.skip("Track A's ingestion directory is present in this checkout")

    with pytest.raises(ImportError) as excinfo:
        import_pair_count()

    message = str(excinfo.value)
    assert "track-a-data-infra" in message
    assert "Searched:" in message