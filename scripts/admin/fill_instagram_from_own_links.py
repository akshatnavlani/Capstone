"""Fill missing creators.instagram_handle from the creator's OWN YouTube links (11 Nov 2026).

A handle is taken only when it is the creator's own link: it appears in their channel description, or in >= 3 of their
own video descriptions AND is >= 60% of all instagram.com links in those descriptions (so sponsor / guest links lose).
Handles already held by another creator are skipped. Only creators in scope with no Instagram handle are touched.

    python scripts/admin/fill_instagram_from_own_links.py            # dry run: writes models/ig_handles_from_links_11nov.json
    python scripts/admin/fill_instagram_from_own_links.py --apply    # also writes the handles (backup table first)
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from joint_video_spillover_test import load  # noqa: E402
from orchestrator import load_env  # noqa: E402

LINK = re.compile(r"instagram\.com/([a-z0-9_.]{3,30})", re.I)
# hand check 11 Nov 2026: link does not clearly belong to the creator (media partner, clinic, unclear), or creator outside the Indian fitness rule
EXCLUDE = {"Cric It with Badri", "Dr AshishSaini UrologistAIIMS", "Dr. Aalap Shah", "Dr. Mitali Rathod", "Goyal Sahab ke Nuskhe",
           "India Running with Milind Soman", "Siddhant Jaiswal", "Surakshith Battina", "Varun dutt dubey", "Ronnie Coleman", "Saket Gokhale"}
NOT_HANDLE = {"p", "reel", "reels", "stories", "explore", "accounts", "tv", "direct", "about", "developer", "legal"}


def handles(text):
    return [h.lower().rstrip(".") for h in LINK.findall(text or "") if h.lower().rstrip(".") not in NOT_HANDLE]


def main() -> int:
    conn = psycopg2.connect(load_env()["DATABASE_URL"])
    cur = conn.cursor()
    scope, *_ = load(cur)
    cur.execute("select creator_id::text, name, lower(instagram_handle) from creators")
    rows = cur.fetchall()
    taken = {h.lstrip("@") for _, _, h in rows if h}
    todo = {c: n for c, n, h in rows if c in scope and not h}
    cur.execute("select creator_id::text, description from youtube_channels where creator_id::text = any(%s)", (list(todo),))
    chan = defaultdict(set)
    for c, d in cur.fetchall():
        chan[c] |= set(handles(d))
    cur.execute("select creator_id::text, description from youtube_videos where creator_id::text = any(%s)", (list(todo),))
    vids = defaultdict(Counter)
    for c, d in cur.fetchall():
        for h in set(handles(d)):
            vids[c][h] += 1
    found, skipped = {}, {}
    for c, n in todo.items():
        if n in EXCLUDE:
            continue
        total = sum(vids[c].values())
        pick = None
        if len(chan[c]) == 1:
            pick = next(iter(chan[c]))
        elif vids[c]:
            h, k = vids[c].most_common(1)[0]
            if k >= 3 and k >= 0.6 * total:
                pick = h
        if not pick:
            continue
        if pick in taken:
            skipped[n] = pick
            continue
        found[c] = {"name": n, "instagram_handle": pick, "in_channel_description": pick in chan[c], "videos_with_link": vids[c].get(pick, 0)}
        taken.add(pick)
    out = ROOT / "models" / "ig_handles_from_links_11nov.json"
    out.write_text(json.dumps({"rule": __doc__.split("\n\n")[1], "found": found, "skipped_already_held": skipped}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(todo)} in-scope creators without an Instagram handle; own link found for {len(found)}; {len(skipped)} skipped (held by another creator) -> {out.name}")
    if "--apply" in sys.argv and found:
        cur.execute("create table if not exists creators_ig_handle_backup_20261111 as select creator_id, instagram_handle, now() as saved_at from creators where false")
        cur.execute("insert into creators_ig_handle_backup_20261111 select creator_id, instagram_handle, now() from creators where creator_id::text = any(%s)", (list(found),))
        for c, f in found.items():
            cur.execute("update creators set instagram_handle = %s, updated_at = now() where creator_id::text = %s and instagram_handle is null", (f["instagram_handle"], c))
        conn.commit()
        print(f"applied {len(found)} handles (backup: creators_ig_handle_backup_20261111)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
