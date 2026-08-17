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

    # ⚠️ SECOND TIGHTENING, 2026-08-17. Description-corroboration and title-name-matching
    # were BOTH tried as sufficient conditions and BOTH wrote wrong handles at scale
    # (45 written, 45 reverted). Concretely, from the live run:
    #   corroboration-only : fcgoaofficial -> @ubaidmellow (29 subs, no name relationship)
    #                        chennaiipl    -> @chennaiipl-msd (54 subs, a fan channel)
    #                        imbhuvi       -> 0 subs, despite 6.3M Instagram followers
    #   name-match         : _ramandeep.singh_ (a KKR cricketer) -> "AFLM - A venture of
    #                        CS Ramandeep Singh", a coaching institute. A NAMESAKE.
    # A fan channel legitimately references the creator's Instagram, and a namesake
    # legitimately shares the name, so neither signal establishes that a channel is THIS
    # person's official one.
    #
    # AUTO-WRITE now requires the customUrl to be essentially the SAME STRING as the
    # creator's own handle/name, plus real scale. Fans don't get the exact handle, and
    # namesakes rarely match a handle exactly. Everything else is returned for review
    # rather than written -- absence of a confident match is a real finding here.
    name_c = _norm(creator_name).replace(" ", "")
    ig_c = _norm(instagram_handle or "").replace(" ", "")
    url_c = _norm(custom).replace(" ", "")
    if url_c and (url_c == name_c or url_c == ig_c) and subs >= min_subs and not auto_suffix:
        return True, (f"exact handle equality '@{custom}' == creator handle "
                       f"({subs:,} subs)")

    # Everything below is EVIDENCE, not proof -- surfaced for a human, never auto-written.
    hints = []
    if instagram_handle and ig_c and ig_c in _norm(desc).replace(" ", ""):
        hints.append("description references the instagram handle")
    ct, tt = _tokens(creator_name), _tokens(title)
    if ct and tt and (ct & tt):
        hints.append(f"title overlap with '{title}'")
    if hints:
        return False, (f"NEEDS REVIEW: {'; '.join(hints)} — '{title}' (@{custom}, "
                        f"{subs:,} subs). Not auto-written: fan channels and namesakes "
                        f"produce exactly this evidence.")

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
            # youtube_api_get already consumed the stream; it stashes the text on the
            # exception. Falling back to e.read() would return b"" and make every failure
            # look identical (that produced 137 blank "search failed" warnings).
            body = (getattr(e, "body_text", "") or "")[:200]
            if e.code in (403, 429):
                log.error("ALL YouTube keys exhausted (last HTTP %d) — stopping cleanly at "
                           "%d/%d creators. Re-run after the daily reset. %s",
                           e.code, found + absent, len(todo), body[:100])
                break
            log.warning("search failed for %s: HTTP %d %s", name, e.code, body[:120])
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
