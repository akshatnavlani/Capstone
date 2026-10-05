"""The Analysis tab's endpoint: serves the exported file, 404 when it was never generated."""

import json

import pytest
from fastapi import HTTPException

from app.routers import analysis


@pytest.fixture(autouse=True)
def _reset_cache():
    analysis._cache = None
    yield
    analysis._cache = None


def test_serves_the_exported_file(tmp_path, monkeypatch):
    f = tmp_path / "analysis_dashboard.json"
    f.write_text(json.dumps({"s1": {"x": 1}}), encoding="utf-8")
    monkeypatch.setattr(analysis, "ARTIFACT_PATH", f)
    assert analysis.get_analysis() == {"s1": {"x": 1}}


def test_picks_up_a_refreshed_file(tmp_path, monkeypatch):
    import os

    f = tmp_path / "analysis_dashboard.json"
    f.write_text(json.dumps({"v": 1}), encoding="utf-8")
    monkeypatch.setattr(analysis, "ARTIFACT_PATH", f)
    assert analysis.get_analysis() == {"v": 1}
    f.write_text(json.dumps({"v": 2}), encoding="utf-8")
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 5))
    assert analysis.get_analysis() == {"v": 2}


def test_missing_file_is_a_404_with_the_fix_in_the_message(tmp_path, monkeypatch):
    monkeypatch.setattr(analysis, "ARTIFACT_PATH", tmp_path / "nope.json")
    with pytest.raises(HTTPException) as e:
        analysis.get_analysis()
    assert e.value.status_code == 404 and "export_analysis_dashboard" in e.value.detail


def test_corrupt_file_is_a_500(tmp_path, monkeypatch):
    f = tmp_path / "analysis_dashboard.json"
    f.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(analysis, "ARTIFACT_PATH", f)
    with pytest.raises(HTTPException) as e:
        analysis.get_analysis()
    assert e.value.status_code == 500
