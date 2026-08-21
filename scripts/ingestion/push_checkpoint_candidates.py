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

# Handles already identified as brands. Brands deliberately never get a sheet row, so
# NOTHING else records that they were dealt with -- without this they stay "pending"
# forever and every subsequent batch re-fetches, re-classifies and re-writes the same
# brand signal. Observed live: batch 3 re-routed five brands batch 2 had already done,
# ~13s of Instagram traffic each, for zero new information.
ROUTED_BRANDS = os.path.join(os.path.dirname(__file__), "routed_brands.json")


def _load_routed() -> set[str]:
    if os.path.exists(ROUTED_BRANDS):
        with open(ROUTED_BRANDS, encoding="utf-8") as f:
            return {h.lower() for h in json.load(f)}
    return set()


def _save_routed(routed: set[str]) -> None:
    with open(ROUTED_BRANDS, "w", encoding="utf-8") as f:
        json.dump(sorted(routed), f, indent=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--from-db", action="store_true",
                     help="Source candidates from creator_related_accounts instead of the "
                          "checkpoint file. STRONGLY PREFERRED: the checkpoint is REWRITTEN "
                          "per run, not accumulated, so a run that completes silently "
                          "discards the co-authors an earlier killed run found. The DB rows "
                          "are flushed per post and never overwritten, so they are the only "
                          "durable record. Found 181 recoverable handles this way vs 63 in "
                          "the checkpoint.")
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    if args.from_db:
        with conn.cursor() as cur:
            cur.execute("""
                select lower(x.handle), min(a.instagram_handle), count(*)
                from creator_related_accounts x
                join creators a on a.creator_id = x.creator_id
                group by lower(x.handle)
            """)
            # shape matches the checkpoint: {handle: [(owner, post_id), ...]}
            checkpoint = {h: [(owner, "")] * n for h, owner, n in cur.fetchall()}
    else:
        with open(CHECKPOINT, encoding="utf-8") as f:
            checkpoint = json.load(f)

    with conn.cursor() as cur:
        cur.execute("select lower(instagram_handle) from creators where instagram_handle is not null")
        creators = {r[0] for r in cur.fetchall()}
    known_orgs = account_classify.load_known_orgs(conn)
    conn.close()

    on_sheet = {(r.get("instagram_handle") or "").strip().lstrip("@").lower()
                for r in sheets_sync.read_rows()}

    routed = _load_routed()
    pending = {h: occ for h, occ in checkpoint.items()
               if h.lower() not in creators and h.lower() not in on_sheet
               and h.lower() not in routed}
    log.info("checkpoint=%d  already creators/on sheet=%d  already-routed brands=%d  PENDING=%d",
              len(checkpoint), len(checkpoint) - len(pending) - len(routed), len(routed),
              len(pending))
    if args.limit:
        pending = dict(sorted(pending.items())[: args.limit])

    rows_out, brands, consec = [], [], 0
    for h, occurrences in sorted(pending.items()):
        owner, post_id = occurrences[0]
        provenance = (f"co-author of @{owner}" + (f" on post {post_id}" if post_id else "")
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
                    owner, f"{h} — {a['evidence']}; seen as co-author of @{owner}")
                brands.append(h)
                routed.add(h.lower())
                _save_routed(routed)      # persist immediately, not at end of run
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
