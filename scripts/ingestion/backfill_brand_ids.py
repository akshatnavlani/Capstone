"""Close the brand_id gap on confirmed sponsorship events (Phase 1E, P0.4-adjacent).

WHY THIS MATTERS MORE THAN THE ROW COUNT SUGGESTS: GAIL's training pairs come from the
`creator_sponsorship_events` view, which carries `brand_id`. Track C's labeling round
produced the project's first real `is_sponsored=true` events (0 -> 11), but only ONE had
`brand_id` set — so Track B would see 1 usable training pair, not 11. Closing this is the
difference between "we finally have treatment labels" and "the model can use them."

WHY THE EXISTING EXTRACTOR MISSED THEM (diagnosed, not assumed): brand_extraction.py
matches explicit disclosure PHRASES — "in partnership with", "sponsored by", "joined
hands with". Every one of the 10 unlinked events instead discloses via a BRANDED HASHTAG
(#Airtel, #Milton, #CadburyCelebrations, #AmazonPrime, #VisitDubai, #BGMI) or an
@mention (@ewc_en). That pattern is dominant in this dataset and the extractor had no
rule for it at all.

PRECISION DISCIPLINE: `is_sponsored` + `brand_id` is the sole treatment-label source for
the entire causal model (PROJECT_PLAN §1 calls it precision-critical), so this script
does NOT auto-write whatever a regex proposes. It proposes candidates, and a human-
reviewed decision table below records what was actually verified against the full caption
text. Two events are deliberately left UNLINKED rather than guessed:

  - DWTx3_MERRb — full caption is 56 chars: "Take it slow. Go with the Flo #ad". The only
    hashtag is #ad. "Flo" may be a brand or may be wordplay on "flow". Not resolvable
    from the text, so not guessed.
  - DUkDWOYiL8x — caption is EMPTY (0 chars); the event was labelled purely from
    Instagram's native paid-partnership label. There is no disclosure text to extract a
    brand from at all.

Both are reported as remaining gaps rather than silently skipped.

Run: python backfill_brand_ids.py [--dry-run]
"""

import argparse
import logging
import os
import re

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("brandfill")

# Generic disclosure / campaign-slogan tags that are never the sponsoring brand. Kept
# explicit so the exclusions are auditable rather than buried in a scoring function.
_GENERIC_TAGS = {
    "ad", "ads", "sponsored", "sponsorship", "paidpartnership", "paidpromotion",
    "collab", "collaboration", "gifted", "partner", "partnership",
    "madeinindia", "proudlyindian", "byindians", "forindians", "brotherswhocare",
    "playnow", "theninjashot", "samedaydelivery", "explore", "reels", "p",
}


def propose_brand_candidates(caption: str) -> list[str]:
    """Branded-hashtag / @mention candidates, ordered by corroboration strength.

    A candidate corroborated by the caption BODY (the brand name also appears as plain
    prose, e.g. "celebrate that spirit with Milton" alongside #Milton) is ranked first —
    that co-occurrence is the strongest cheap signal that the token is a real brand and
    not a campaign slogan.
    """
    if not caption:
        return []
    tags = [t for t in re.findall(r"\[#([A-Za-z0-9_]+)\]", caption)]
    mentions = re.findall(r"\[@([A-Za-z0-9_.\\]+)\]", caption)
    body = re.sub(r"\[#[^\]]*\]\([^)]*\)|\[@[^\]]*\]\([^)]*\)", " ", caption)

    cands, seen = [], set()
    for tok in mentions + tags:
        clean = tok.replace("\\", "").strip(".")
        key = clean.lower()
        if not clean or key in _GENERIC_TAGS or key in seen:
            continue
        seen.add(key)
        corroborated = re.search(re.escape(clean.rstrip("s")), body, re.I) is not None
        cands.append((0 if corroborated else 1, clean))
    return [c for _, c in sorted(cands, key=lambda x: x[0])]


# HUMAN-REVIEWED decisions. Each entry was checked against the FULL caption printed from
# the live DB before being written — not accepted from the proposer blindly. `None` means
# deliberately left unlinked (see module docstring).
REVIEWED: dict[str, str | None] = {
    "DZcZ5WJP-_M": "Amazon Prime",       # body: "Amazon Prime's Same-day Delivery" + #AmazonPrime
    "DMz4U4HtLgt": "Cadbury",            # #CadburyCelebrations (campaign tag for Cadbury)
    "DXY4y65Ee69": "Airtel",             # #Airtel + #AirtelSafeNetwork + #AirtelOTPAlert
    "DYUY7aSxVdh": "BGMI",               # body: "BGMI 4.4 Update" + #BGMI + #BGMIxBhuvanBam
    "DbDp7T4olyC": "Esports World Cup",  # body names it; @ewc_en is its official account
    "Dbf3uELhR7a": "Milton",             # body: "celebrate that spirit with Milton, a brand" + #Milton
    "DTzVFyJCBof": "Visit Dubai",        # #VisitDubai, body about Dubai throughout
    "DLrSRdqTcEQ": "Visit Dubai",        # #VisitDubai, same campaign
    "DWTx3_MERRb": None,                 # "Go with the Flo" — ambiguous, NOT guessed
    "DUkDWOYiL8x": None,                 # empty caption, native label only — nothing to extract
}


def load_env():
    env = dict(os.environ)
    with open(os.path.join(os.path.dirname(__file__), "..", "..", ".env"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k, v)
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    env = load_env()
    conn = psycopg2.connect(env["DATABASE_URL"])

    with conn.cursor() as cur:
        cur.execute("select count(*) filter (where is_sponsored), "
                     "count(*) filter (where is_sponsored and brand_id is not null) "
                     "from instagram_posts")
        total, before = cur.fetchone()
        cur.execute("select count(*) from brands")
        brands_before = cur.fetchone()[0]
    log.info("BEFORE: %d/%d sponsored events have brand_id; brands table=%d rows",
              before, total, brands_before)

    linked = skipped = 0
    with conn.cursor() as cur:
        cur.execute("select post_id, caption from instagram_posts "
                     "where is_sponsored and brand_id is null")
        rows = cur.fetchall()

        for post_id, caption in rows:
            proposed = propose_brand_candidates(caption or "")
            decision = REVIEWED.get(post_id, "__UNREVIEWED__")

            if decision == "__UNREVIEWED__":
                # New event appeared since review — do NOT auto-write it. Precision-
                # critical field; surface it for a human pass instead.
                log.warning("%s: NOT in reviewed set (proposed=%s) — left unlinked, needs review",
                             post_id, proposed[:3])
                skipped += 1
                continue
            if decision is None:
                log.info("%s: deliberately unlinked (proposed=%s)", post_id, proposed[:3])
                skipped += 1
                continue

            if args.dry_run:
                log.info("[dry-run] %s -> %r (proposer said %s)", post_id, decision, proposed[:3])
                linked += 1
                continue

            # brands.name is UNIQUE; source stays the documented default
            # 'sponsorship_mention' since these come from disclosure text on creator
            # content, not from independent brand discovery.
            cur.execute(
                "insert into brands (name) values (%s) "
                "on conflict (name) do update set updated_at = now() returning brand_id",
                (decision,),
            )
            brand_id = cur.fetchone()[0]
            cur.execute("update instagram_posts set brand_id=%s where post_id=%s",
                         (brand_id, post_id))
            conn.commit()
            linked += 1
            log.info("%s -> brand %r (brand_id=%s)", post_id, decision, str(brand_id)[:8])

    with conn.cursor() as cur:
        cur.execute("select count(*) filter (where is_sponsored), "
                     "count(*) filter (where is_sponsored and brand_id is not null) "
                     "from instagram_posts")
        total_a, after = cur.fetchone()
        cur.execute("select count(*) from brands")
        brands_after = cur.fetchone()[0]
    conn.close()
    log.info("AFTER: %d/%d sponsored events have brand_id (was %d); brands=%d (was %d); "
              "linked=%d deliberately_unlinked=%d",
              after, total_a, before, brands_after, brands_before, linked, skipped)


if __name__ == "__main__":
    main()
