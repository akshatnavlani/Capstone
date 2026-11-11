"""Per-person Instagram cap (9 Nov 2026): record WHO made each Instagram page load, so each teammate gets their own
130 loads a day instead of sharing one 130.

    python scripts/admin/add_loaded_by_column.py

Run it YOURSELF once (it changes the shared database). Adds one column `loaded_by` (default: the database login that
wrote the row) to post_snapshots and instagram_extra_loads. Existing rows get your admin login. Nothing is changed or
deleted. instagram_daily.py and snapshot_instagram.py then count only the current login's loads (they fall back to the
old shared count while the column is missing). To undo:  alter table post_snapshots drop column loaded_by;
alter table instagram_extra_loads drop column loaded_by;
"""
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))
from orchestrator import load_env  # noqa: E402

conn = psycopg2.connect(load_env()["DATABASE_URL"], connect_timeout=20)
cur = conn.cursor()
cur.execute("set lock_timeout = '20s'")
for table in ("post_snapshots", "instagram_extra_loads"):
    cur.execute(f"alter table {table} add column if not exists loaded_by text default current_user")
conn.commit()
print("done: loaded_by added to post_snapshots and instagram_extra_loads; each login now has its own Instagram cap")
