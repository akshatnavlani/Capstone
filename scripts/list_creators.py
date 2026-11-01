"""Write every creator to data/creator_list.csv for a manual scope review.

Use it to mark creators who are outside the project's scope (e.g. not Indian):
copy their names into data/creator_scope_overrides.csv with include=no. The
training script then never MEASURES them (as exposed observations or
controls). They stay in the graph, so everyone else's exposure is unchanged.

READ-ONLY on the database. Run from the repo root:
    python scripts/list_creators.py
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import psycopg2

REPO = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    path = REPO / ".env"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)


def main() -> int:
    _load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set. See .env in the repo root.")
        return 1
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute(
        "select name, category, youtube_handle, instagram_handle from creators order by name"
    )
    rows = cur.fetchall()
    conn.close()
    out = REPO / "data" / "creator_list.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "category", "youtube_handle", "instagram_handle"])
        w.writerows(rows)
    print(f"Wrote {len(rows)} creators to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
