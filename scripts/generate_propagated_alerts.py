"""Turn propagated sentiment risk into risk alerts (PendingWork S1 output
contract: populate risk_alerts.propagated_from_creator_id).

DRY RUN BY DEFAULT: reads the database and prints the alerts it would create;
writes nothing. Pass --write to insert them into riskalert (shared Supabase
data, so only do that on purpose). Already-open alerts with the same creator,
source creator and source are skipped, so re-running does not duplicate.

Only the top --top-percent (default 10%) of creators by propagated risk are
alerted; propagated risk is small in absolute terms, so alerting everyone who
receives any would be noise. Severity is relative within that group: top third
"high", middle third "medium", the rest "low".

Usage (repo root, venv active):
    python scripts/generate_propagated_alerts.py
    python scripts/generate_propagated_alerts.py --write
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from sqlmodel import Session, create_engine, select  # noqa: E402

from app.models import Creator, RiskAlert  # noqa: E402
from app.temporal import compute_temporal  # noqa: E402

SOURCE = "sentiment_propagation"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
        url = re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    return url


def severity_labels(values: list[float]) -> list[str]:
    lo, hi = np.percentile(values, [100 / 3, 200 / 3])
    return ["high" if v >= hi else "medium" if v >= lo else "low" for v in values]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="insert the alerts (default: preview only)")
    ap.add_argument("--top-percent", type=float, default=10.0,
                    help="only alert creators in the top N%% by propagated risk (propagated risk is small "
                         "in absolute terms, so alerting everyone who receives any would be noise)")
    args = ap.parse_args()

    engine = create_engine(database_url())
    with Session(engine) as session:
        temporal = compute_temporal(session)
        if not temporal:
            print("no temporal results (is models/temporal_sentiment.json present?)")
            return
        names = {str(c.creator_id): c.name for c in session.exec(select(Creator)).all()}
        rows = [t for t in temporal.values() if t["source_creator_id"] and t["propagated_risk"] > 0]
        rows.sort(key=lambda t: t["propagated_risk"], reverse=True)
        print(f"{len(rows)} creators receive propagated risk")
        if not rows:
            return
        cutoff = float(np.percentile([t["propagated_risk"] for t in rows], 100 - args.top_percent))
        rows = [t for t in rows if t["propagated_risk"] >= cutoff]
        print(f"alerting the top {args.top_percent:g}%: {len(rows)} creators (propagated risk >= {cutoff:.3f})")

        severities = severity_labels([t["propagated_risk"] for t in rows])
        existing = {
            (str(a.creator_id), str(a.propagated_from_creator_id))
            for a in session.exec(
                select(RiskAlert).where(RiskAlert.resolved == False, RiskAlert.source == SOURCE)  # noqa: E712
            ).all()
        }

        to_add = []
        for t, sev in zip(rows, severities):
            if (t["creator_id"], t["source_creator_id"]) in existing:
                continue
            src_name = names.get(t["source_creator_id"], t["source_creator_id"])
            reason = (
                f"Risk propagated from {src_name}: collaborator audience sentiment is negative "
                f"(propagated risk {t['propagated_risk']:.2f})."
            )
            to_add.append(RiskAlert(
                creator_id=t["creator_id"], severity=sev, reason=reason,
                source=SOURCE, propagated_from_creator_id=t["source_creator_id"],
            ))
            print(f"  [{sev:6}] {names.get(t['creator_id'], t['creator_id'])}  <-  {src_name}")

        print(f"\n{len(to_add)} new alerts ({len(rows) - len(to_add)} already open)")
        if args.write and to_add:
            session.add_all(to_add)
            session.commit()
            print("written to riskalert")
        elif to_add:
            print("preview only; re-run with --write to insert")


if __name__ == "__main__":
    main()
