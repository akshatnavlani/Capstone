"""One final list of Instagram handles for in-scope creators that had none (11 Nov 2026). READ ONLY; writes models/ig_handles_final_11nov.json.

Sources, all the creator's OWN YouTube content, in this order (first one wins):
 1. instagram.com links in their channel / video descriptions (models/ig_handles_from_links_11nov.json)
 2. 'Instagram ... @handle' text in their descriptions (>= 3 videos and >= 60% of such mentions, or the channel description)
 3. the links section of their YouTube About page, exactly one Instagram link (models/ig_handles_about_11nov.json)
 4. About pages with several Instagram links: taken only when exactly one carries the creator's name (hand decisions below)
Hand check: DROP = link not clearly the creator's own (media partner, clinic, other page) or creator outside the Indian
fitness rule; PREFER_ABOUT = the About page's personal account replaces a description link of a different account.
A handle already held by another creator is never taken. Then: scripts/admin/apply_ig_handles.py (writes, with backup).
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

DROP = {"Cric It with Badri:divomovies", "Dr AshishSaini UrologistAIIMS:excel_advance_urology", "Dr. Mitali Rathod:dr.uterus",
        "Goyal Sahab ke Nuskhe:healtthguru", "India Running with Milind Soman:livyourfame", "India Running with Milind Soman:liveonfame",
        "Varun dutt dubey:bodypower58", "Varun dutt dubey:gmail.com", "Dr. Vikash Kumar Agarwal:vcarecancercenter",
        "Nutritionist Sonakshi Joshi:dash.of.delish_17", "Siddhant Jaiswal:*", "Ronnie Coleman:*", "Saket Gokhale:*"}
PREFER_ABOUT = {"Dr. Aalap Shah"}
AMBIGUOUS_PICK = {"Yasmin Karachiwala": "yasminkarachiwala", "Jeet Selal Aesthetics": "jeet_selal", "Siddhant Rai Sikand": "siddhantraisikand",
                  "IFBB PRO MANOJ PATIL": "manojpatil_ifbbpro_official", "The Yoga Institute": "theyogainstituteofficial",
                  "Dr AshishSaini UrologistAIIMS": "dr_ashishsaini", "Gut Feeling with Dr Pal - Podcast": "gutfeelingwithdrpal"}
TEXT = re.compile(r"(?:instagram|insta\b|\big\b)[^@\n]{0,40}@([a-z0-9_.]{3,30})", re.I)


def dropped(name, h):
    return f"{name}:{h}" in DROP or f"{name}:*" in DROP


def main() -> int:
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    scope, *_ = load(cur)
    cur.execute("select creator_id::text, name, lower(instagram_handle) from creators")
    rows = cur.fetchall()
    taken = {h.lstrip("@") for _, _, h in rows if h}
    names = {c: n for c, n, h in rows if c in scope and not h}
    links = json.load(open(ROOT / "models" / "ig_handles_from_links_11nov.json", encoding="utf-8"))["found"]
    about = json.load(open(ROOT / "models" / "ig_handles_about_11nov.json", encoding="utf-8"))
    # source 2: text mentions
    cur.execute("select creator_id::text, description from youtube_videos where creator_id::text = any(%s)", (list(names),))
    cnt = defaultdict(Counter)
    for c, d in cur.fetchall():
        for h in {x.lower().rstrip(".") for x in TEXT.findall(d or "")}:
            cnt[c][h] += 1
    cur.execute("select creator_id::text, description from youtube_channels where creator_id::text = any(%s)", (list(names),))
    ch = defaultdict(set)
    for c, d in cur.fetchall():
        ch[c] |= {x.lower().rstrip(".") for x in TEXT.findall(d or "")}
    text = {}
    for c in names:
        tot = sum(cnt[c].values())
        if len(ch[c]) == 1:
            text[c] = next(iter(ch[c]))
        elif cnt[c]:
            h, k = cnt[c].most_common(1)[0]
            if k >= 3 and k >= 0.6 * tot:
                text[c] = h
    amb = {n: h for n, h in AMBIGUOUS_PICK.items() if n in about["ambiguous_not_taken"] and h in about["ambiguous_not_taken"][n]}
    final = {}
    for c, n in sorted(names.items(), key=lambda x: x[1]):
        cands = []
        if n in PREFER_ABOUT and c in about["found"]:
            cands.append((about["found"][c]["instagram_handle"], "YouTube About page (personal account preferred)"))
        if c in links:
            cands.append((links[c]["instagram_handle"], "instagram.com link in own descriptions"))
        if c in text:
            cands.append((text[c], "'Instagram @handle' in own descriptions"))
        if c in about["found"]:
            cands.append((about["found"][c]["instagram_handle"], "YouTube About page link"))
        if n in amb:
            cands.append((amb[n], "YouTube About page, the one link with the creator's name"))
        for h, src in cands:
            if not dropped(n, h) and h not in taken:
                final[c] = {"name": n, "instagram_handle": h, "source": src}
                taken.add(h)
                break
    out = ROOT / "models" / "ig_handles_final_11nov.json"
    out.write_text(json.dumps(final, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(names)} in-scope creators without an Instagram handle; final list {len(final)} -> {out.name}")
    print(Counter(f["source"] for f in final.values()).most_common())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
