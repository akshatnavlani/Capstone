"""Google Sheets sync — Track A candidate pipeline (pivot round, 2026-08-10).

Write access needs a GCP service account (the claude.ai Sheets OAuth connector didn't
work, per user direction 2026-08-10). Setup, one-time, done by the user:
  1. console.cloud.google.com -> create/select a project -> enable the Google Sheets API.
  2. IAM & Admin -> Service Accounts -> Create -> any name (e.g. "capstone-sheets-sync").
  3. On that service account: Keys -> Add Key -> Create new key -> JSON. Downloads a file.
  4. Save that file as scripts/ingestion/google-service-account.json (gitignored, never
     committed — same treatment as .env).
  5. Open the file, copy the "client_email" field (looks like
     ...@...iam.gserviceaccount.com). Share the Google Sheet with that email as Editor.

Sync protocol (per PROJECT_PLAN.md/HANDOFF.md): periodic push + read-back, NOT
real-time. push_candidates() appends staged rows with approval_status blank;
read_approval_status() reads the column back to check for new approvals/rejections.
Sheet: https://docs.google.com/spreadsheets/d/1UX9K3gQnh4roMgTi0cy3Sxm82kTLDkZI9w4jJELFVPQ

Columns (live as of 2026-08-10, read from the sheet's real header at call time rather
than hardcoded — see push_candidates): name, approval_status, category, youtube_handle,
instagram_handle, reddit_handles, notes, reddit_topic_subs. creator_id/created_at/
updated_at were removed from the sheet on user instruction (creator_id is a DB-assigned
UUID that doesn't exist until a candidate is actually ingested into the creators table;
timestamps weren't wanted here either) — those fields still exist in the real DB, just
not mirrored in this sheet.
"""

import json
import os

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1UX9K3gQnh4roMgTi0cy3Sxm82kTLDkZI9w4jJELFVPQ"
KEY_PATH = os.path.join(os.path.dirname(__file__), "google-service-account.json")
STAGING_PATH = os.path.join(os.path.dirname(__file__), "candidate_staging.json")

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _client() -> gspread.Client:
    if not os.path.exists(KEY_PATH):
        raise RuntimeError(
            f"No service account key at {KEY_PATH} — see this module's docstring "
            "for the one-time GCP setup steps."
        )
    creds = Credentials.from_service_account_file(KEY_PATH, scopes=_SCOPES)
    return gspread.authorize(creds)


def _worksheet():
    return _client().open_by_key(SHEET_ID).sheet1


def read_rows() -> list[dict]:
    """Full sheet content as a list of dicts, keyed by header row."""
    return _worksheet().get_all_records()


def read_approval_counts() -> dict[str, int]:
    rows = read_rows()
    counts = {"accepted": 0, "rejected": 0, "blank": 0}
    for r in rows:
        status = (r.get("approval_status") or "").strip().lower()
        if status == "accepted":
            counts["accepted"] += 1
        elif status == "rejected":
            counts["rejected"] += 1
        else:
            counts["blank"] += 1
    return counts


def append_brand_signal(instagram_handle: str, signal: str, dry_run: bool = False) -> bool:
    """Append a brand observation to one creator's `brand_signals` cell.

    This is the write side of the standing rule set 2026-08-16: a brand/business account
    must NOT become its own sheet row/candidate; it is recorded against the creator it
    was observed on. Appends (semicolon-separated, deduplicated) rather than replacing,
    since a creator accumulates several brand signals over time.

    Never touches `approval_status`. Returns False if the handle isn't on the sheet or
    the signal is already recorded.
    """
    ws = _worksheet()
    values = ws.get_all_values()
    header = values[0]
    for col in ("brand_signals", "instagram_handle"):
        if col not in header:
            raise RuntimeError(f"sheet header missing `{col}`: {header}")
    bs_col, ig_col = header.index("brand_signals"), header.index("instagram_handle")
    want = instagram_handle.strip().lstrip("@").lower()

    for row_i, row in enumerate(values[1:], start=2):
        if len(row) <= ig_col or (row[ig_col] or "").strip().lstrip("@").lower() != want:
            continue
        current = (row[bs_col] or "").strip() if len(row) > bs_col else ""
        parts = [p.strip() for p in current.split(";") if p.strip()]
        if signal in parts:
            return False
        parts.append(signal)
        new = "; ".join(parts)
        if dry_run:
            print(f"[dry-run] row{row_i} @{want} brand_signals: {current!r} -> {new!r}")
            return True
        col_letter = gspread.utils.rowcol_to_a1(1, bs_col + 1).rstrip("1")
        ws.update(f"{col_letter}{row_i}", [[new]], value_input_option="RAW")
        return True
    return False


def update_category(updates: dict[str, str], dry_run: bool = False) -> int:
    """Rewrite ONLY the `category` cell for the given {instagram_handle: category} rows.

    Built 2026-08-16 to repair 146 accepted rows stuck at category='other'. Deliberately
    narrow, because the failure modes here are expensive and already documented:

      - `approval_status` is the USER's column and must never be written. This targets a
        single named column and asserts it is not approval_status before writing.
      - Row position is resolved by MATCHING THE HANDLE in each row, never by reusing an
        index from get_all_records(). A stale/offset index would silently rewrite a
        different creator's category, which nothing downstream would catch — `category`
        has a CHECK constraint that accepts every value we might wrongly write.
      - Writes go through batch_update on explicit single-cell ranges, avoiding the
        native-Table range bug that silently destroyed a real row (see push_candidates).

    Returns the number of cells written. Unknown handles are reported, not skipped
    silently.
    """
    if not updates:
        return 0
    ws = _worksheet()
    values = ws.get_all_values()
    header = values[0]
    if "category" not in header or "instagram_handle" not in header:
        raise RuntimeError(f"sheet header missing required columns: {header}")
    cat_col = header.index("category")
    ig_col = header.index("instagram_handle")
    if header[cat_col] != "category":
        raise RuntimeError("refusing to write: resolved column is not `category`")

    wanted = {h.strip().lstrip("@").lower(): c for h, c in updates.items()}
    cells, seen = [], set()
    for row_i, row in enumerate(values[1:], start=2):
        if len(row) <= ig_col:
            continue
        h = (row[ig_col] or "").strip().lstrip("@").lower()
        if h not in wanted:
            continue
        new = wanted[h]
        current = (row[cat_col] or "").strip() if len(row) > cat_col else ""
        seen.add(h)
        if current == new:
            continue  # already correct; don't burn a write
        cells.append((row_i, new, h, current))

    missing = set(wanted) - seen
    if missing:
        log_missing = ", ".join(sorted(missing))
        raise RuntimeError(f"handles not found on the sheet, refusing partial write: {log_missing}")

    if dry_run:
        for row_i, new, h, current in cells:
            print(f"[dry-run] row{row_i} @{h}: {current!r} -> {new!r}")
        return len(cells)

    col_letter = gspread.utils.rowcol_to_a1(1, cat_col + 1).rstrip("1")
    body = [{"range": f"{col_letter}{row_i}", "values": [[new]]} for row_i, new, _, _ in cells]
    for i in range(0, len(body), 100):  # chunked: one oversized request can time out
        ws.batch_update(body[i:i + 100], value_input_option="RAW")
    return len(cells)


def push_candidates(rows: list[dict] | None = None) -> int:
    """Append staged candidates (approval_status blank) to the sheet.

    Defaults to reading scripts/ingestion/candidate_staging.json (the local staging
    file discover_candidates.py writes to). Existing instagram_handles already in the
    sheet are skipped so re-running doesn't duplicate rows.
    """
    if rows is None:
        if not os.path.exists(STAGING_PATH):
            return 0
        with open(STAGING_PATH, encoding="utf-8") as f:
            rows = json.load(f)
    if not rows:
        return 0

    ws = _worksheet()
    # Read the REAL header row rather than assuming a fixed column order — a prior
    # round hardcoded an order that didn't match the live sheet (approval_status is
    # the 3rd column, not the last) and silently scrambled 3 pushed rows. Building
    # each row by header name, live, makes that class of bug impossible.
    header = ws.row_values(1)
    existing = {
        (r.get("instagram_handle") or "").lower()
        for r in ws.get_all_records()
        if r.get("instagram_handle")
    }

    to_append = []
    for r in rows:
        handle = (r.get("instagram_handle") or "").lower()
        if handle and handle in existing:
            continue
        row_fields = {}
        row_fields["name"] = r.get("name", "")
        row_fields["category"] = r.get("category", "")
        row_fields["youtube_handle"] = r.get("youtube_handle", "")
        row_fields["instagram_handle"] = r.get("instagram_handle", "")
        row_fields["follower_count"] = r.get("follower_count", "")
        row_fields["reddit_handles"] = json.dumps(r.get("reddit_handles", [])) if r.get("reddit_handles") else "[]"
        row_fields["notes"] = r.get("notes", "")
        row_fields["reddit_topic_subs"] = json.dumps(r.get("reddit_topic_subs", [])) if r.get("reddit_topic_subs") else "[]"
        row_fields["approval_status"] = r.get("approval_status", "")
        # Brands tagged in bio, discount codes, paid-collab language. Free to capture
        # (the bio is already read for the relevance check) and predicts which creators
        # will actually yield sponsorship events.
        row_fields["brand_signals"] = r.get("brand_signals", "")
        missing = [c for c in header if c not in row_fields]
        if missing:
            raise RuntimeError(f"sheet has columns not handled by this script: {missing}")
        to_append.append([row_fields[c] for c in header])

    if to_append:
        # NOT ws.append_rows() -- real data-loss bug found 2026-08-10: once the user
        # converted this range to a native Sheets "Table", the values.append API's
        # auto-detected table range froze at its size when the Table was created
        # (A1:I20) and never grew, even with 32 real rows of data present. Every
        # subsequent append_rows() call landed at row 21 regardless of how much real
        # data already existed below it, silently overwriting whatever was there —
        # confirmed via the raw API response's `tableRange` field, and confirmed it
        # destroyed a real candidate (fit_boult, restored from conversation history).
        # Writing to an EXPLICIT range computed from the actual current row count
        # sidesteps the Table's stale auto-detection entirely.
        next_row = len(ws.get_all_values()) + 1
        last_row = next_row + len(to_append) - 1

        # Grow the grid before writing past it. Found 2026-08-17: the sheet filled to its
        # allocated 995 rows, and every push then failed with
        #   APIError [400]: Range (...!A996:J997) exceeds grid limits. Max rows: 995
        # An explicit-range write does NOT auto-extend the sheet, so discovery had
        # silently stopped being able to add candidates at all.
        if last_row > ws.row_count:
            ws.add_rows(last_row - ws.row_count + 500)   # headroom, not one row at a time

        last_col_letter = gspread.utils.rowcol_to_a1(1, len(header)).rstrip("1")
        ws.update(f"A{next_row}:{last_col_letter}{last_row}", to_append, value_input_option="RAW")
    return len(to_append)


if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "status":
        print(read_approval_counts())
    elif action == "push":
        n = push_candidates()
        print(f"pushed {n} new candidate rows")
    else:
        print("usage: python sheets_sync.py [status|push]")
