"""Read-only endpoint behind the dashboard's Analysis tab.

Serves models/analysis_dashboard.json, written by scripts/export_analysis_dashboard.py from the
saved results of the S1, S3, S7 and S8 analyses plus the data the interactive charts need. Rerun the
export script to refresh it. Nothing here touches the database.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/analysis", tags=["analysis"])

ARTIFACT_PATH = Path(__file__).resolve().parents[3] / "models" / "analysis_dashboard.json"

_cache: tuple[float, dict] | None = None


@router.get("")
def get_analysis() -> dict:
    global _cache
    try:
        mtime = ARTIFACT_PATH.stat().st_mtime
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="analysis data not generated: run scripts/export_analysis_dashboard.py")
    if _cache is None or _cache[0] != mtime:
        try:
            _cache = (mtime, json.loads(ARTIFACT_PATH.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as e:
            raise HTTPException(status_code=500, detail=f"analysis data unreadable: {e}")
    return _cache[1]
