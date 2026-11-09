"""Create a separate database login for a teammate (9 Nov 2026: Eesha and Akshat run the Instagram collection on their own laptops).

    python scripts/admin/create_teammate_login.py eesha

Run it YOURSELF in a terminal: it asks for the new login's password (typed twice, never shown, never saved). Send that password
to the teammate privately (not in a group chat, not in git). They put their own DATABASE_URL in their own .env.

What the login can do: read every table, add and update rows (needed to save Instagram posts, profiles and snapshots),
create a new table (one Instagram script keeps a backup table). What it cannot do: delete rows, empty or drop tables,
change other logins. To remove it later:  drop owned by eesha; drop role eesha;   (run as the admin)
"""
import getpass
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))
from orchestrator import load_env  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z][a-z0-9_]{2,30}", sys.argv[1]):
        print("usage: python scripts/admin/create_teammate_login.py <login name, lower case, e.g. eesha>")
        return 2
    name = sys.argv[1]
    pw = getpass.getpass(f"password for {name} (at least 16 characters): ")
    if len(pw) < 16 or pw != getpass.getpass("type it again: "):
        print("too short or the two did not match; nothing changed")
        return 1
    conn = psycopg2.connect(load_env()["DATABASE_URL"])
    cur = conn.cursor()
    role = sql.Identifier(name)
    cur.execute(sql.SQL("create role {} login password %s").format(role), (pw,))
    cur.execute(sql.SQL("grant connect on database {} to {}").format(sql.Identifier(conn.info.dbname), role))
    cur.execute(sql.SQL("grant usage, create on schema public to {}").format(role))
    cur.execute(sql.SQL("grant select, insert, update on all tables in schema public to {}").format(role))
    cur.execute(sql.SQL("grant usage, select on all sequences in schema public to {}").format(role))
    conn.commit()
    print(f"login '{name}' created: read, add and update rows; no deleting. Send the password privately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
