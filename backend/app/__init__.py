"""Backend app package.

A1 dedup (2026-09-24): `ml/` at the repo root is the single source for GAIL
code — the old `app.gail` vendored copy is deleted. This shim puts the repo
root on `sys.path` so `import ml.*` works whether the server runs from
`backend/` (`uvicorn app.main:app`) or repo root. Deploy/build context must
include repo-root `ml/` + `models/gail_checkpoint.pt`; without them the
spillover service falls back to placeholder by design (never crashes).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if (_REPO_ROOT / "ml").is_dir() and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
