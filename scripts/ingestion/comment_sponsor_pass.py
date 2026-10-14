"""Label videos as sponsored from the CREATOR'S OWN comment (a pinned or first comment often holds the sponsor and code).

    python comment_sponsor_pass.py --dry-run     # list what it would label, write nothing
    python comment_sponsor_pass.py               # label them (backup rows go to youtube_videos_sponsor_backup_20261012)

A video is labelled only when (a) the comment is written by the channel's own account, (b) it names a KNOWN brand together
with a code or @mention (known_brands.all_strong_brands), and (c) the video is not already marked sponsored. The label gets
evidence type 'creator_comment' and the raw match 'comment:brand:NAME(signals)'. Never flips a true to false. Safe to re-run.
"""

import argparse
import json
import re

from known_brands import all_strong_brands
from sponsorship_detector import BOILERPLATE_MIN_REPEATS, normalize_line


def is_owner(author: str | None, channel_handle: str | None, channel_title: str | None) -> bool:
    """True when the comment's author name is the channel's own handle or title (spaces and case ignored)."""
    a = re.sub(r"\s+", "", (author or "").lstrip("@")).lower()
    if not a:
        return False
    return a in {re.sub(r"\s+", "", (channel_handle or "").lstrip("@")).lower(),
                 re.sub(r"\s+", "", (channel_title or "")).lower()} - {""}


def comment_evidence(text: str | None) -> list[str]:
    """['comment:brand:NAME(signals)', ...] for the known brands the comment clearly promotes."""
    return [f"comment:brand:{m.name}({'+'.join(m.signals)})" for m in all_strong_brands(text)]


def standing_keys(owner_comments: list[tuple]) -> set[tuple]:
    """(creator_id, normalised text) of owner comments repeated on BOILERPLATE_MIN_REPEATS or more videos: a standing
    comment pasted on every upload, not about one video (the same rule as description footers)."""
    seen: dict[tuple, set] = {}
    for creator_id, video_id, text in owner_comments:
        seen.setdefault((creator_id, normalize_line(text or "")), set()).add(video_id)
    return {k for k, vids in seen.items() if len(vids) >= BOILERPLATE_MIN_REPEATS}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    from orchestrator import get_connection, log
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""select c.comment_id, c.video_id, c.author_handle, c.text, yc.channel_handle, yc.title, v.creator_id, v.brand_id, v.is_sponsored
                       from youtube_comments c join youtube_videos v on v.video_id = c.video_id join youtube_channels yc on yc.channel_id = v.channel_id
                       where v.is_sponsored is not true and c.text ~* '(code|coupon|discount|promo|@)'""")
        rows = cur.fetchall()
        cur.execute("select lower(name), brand_id from brands"); brand_ids = dict(cur.fetchall())
        cur.execute("select verification_id, creator_id from creator_verification where creator_id is not null"); ver = {c: v for v, c in cur.fetchall()}
        found: dict[str, tuple] = {}
        owner_rows = [r for r in rows if is_owner(r[2], r[4], r[5])]
        standing = standing_keys([(r[6], r[1], r[3]) for r in owner_rows])
        log.info("%d owner comments with a code word; %d distinct standing comments ignored", len(owner_rows), len(standing))
        for _cid, video_id, author, text, handle, title, creator_id, brand_id, _sp in owner_rows:
            if video_id in found or (creator_id, normalize_line(text or "")) in standing:
                continue
            ev = comment_evidence(text)
            if ev:
                found[video_id] = (ev, creator_id, brand_id)
        log.info("%d videos would be labelled from the creator's own comment", len(found))
        if args.dry_run:
            for vid, (ev, _c, _b) in list(found.items())[:15]:
                log.info("  %s %s", vid, ev)
            return
        for vid, (ev, creator_id, brand_id) in found.items():
            name = re.search(r"brand:([^()]+)\(", ev[0]).group(1)
            bid = brand_id or brand_ids.get(name.lower())
            cur.execute("insert into youtube_videos_sponsor_backup_20261012 (video_id, old_is_sponsored, old_raw, old_brand_id) "
                        "select video_id, is_sponsored, sponsorship_raw_matches, brand_id from youtube_videos where video_id=%s on conflict do nothing", (vid,))
            cur.execute("update youtube_videos set is_sponsored=true, sponsorship_raw_matches=%s::jsonb, sponsorship_evidence='creator_comment', "
                        "brand_id=coalesce(brand_id, %s) where video_id=%s and is_sponsored is not true", (json.dumps(ev), bid, vid))
            v = ver.get(creator_id)
            if v and bid:
                cur.execute("insert into creator_brand_links (verification_id, creator_id, brand_id, platform, evidence, source) values (%s,%s,%s,'youtube',%s,"
                            "'creator comment pass') on conflict (verification_id, brand_id) do nothing", (v, creator_id, bid, f"{ev[0]} on video {vid}"))
        conn.commit()
        log.info("labelled %d videos (evidence type creator_comment)", len(found))


if __name__ == "__main__":
    main()
