"""Find and VERIFY YouTube channels for creators that have no `youtube_handle`.

WHY (P0.5, rescoped 2026-08-18): of 259 creators, 257 have an Instagram handle but only 11
have a YouTube handle. The 240+ creators added by bulk promotion have never had YouTube
attempted, because there was no way to attempt it — `orchestrator.py` can only look a
channel up by an ALREADY-KNOWN handle (`channels?forHandle=`). This module adds the missing
capability: search by name, then verify before writing.

VERIFICATION IS THE POINT, NOT THE SEARCH. This project's standing rule exists because ~4
of 5 guessed handles once resolved to fan/unrelated channels, and a wrong handle pollutes a
real creator's data with a stranger's. So a hit is only written when it passes an explicit
check, and "no confident match" is recorded as a REAL FINDING rather than retried forever —
plenty of these creators genuinely have no channel.

Verification accepts a candidate on either of:
  1. NAME MATCH — normalised token overlap between creator name and channel title.
  2. CROSS-PLATFORM CORROBORATION — the channel's description/customUrl contains the
     creator's known Instagram handle. This is the strongest signal available and is the
     trick that resolved Neeraj Chopra's handle previously (his YouTube listed a management
     contact matching his verified Instagram bio).

QUOTA: search.list costs 100 units against a 10,000/day default; channels.list costs 1.
That caps a day at ~95 searches, so this WILL span several rounds. Progress is checkpointed
per creator and the run stops cleanly on the budget rather than dying mid-batch on a hard
quota error.

Run: python discover_youtube_handles.py [--budget 9000] [--limit N] [--dry-run]
"""

import argparse
import json
import logging
import os
import re
import urllib.error

import psycopg2

from orchestrator import ENV, youtube_api_get

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("yt-discover")

CHECKPOINT = os.path.join(os.path.dirname(__file__), "yt_discovery_checkpoint.json")

SEARCH_COST = 100      # youtube search.list
CHANNELS_COST = 1      # youtube channels.list
DEFAULT_BUDGET = 9000  # leave headroom under the 10,000/day default

_PUNCT = re.compile(r"[^a-z0-9]+")


def _norm(s: str) -> str:
    return _PUNCT.sub(" ", (s or "").lower()).strip()


def _tokens(s: str) -> set[str]:
    return {t for t in _norm(s).split() if len(t) > 2}


def verify(creator_name: str, instagram_handle: str | None, ch: dict,
            min_subs: int = 1000) -> tuple[bool, str]:
    """Is this channel really this creator's? Returns (accepted, reason).

    ⚠️ THE FIRST VERSION OF THIS FUNCTION WAS CIRCULAR AND ACCEPTED JUNK. It searched for
    the Instagram handle across title + description + customUrl combined. But a channel's
    customUrl is DERIVED FROM ITS OWN NAME, so any name-similar channel the search returned
    trivially "corroborated" itself. It accepted, on a 3-creator smoke test:
        __camgreen__   -> @camgreen-to5kr                    (0 subscribers)
        __fitnessspo__ -> @fitnesssport-entrenandoenc6492    (Spanish, unrelated)
    Both were written to the DB and had to be reverted. This is exactly the failure the
    project's "never trust a guessed handle" rule exists for.

    Corroboration now means the handle appears in the DESCRIPTION — free text the channel
    owner wrote — never in the title or customUrl.
    """
    sn = ch.get("snippet", {})
    title = sn.get("title") or ""
    desc = sn.get("description") or ""
    try:
        subs = int(ch.get("statistics", {}).get("subscriberCount") or 0)
    except (TypeError, ValueError):
        subs = 0

    # An auto-generated handle suffix (@name-to5kr, @name6492) means YouTube minted the
    # handle rather than the owner choosing it — a strong negative signal for a real
    # public figure's official channel.
    custom = (sn.get("customUrl") or "").lstrip("@")
    auto_suffix = bool(re.search(r"-[a-z0-9]{5}$|\d{4}$", custom))

    # 1. CROSS-PLATFORM CORROBORATION — description only. This is the trick that resolved
    #    Neeraj Chopra previously (his channel listed a management contact matching his
    #    verified Instagram bio).
    if instagram_handle:
        ig_compact = _norm(instagram_handle).replace(" ", "")
        desc_compact = _norm(desc).replace(" ", "")
        if ig_compact and ig_compact in desc_compact:
            return True, f"cross-platform: description references instagram '{instagram_handle}'"

    # 2. NAME MATCH — requires a real title match AND plausible scale. A public figure with
    #    a genuine channel is not sitting at 0 subscribers.
    ct, tt = _tokens(creator_name), _tokens(title)
    if ct and tt:
        overlap = ct & tt
        # Compact equality catches the very common case where a promoted creator's NAME is
        # their handle: "__devmeena__" vs channel title "Dev Meena" share no whole tokens,
        # but are the same string once separators are removed.
        compact_equal = (_norm(creator_name).replace(" ", "") ==
                          _norm(title).replace(" ", "") != "")
        strong = (overlap == ct or overlap == tt or len(overlap) >= 2 or compact_equal)
        if strong and subs >= min_subs and not auto_suffix:
            return True, (f"name match '{creator_name}' vs '{title}' "
                           f"({subs:,} subs, owner-chosen handle)")
        if strong and (subs < min_subs or auto_suffix):
            return False, (f"name matched '{title}' but REJECTED: "
                            f"{subs} subs{', auto-generated handle' if auto_suffix else ''}")

    return False, f"no confident match (best candidate '{title}', {subs} subs)"


def load_ckpt() -> dict:
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_ckpt(d: dict) -> None:
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                     help="Quota units to spend this run (search=100, channels=1).")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("""
            select creator_id, name, instagram_handle
            from creators
            where youtube_handle is null
            order by name
        """)
        todo = cur.fetchall()

    ckpt = load_ckpt()
    todo = [t for t in todo if str(t[0]) not in ckpt]
    if args.limit:
        todo = todo[: args.limit]
    log.info("creators without youtube_handle and unchecked: %d (checkpoint has %d)",
              len(todo), len(ckpt))

    spent = found = absent = 0
    for cid, name, ig in todo:
        if spent + SEARCH_COST + CHANNELS_COST > args.budget:
            log.warning("quota budget reached (%d units spent) — stopping cleanly. "
                         "Re-run next round to continue.", spent)
            break
        if args.dry_run:
            log.info("[dry-run] would search '%s' (ig=%s)", name, ig)
            continue

        try:
            res = youtube_api_get("search", q=name, type="channel", part="snippet",
                                   maxResults="3")
            spent += SEARCH_COST
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            if e.code == 403 and "quota" in body.lower():
                log.error("QUOTA EXHAUSTED mid-run — stopping. %s", body[:120])
                break
            log.warning("search failed for %s: %s", name, body[:120])
            continue
        except Exception as e:
            log.warning("search error for %s: %s", name, e)
            continue

        items = res.get("items", [])
        if not items:
            ckpt[str(cid)] = {"name": name, "result": "no_channel_found",
                               "reason": "search returned no channels"}
            absent += 1
            save_ckpt(ckpt)
            log.info("ABSENT %s — search returned nothing", name)
            continue

        # Pull full snippets for the candidates so verification sees description/customUrl,
        # which the search result does not include.
        ids = ",".join(i["id"]["channelId"] for i in items if i.get("id", {}).get("channelId"))
        try:
            det = youtube_api_get("channels", id=ids, part="snippet,statistics")
            spent += CHANNELS_COST
        except Exception as e:
            log.warning("channels lookup failed for %s: %s", name, e)
            continue

        accepted = None
        for ch in det.get("items", []):
            ok, reason = verify(name, ig, ch)
            if ok:
                accepted = (ch, reason)
                break

        if not accepted:
            best = (det.get("items") or [{}])[0].get("snippet", {}).get("title", "?")
            ckpt[str(cid)] = {"name": name, "result": "no_confident_match",
                               "reason": f"candidates rejected, best='{best}'"}
            absent += 1
            save_ckpt(ckpt)
            log.info("REJECT %s — no confident match (best '%s')", name, best)
            continue

        ch, reason = accepted
        handle = (ch["snippet"].get("customUrl") or "").lstrip("@")
        if not handle:
            ckpt[str(cid)] = {"name": name, "result": "no_confident_match",
                               "reason": "verified channel has no customUrl handle"}
            absent += 1
            save_ckpt(ckpt)
            continue

        with conn.cursor() as cur:
            # Unique partial index on youtube_handle: never steal one already assigned.
            cur.execute("select name from creators where youtube_handle = %s and creator_id <> %s",
                         (handle, cid))
            clash = cur.fetchone()
            if clash:
                ckpt[str(cid)] = {"name": name, "result": "handle_clash",
                                   "reason": f"'{handle}' already belongs to {clash[0]}"}
                absent += 1
                save_ckpt(ckpt)
                log.warning("CLASH %s -> @%s already assigned to %s", name, handle, clash[0])
                continue
            cur.execute("update creators set youtube_handle = %s, updated_at = now() "
                         "where creator_id = %s", (handle, cid))
        conn.commit()
        ckpt[str(cid)] = {"name": name, "result": "found", "handle": handle,
                           "subs": ch.get("statistics", {}).get("subscriberCount"),
                           "reason": reason}
        save_ckpt(ckpt)
        found += 1
        log.info("FOUND %s -> @%s (%s subs) [%s]", name, handle,
                  ch.get("statistics", {}).get("subscriberCount", "?"), reason)

    conn.close()
    log.info("DONE found=%d absent_or_rejected=%d quota_spent=%d of %d budget",
              found, absent, spent, args.budget)


if __name__ == "__main__":
    main()
