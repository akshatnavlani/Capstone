"""Dump the feature-store JSON files that the holdout evaluation and GAIL training need, from the live database, through the backend's own endpoints.

    python scripts/export_feature_store.py <out_dir>

Writes creators.json, collab_edges.json, co_occurrence_edges.json, sponsorship_edges.json, mention_edges.json (@mentions between our creators) and shared_brand_edges.json (creators who promoted the same
brand; added 26 Oct 2026, opt-in for training). Read only. Needs DATABASE_URL in the repo's .env.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
env = (ROOT / ".env").read_text(encoding="utf-8")
for line in env.splitlines():
    if line.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"').replace("postgresql://", "postgresql+psycopg2://")
from ml._scipy_compat import avoid_blocked_scipy_solver  # noqa: E402

avoid_blocked_scipy_solver()
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
for name, path in [("creators.json", "/feature-store/creators"), ("collab_edges.json", "/feature-store/edges/collaborations"),
                   ("co_occurrence_edges.json", "/feature-store/edges/co-occurrence"), ("sponsorship_edges.json", "/feature-store/edges/sponsorships"),
                   ("shared_brand_edges.json", "/feature-store/edges/shared-brand"),
                   ("mention_edges.json", "/feature-store/edges/mentions")]:
    r = client.get(path)
    print(path, r.status_code, flush=True)
    r.raise_for_status()
    data = r.json()
    (OUT / name).write_text(json.dumps(data), encoding="utf-8")
    print("  ", name, "items:", len(data) if isinstance(data, list) else type(data).__name__, flush=True)
