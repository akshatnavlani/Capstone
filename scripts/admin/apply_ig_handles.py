r"""Writes models/ig_handles_final_11nov.json into creators.instagram_handle (only where it is still empty), after a backup
table creators_ig_handle_backup_20261111. Undo: update creators c set instagram_handle = b.instagram_handle from that table b
where c.creator_id = b.creator_id.

    venv\Scripts\python.exe scripts\admin\apply_ig_handles.py
"""
import json
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from orchestrator import load_env  # noqa: E402

final = json.load(open(ROOT / "models" / "ig_handles_final_11nov.json", encoding="utf-8"))
conn = psycopg2.connect(load_env()["DATABASE_URL"])
cur = conn.cursor()
cur.execute("create table if not exists creators_ig_handle_backup_20261111 as select creator_id, instagram_handle, now() as saved_at from creators where false")
cur.execute("insert into creators_ig_handle_backup_20261111 select creator_id, instagram_handle, now() from creators where creator_id::text = any(%s)", (list(final),))
n = 0
for c, f in final.items():
    cur.execute("update creators set instagram_handle = %s, updated_at = now() where creator_id::text = %s and instagram_handle is null", (f["instagram_handle"], c))
    n += cur.rowcount
conn.commit()
print(f"applied {n} of {len(final)} Instagram handles (backup table creators_ig_handle_backup_20261111)")
