"""How a creator promotes, and how the audience reacts: a disclosure index and a sponsored-response (purchase-intent) comparison. READ ONLY on the database; writes models/promotion_behaviour.json.

    python scripts/run_promotion_behaviour.py [--placebo 300] [--out models/promotion_behaviour.json]

1. DISCLOSURE INDEX (per creator, YouTube): of the videos we detected as sponsored, the share that carry an explicit disclosure: a tag such as #ad or "sponsored by", the platform's
   paid-partnership label, or a spoken disclosure. The rest were found only from a brand name and discount code. 95% Wilson interval; at least 5 sponsored videos. A brand cares because
   undisclosed promotion is an advertising-rules and trust risk. LIMITS: the detector reads descriptions (plus a pinned creator comment and a spoken-scan of some Shorts), so a disclosure
   made only in a place we do not read counts as "not disclosed"; the index is a floor, not an accusation.
2. SPONSORED RESPONSE (YouTube long videos): comments that look like buying or asking where to buy (scripts/ingestion/purchase_intent.py) per 1,000 collected comments, on the creator's
   sponsored videos vs their other videos. Per creator: ratio sponsored / other with a 95% interval from resampling videos (needs 3+ sponsored and 5+ other videos and 300+ comments each side).
   Overall: median log ratio over creators, interval by resampling creators, and a PLACEBO that shuffles the sponsored flags among each creator's own videos (keeps how many are sponsored).
   LIMITS: a PROXY for audience reaction, not sales; sponsored videos mention a code or link, which invites such comments by design; "other" videos are those the detector did not flag
   (some undetected sponsorships are mixed in, which would shrink the ratio); Instagram has too few intent comments (36) to compare, so it is not shown.
"""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
V = "(select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed','probable'))"
MIN_SPONSORED_DISCLOSURE = 5
MIN_S_VIDEOS, MIN_O_VIDEOS, MIN_COMMENTS = 3, 5, 300
NON_DISCLOSURE_PREFIXES = ("brand:", "native:", "spoken:", "comment:", "review:")


def is_disclosed(evidence: list | None) -> bool:
    """True when the stored evidence list holds an explicit disclosure: the paid-partnership label, a spoken disclosure, or a plain tag (#ad, sponsored by, ...)."""
    for e in evidence or []:
        e = str(e)
        if e == "native:paid_partnership_label" or e.startswith("spoken:disclosure") or e.startswith("disclosure:"):
            return True
        if not e.startswith(NON_DISCLOSURE_PREFIXES):
            return True
    return False


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def disclosure_label(share: float) -> str:
    """Neutral wording about what we can READ, not a judgement of the creator: the detector may miss a disclosure made somewhere it does not look."""
    if share >= 0.7:
        return "explicit disclosure on most detected sponsored videos"
    if share <= 0.2:
        return "explicit disclosure on few detected sponsored videos"
    return "explicit disclosure on some detected sponsored videos"


def load():
    import psycopg2
    from dotenv import dotenv_values

    conn = psycopg2.connect(dotenv_values(ROOT / ".env")["DATABASE_URL"], connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute(f"""select v.creator_id::text, v.video_id, v.is_sponsored, v.sponsorship_raw_matches, coalesce(v.duration_seconds,0) > 60,
                           coalesce(cc.n, 0), coalesce(pi.n, 0)
                    from youtube_videos v
                    left join (select video_id, count(*) n from youtube_comments group by 1) cc on cc.video_id = v.video_id
                    left join (select post_id, count(*) n from purchase_intent_comments where platform = 'youtube' group by 1) pi on pi.post_id = v.video_id
                    where v.creator_id in {V}""")
    rows = cur.fetchall()
    cur.execute("select creator_id::text, name from creators")
    names = dict(cur.fetchall())
    conn.close()
    return rows, names


def ratio(s, o):
    """Rate in sponsored videos over rate in other videos; each argument is an array of (comments, intent) rows. +0.5 smoothing on the counts."""
    rs = (s[:, 1].sum() + 0.5) / (s[:, 0].sum() + 0.5)
    ro = (o[:, 1].sum() + 0.5) / (o[:, 0].sum() + 0.5)
    return rs / ro


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--placebo", type=int, default=300)
    ap.add_argument("--out", default=str(ROOT / "models" / "promotion_behaviour.json"))
    args = ap.parse_args()
    rows, names = load()
    rng = np.random.default_rng(30)

    # ---- 1. disclosure ----
    disc: dict[str, list[bool]] = {}
    for cid, _vid, sp, raw, _long, _n, _k in rows:
        if sp:
            disc.setdefault(cid, []).append(is_disclosed(raw if isinstance(raw, list) else json.loads(raw) if raw else []))
    creators: dict[str, dict] = {}
    for cid, flags in disc.items():
        n, k = len(flags), sum(flags)
        if n >= MIN_SPONSORED_DISCLOSURE:
            lo, hi = wilson(k, n)
            creators.setdefault(cid, {"creator_id": cid, "name": names.get(cid, cid)})["disclosure"] = {
                "sponsored_videos": n, "disclosed": k, "share": round(k / n, 3), "ci95": [round(lo, 3), round(hi, 3)], "label": disclosure_label(k / n)}
    all_flags = [f for fl in disc.values() for f in fl]
    shares = [d["disclosure"]["share"] for d in creators.values() if "disclosure" in d]
    disclosure_summary = {"creators": len(shares), "sponsored_videos": len(all_flags), "share_disclosed_overall": round(sum(all_flags) / max(len(all_flags), 1), 3),
                          "median_creator_share": round(float(np.median(shares)), 3) if shares else None,
                          "creators_most": sum(1 for x in shares if x >= 0.7), "creators_some": sum(1 for x in shares if 0.2 < x < 0.7),
                          "creators_few": sum(1 for x in shares if x <= 0.2)}
    print(f"disclosure: {disclosure_summary}")

    # ---- 2. sponsored response ----
    per: dict[str, dict[str, list]] = {}
    for cid, _vid, sp, _raw, is_long, n, k in rows:
        if is_long and n >= 20:
            per.setdefault(cid, {"s": [], "o": []})["s" if sp else "o"].append((float(n), float(k)))
    qual = {}
    for cid, g in per.items():
        s, o = np.array(g["s"]), np.array(g["o"])
        if len(s) >= MIN_S_VIDEOS and len(o) >= MIN_O_VIDEOS and s[:, 0].sum() >= MIN_COMMENTS and o[:, 0].sum() >= MIN_COMMENTS:
            qual[cid] = (s, o)
    res_rows, logs = [], []
    for cid, (s, o) in qual.items():
        r = ratio(s, o)
        boots = [ratio(s[rng.integers(0, len(s), len(s))], o[rng.integers(0, len(o), len(o))]) for _ in range(500)]
        lo, hi = np.percentile(boots, [2.5, 97.5])
        verdict = "more buying signals on sponsored videos" if lo > 1 else "fewer buying signals on sponsored videos" if hi < 1 else "about the same"
        creators.setdefault(cid, {"creator_id": cid, "name": names.get(cid, cid)})["response"] = {
            "sponsored_videos": len(s), "other_videos": len(o), "intent_per_1000_sponsored": round(1000 * s[:, 1].sum() / s[:, 0].sum(), 2),
            "intent_per_1000_other": round(1000 * o[:, 1].sum() / o[:, 0].sum(), 2), "ratio": round(float(r), 2), "ci95": [round(float(lo), 2), round(float(hi), 2)], "verdict": verdict}
        logs.append(math.log(r))
        res_rows.append(verdict)
    med = float(np.median(logs)) if logs else float("nan")
    boot_med = [float(np.median(rng.choice(logs, len(logs)))) for _ in range(2000)] if logs else []
    lo, hi = (float(np.percentile(boot_med, 2.5)), float(np.percentile(boot_med, 97.5))) if boot_med else (float("nan"),) * 2
    plac = []
    for _ in range(args.placebo):
        ls = []
        for s, o in qual.values():
            allv = np.vstack([s, o])
            idx = rng.permutation(len(allv))
            ls.append(math.log(ratio(allv[idx[:len(s)]], allv[idx[len(s):]])))
        plac.append(float(np.median(ls)))
    p = (1 + sum(x >= med for x in plac)) / (1 + len(plac)) if plac else None
    response_summary = {"creators": len(qual), "median_ratio": round(math.exp(med), 2) if logs else None, "ci95_ratio": [round(math.exp(lo), 2), round(math.exp(hi), 2)] if logs else None,
                        "placebo_median_ratio": round(math.exp(float(np.median(plac))), 2) if plac else None, "p_one_sided_more_on_sponsored": round(p, 4) if p is not None else None,
                        "creators_more": sum(v.startswith("more") for v in res_rows), "creators_fewer": sum(v.startswith("fewer") for v in res_rows),
                        "creators_same": sum(v == "about the same" for v in res_rows)}
    print(f"response: {response_summary}")

    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "disclosure": disclosure_summary, "response": response_summary,
           "creators": sorted(creators.values(), key=lambda c: c["name"]), "placebo_runs": args.placebo,
           "limits": "disclosure is read from descriptions, a pinned creator comment and a spoken scan of some Shorts, so it is a floor; response is a proxy (buying-looking comments), not sales; YouTube only"}
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
