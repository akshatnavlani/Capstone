"""Import Track A's canonical `pair_count` without its browser tooling.

WHY THIS EXISTS. `pair_count.py` is Track A's single source of truth for what
counts as a computable (event, neighbour) training pair, and both
`train_prod_model.py` and `compute_training_pair_deltas.py` import it rather
than re-deriving that definition. Duplicating it would be the exact drift A1
removed between `ml/` and `backend/app/gail/`.

The obstacle: `pair_count` does `from orchestrator import ENV`, and importing
`orchestrator` raises `RuntimeError: opencli not found on PATH` — it is the
ingestion orchestrator and wants the Instagram browser-automation tool present
at import time. Counting pairs needs none of that; it needs one connection
string.

`pair_count` uses `ENV` in exactly one place:

    conn = psycopg2.connect(ENV["DATABASE_URL"])

So this module registers a stand-in `orchestrator` holding just that mapping,
then imports the real `pair_count` unchanged. The pair-counting LOGIC is still
Track A's and still canonical; only the unrelated import is satisfied locally.

`sys.modules.setdefault` is deliberate: if a caller has already imported the
real orchestrator (running inside Track A's own environment, with opencli
present), that one wins and this module changes nothing.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path


def _candidate_ingestion_dirs(start: Path) -> list[Path]:
    """Places Track A's ingestion package may live, most expected first.

    The sibling-worktree layout is what the training scripts were written
    against; the in-repo path covers a checkout where the directory was copied
    alongside this branch's own scripts.
    """
    repo_root = start.resolve().parents[1]
    return [
        repo_root.parent / "track-a-data-infra" / "scripts" / "ingestion",
        repo_root / "scripts" / "ingestion",
    ]


def find_ingestion_dir(start: Path | None = None) -> Path | None:
    """First candidate directory that actually contains `pair_count.py`."""
    start = start or Path(__file__)
    for candidate in _candidate_ingestion_dirs(start):
        if (candidate / "pair_count.py").exists():
            return candidate
    return None


def install_orchestrator_stub(env: dict | None = None) -> None:
    """Register a minimal `orchestrator` module exposing only `ENV`.

    Args:
        env: the mapping `pair_count` will read `DATABASE_URL` from. Defaults
            to the process environment, which the training scripts have already
            populated from their own `.env` loading by the time this runs.
    """
    stub = types.ModuleType("orchestrator")
    stub.ENV = dict(env if env is not None else os.environ)
    stub.__doc__ = (
        "Stand-in installed by scripts/_track_a.py so Track A's pair_count can "
        "be imported without the ingestion orchestrator's browser tooling. "
        "Exposes ENV only."
    )
    sys.modules.setdefault("orchestrator", stub)


def import_pair_count(env: dict | None = None):
    """Return Track A's canonical `pair_count` module.

    Raises:
        ImportError: when the ingestion directory cannot be found, with the
            paths that were searched. A clear failure here is better than a
            silently re-derived pair definition, which is how the two tracks
            would drift apart.
    """
    ingestion_dir = find_ingestion_dir()
    if ingestion_dir is None:
        searched = "\n  ".join(str(p) for p in _candidate_ingestion_dirs(Path(__file__)))
        raise ImportError(
            "Track A's pair_count.py was not found. Clone the track-a-data-infra "
            "branch as a sibling of this repository:\n\n"
            "  git clone -b track-a-data-infra <repo-url> track-a-data-infra\n\n"
            f"Searched:\n  {searched}"
        )

    install_orchestrator_stub(env)
    if str(ingestion_dir) not in sys.path:
        sys.path.insert(0, str(ingestion_dir))

    import pair_count  # noqa: E402  (path must be set up first)

    return pair_count