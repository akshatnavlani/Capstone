"""Push co-author candidates from `coauthor_checkpoint.json` to the sheet.

WHY (2026-08-17): `collab_edges.py` flushes EDGES per post, but its co-author sheet push
runs once at the END of the run. Two runs were killed externally tonight, and both times
the edges survived while the sheet push never executed — so every co-author those runs
discovered stayed stranded on disk. The push also reads its in-memory `observed_coauthors`
rather than the checkpoint, so a later run does NOT pick the stranded ones up: they are
invisible to every subsequent run.

This makes that work recoverable. It is a RECOVERY path, not a second implementation —
it reuses the existing pieces exactly as they are:
    account_classify.classify_handle()   category + brand verdict + grid relevance
    sheets_sync.append_brand_signal()     brand routing
    sheets_sync.push_candidates()         the write itself (already dedups on handle)

Safe to re-run: push_candidates skips handles already on the sheet, and creators are
skipped outright. approval_status is left blank — it is the user's column.

Run: python push_checkpoint_candidates.py [--dry-run] [--limit N]
"""

import argparse
import json
import logging
import os

import psycopg2

import account_classify
import sheets_sync
from orchestrator import ENV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ckpt-push")

CHECKPOINT = os.path.join(os.path.dirname(__file__), "coauthor_checkpoint.json")
MAX_CONSEC_UNREACHABLE = 5


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    with open(CHECKPOINT, encoding="utf-8") as f:
        checkpoint = json.load(f)

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("select lower(instagram_handle) from creators where instagram_handle is not null")
        creators = {r[0] for r in cur.fetchall()}
    known_orgs = account_classify.load_known_orgs(conn)
    conn.close()

    on_sheet = {(r.get("instagram_handle") or "").strip().lstrip("@").lower()
                for r in sheets_sync.read_rows()}

    pending = {h: occ for h, occ in checkpoint.items()
               if h.lower() not in creators and h.lower() not in on_sheet}
    log.info("checkpoint=%d  already creators/on sheet=%d  PENDING=%d",
              len(checkpoint), len(checkpoint) - len(pending), len(pending))
    if args.limit:
        pending = dict(sorted(pending.items())[: args.limit])

    rows_out, brands, consec = [], [], 0
    for h, occurrences in sorted(pending.items()):
        owner, post_id = occurrences[0]
        provenance = (f"co-author of @{owner} on post {post_id}"
                       + (f" (+{len(occurrences)-1} more collab posts)"
                          if len(occurrences) > 1 else ""))
        if args.dry_run:
            log.info("[dry-run] would classify+push %s (%s)", h, provenance)
            continue
        try:
            a = account_classify.classify_handle(h, known_orgs)
        except Exception as e:
            log.warning("classify failed for %s: %s", h, e)
            a = {"reachable": False, "category": "other", "evidence": f"classify error: {e}",
                 "relevance_ratio": 0.0, "relevant": 0, "total": 0, "followers": "", "name": h}

        consec = 0 if a.get("reachable") else consec + 1
        if consec >= MAX_CONSEC_UNREACHABLE:
            log.warning("%d consecutive unreachable profiles — stopping and pushing what is "
                         "classified so far (re-run to continue).", consec)
            break

        if a["category"] == account_classify.BRAND:
            try:
                ok = sheets_sync.append_brand_signal(
                    owner, f"{h} — {a['evidence']}; seen as co-author on {post_id}")
                brands.append(h)
                log.info("BRAND %s -> brand_signals of @%s (%s)", h, owner,
                          "written" if ok else "already present / owner not on sheet")
            except Exception as e:
                log.warning("brand_signals write failed for %s: %s", h, e)
            continue

        rel = (f"; grid relevance {a['relevant']}/{a['total']} ({a['relevance_ratio']:.0%})"
               if a["total"] else "; grid relevance unavailable")
        rows_out.append({
            "name": a.get("name") or h,
            "instagram_handle": h,
            "category": a["category"],
            "follower_count": a.get("followers") or "",
            "notes": f"{provenance}{rel}; category: {a['evidence']} [recovered from checkpoint]",
            "brand_signals": "",
            "approval_status": "",
        })

    if args.dry_run:
        log.info("[dry-run] %d candidates would be processed", len(pending))
        return
    pushed = sheets_sync.push_candidates(rows_out) if rows_out else 0
    log.info("DONE pushed=%d brands_routed=%d classified=%d",
              pushed, len(brands), len(rows_out) + len(brands))


if __name__ == "__main__":
    main()
