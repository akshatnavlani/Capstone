"""Filter and cost error analysis (PendingWork S7). READ ONLY: never writes to the database.

    python scripts\\audit_filters_and_cost.py
    python scripts\\audit_filters_and_cost.py --sample-product 40     # print dropped creators for hand review

The recommendation endpoint filters creators in a fixed order (budget, platform, region,
demographic, product category); a creator is counted under the FIRST filter that drops it.
The soft filters keep any creator with no text to judge, and drop a creator whose text lacks
every query word (a plain substring test). This audit measures:

  1. The standing demo query ("Athletic water bottle", 5,000,000 INR, "India"): do the counts
     259 considered / 15 budget / 116 region / 128 product reproduce, and why?
  2. The region filter: of the creators it drops for "India", how many show clear evidence of
     being in India (YouTube country code IN, flag emoji, Devanagari or Gurmukhi script, +91,
     Indian place names), and how many are really elsewhere?
  3. The product filter: how many drops are recoverable by whole-word and stemmed matching
     (athlete / athletic), and how many keeps are substring accidents.
  4. How often a soft filter is a no-op because the creator has no text at all.
  5. Cost-model stability: under a flat, a category-tiered and a hypothetical follower-tiered
     cost model, how much does the eligible set and the top of the ranking move?

Ranking uses the stored fusionscore rows (brief-independent baseline), so the comparison
isolates the effect of the cost model. Results are saved to models/filter_cost_audit.json.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

# Cost per follower, INR. FLAT is what this branch ships; TIERED is on branch review-1
# (backend/app/routers/influencers.py CATEGORY_RATE); FOLLOWER_TIERED is hypothetical: real
# influencer pricing falls per follower as reach grows, so it stands in for a future rate card.
FLAT = 0.5
CATEGORY_RATE = {"athlete": 0.60, "team": 0.45, "league": 0.45, "fitness_influencer": 0.35, "lifestyle_influencer": 0.40, "other": 0.50}
FOLLOWER_TIERS = [(100_000, 1.0), (1_000_000, 0.6), (10_000_000, 0.3), (float("inf"), 0.1)]  # (reach below, rate)

BRIEFS = ["Athletic water bottle", "running shoes", "protein powder", "yoga mat", "cricket bat",
          "sports drink", "fitness tracker", "gym equipment", "badminton racket", "athletic apparel"]
BUDGETS = [1_000_000, 2_000_000, 5_000_000, 10_000_000, 50_000_000]

INDIA_MARKERS = ["🇮🇳", "+91", "mumbai", "delhi", "gurgaon", "gurugram", "kolkata", "bengaluru", "bangalore", "chennai", "hyderabad",
                 "pune", "jaipur", "lucknow", "kerala", "punjab", "kashmir", "gujarat", "tamil", "noida", "haryana", "bharat",
                 "ipl", "bcci", "kabaddi", "i-league", "durand", "indian", "rohini", "calicut", "kushti"]
INDIC_SCRIPT = re.compile("[ऀ-෿]")  # Devanagari, Bengali, Gurmukhi, Gujarati, Tamil, Telugu, Kannada, Malayalam
FOREIGN_COUNTRIES = {"US", "AU", "GB", "AE", "CA", "DE", "FR", "ES", "BR", "NZ", "ZA"}


def stem(w: str) -> str:
    w = w.lower()
    for suf in ("ing", "ers", "er", "ies", "es", "ic", "ed", "s", "e"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pct(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f}% (95% CI {100 * lo:.0f}-{100 * hi:.0f}%)" if n else "0/0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-product", type=int, default=0, help="print N random product-filter drops for hand review")
    ap.add_argument("--sample-region", action="store_true", help="print every region-dropped creator")
    ap.add_argument("--sample-keeps", type=int, default=0, help="print N random substring-only keeps (kept by the substring test, not by whole-word match)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL") or re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    os.environ["CREATOR_FEATURES_DISABLED"] = "1"
    from ml._scipy_compat import avoid_blocked_scipy_solver

    avoid_blocked_scipy_solver()
    from sqlmodel import Session, create_engine, select

    from app.models import Creator, FusionScore, InstagramProfile, YouTubeChannel
    from app.routers import influencers as R  # the real _extract_keywords / _keyword_overlap

    with Session(create_engine(os.environ["DATABASE_URL"])) as s:
        creators = s.exec(select(Creator)).all()
        yt = {y.creator_id: y for y in s.exec(select(YouTubeChannel)).all()}
        ig = {i.creator_id: i for i in s.exec(select(InstagramProfile).where(InstagramProfile.creator_id.is_not(None))).all()}
        latest = {}
        for f in s.exec(select(FusionScore).order_by(FusionScore.computed_at)).all():
            latest[f.creator_id] = f.final_score
    n = len(creators)
    out: dict = {}

    def reach_of(c) -> int:
        y, i = yt.get(c.creator_id), ig.get(c.creator_id)
        return max((y.subscriber_count if y else 0) or 0, (i.follower_count if i else 0) or 0)

    rates = {
        "flat 0.5 (this branch)": lambda c, r: FLAT,
        "category-tiered (review-1)": lambda c, r: CATEGORY_RATE.get(c.category or "other", FLAT),
        "follower-tiered (hypothetical rate card)": lambda c, r: next(rate for cap, rate in FOLLOWER_TIERS if r < cap),
    }

    def matcher_current(kw, texts):
        """LEGACY test, frozen: any query word as a plain substring of the text (before the S7 fixes)."""
        combined = " ".join(t.lower() for t in texts if t)
        return any(k in combined for k in kw)

    def matcher_word(kw, texts):
        ws = set(words(" ".join(t for t in texts if t)))
        return any(k in ws for k in kw)

    def matcher_stem(kw, texts):
        ws = {stem(w) for w in words(" ".join(t for t in texts if t))}
        return any(stem(k) in ws for k in kw)

    def run(product, budget, region=None, rate=None, match=matcher_current, fixed=False):
        rk, pk = R._extract_keywords(region), R._extract_keywords(product)
        counts = collections.Counter()
        dropped = collections.defaultdict(list)
        kept = []
        for c in creators:
            y, i = yt.get(c.creator_id), ig.get(c.creator_id)
            counts["considered"] += 1
            reach = reach_of(c)
            if reach and reach * (rate or rates["flat 0.5 (this branch)"])(c, reach) > budget:
                counts["budget"] += 1
                dropped["budget"].append(c)
                continue
            rs = [y.country if y else None, y.description if y else None, i.bio if i else None]
            region_ok = R._region_overlap(rk, rs, c.name) if fixed else match(rk, rs)
            if rk and any(rs) and not region_ok:
                counts["region"] += 1
                dropped["region"].append(c)
                continue
            ps = [c.category.replace("_", " ") if c.category else None, y.description if y else None, i.bio if i else None]
            product_ok = R._keyword_overlap(pk, ps) if fixed else match(pk, ps)
            if pk and any(ps) and not product_ok:
                counts["product"] += 1
                dropped["product"].append(c)
                continue
            kept.append(c)
        return counts, kept, dropped

    # ---- 1. standing demo query ----------------------------------------------------------------
    print("1. STANDING DEMO QUERY: 'Athletic water bottle', 5,000,000 INR, region 'India'")
    demo = {}
    for name, rate in rates.items():
        cnt, kept, _ = run("Athletic water bottle", 5_000_000, "India", rate)
        demo[name] = {**cnt, "kept": len(kept)}
        print(f"   {name:42s} considered {cnt['considered']}, budget {cnt['budget']}, region {cnt['region']}, product {cnt['product']}, results {len(kept)}")
    print("   counts are sequential: a creator is counted under the first filter that drops it, so they add up to 259 and nothing is left")
    demo_fixed = {}
    for name, rate in rates.items():
        cnt, kept, _ = run("Athletic water bottle", 5_000_000, "India", rate, fixed=True)
        demo_fixed[name] = {**cnt, "kept": len(kept)}
        print(f"   AFTER THE FIX  {name:42s} budget {cnt['budget']}, region {cnt['region']}, product {cnt['product']}, results {len(kept)}")
    out["demo_query_fixed"] = demo_fixed
    cnt, kept, _ = run("athlete", 5_000_000, "India")
    print(f"   the same budget and region with the query 'athlete' (the demo's other word): {len(kept)} results, product drops {cnt['product']}")
    out["demo_query"] = demo

    # ---- 2. region filter ----------------------------------------------------------------------------
    _, _, dr = run("athlete", 5_000_000, "India")
    reg = dr["region"]
    code_in, evid, foreign, unknown = [], [], [], []
    for c in reg:
        y, i = yt.get(c.creator_id), ig.get(c.creator_id)
        text = " ".join(t for t in [y.description if y else None, i.bio if i else None, c.name] if t).lower()
        if y and y.country == "IN":
            code_in.append(c)
        if y and y.country in FOREIGN_COUNTRIES:
            foreign.append(c)
        elif (y and y.country == "IN") or INDIC_SCRIPT.search(text) or any(m in text for m in INDIA_MARKERS):
            evid.append(c)
        else:
            unknown.append(c)
    print("\n2. REGION FILTER ('India')")
    print(f"   dropped {len(reg)} creators; the filter needs the word 'india' (substring) in the YouTube country field, YouTube description or Instagram bio")
    print(f"   clear evidence of India in the data: {pct(len(evid), len(reg))}")
    print(f"      of which the YouTube country field is the ISO code 'IN', which never contains 'india': {len(code_in)}")
    print(f"   clear evidence of being elsewhere (YouTube country US/AU/GB/AE/...): {pct(len(foreign), len(reg))}")
    print(f"   no evidence either way in the text: {pct(len(unknown), len(reg))}  (the audit cannot call these)")
    named_india = [c.name for c in reg if "india" in c.name.lower()]
    print(f"   the creator NAME is never read: {len(named_india)} dropped creators have 'India' in their own name: {named_india}")
    print(f"   => at least {100 * len(evid) / len(reg):.0f}% of region drops are creators the data itself places in India; correct drops are at most {100 * (len(foreign) + len(unknown)) / len(reg):.0f}%")
    out["region"] = {"dropped": len(reg), "india_evidence": len(evid), "iso_code_IN": len(code_in), "foreign": len(foreign), "unknown": len(unknown), "india_in_name": named_india}
    _, kept_f, dr_f = run("athlete", 5_000_000, "India", fixed=True)
    reg_f = dr_f["region"]
    ev_f = [c for c in reg_f if (yt.get(c.creator_id) and yt[c.creator_id].country == "IN") or INDIC_SCRIPT.search(" ".join(t for t in [(yt.get(c.creator_id).description if yt.get(c.creator_id) else None), (ig.get(c.creator_id).bio if ig.get(c.creator_id) else None), c.name] if t)) or any(m in " ".join(t for t in [(yt.get(c.creator_id).description if yt.get(c.creator_id) else None), (ig.get(c.creator_id).bio if ig.get(c.creator_id) else None), c.name] if t).lower() for m in INDIA_MARKERS)]
    print(f"   AFTER THE FIX the same region filter drops {len(reg_f)} (was {len(reg)}); {len(ev_f)} of those still show explicit India evidence ({len(kept_f)} creators survive for 'athlete'/5M/India, was 77)")
    out["region_fixed"] = {"dropped": len(reg_f), "still_with_india_evidence": len(ev_f), "athlete_5M_India_results": len(kept_f)}
    if args.sample_region:
        for lab, grp in (("INDIA-EVIDENCE", evid), ("FOREIGN", foreign), ("UNKNOWN", unknown)):
            print(f"   -- {lab}")
            for c in grp:
                y, i = yt.get(c.creator_id), ig.get(c.creator_id)
                print(f"      {c.name[:28]:28s} ctry={y.country if y else None} | {((i.bio if i and i.bio else '') or (y.description if y and y.description else '')).replace(chr(10), ' ')[:70]}")

    # ---- 3. product filter: substring vs whole-word vs stemmed ---------------------------------------------
    print("\n3. PRODUCT FILTER (budget 5M, no region), per brief: kept by current substring test / whole word / stemmed whole word")
    prod = {}
    recoverable_pool: list[tuple[str, object]] = []
    sub_only_pool: list[tuple[str, object]] = []
    for brief in BRIEFS:
        k_cur = {c.creator_id for c in run(brief, 5_000_000, None, match=matcher_current)[1]}
        k_word = {c.creator_id for c in run(brief, 5_000_000, None, match=matcher_word)[1]}
        k_stem = {c.creator_id for c in run(brief, 5_000_000, None, match=matcher_stem)[1]}
        k_fixed = {c.creator_id for c in run(brief, 5_000_000, None, fixed=True)[1]}
        recov = k_stem - k_cur
        sub_only = k_cur - k_word
        by_id = {c.creator_id: c for c in creators}
        recoverable_pool += [(brief, by_id[i]) for i in recov]
        sub_only_pool += [(brief, by_id[i]) for i in sub_only]
        prod[brief] = {"current": len(k_cur), "whole_word": len(k_word), "stemmed": len(k_stem), "recoverable": len(recov), "substring_only_keeps": len(sub_only), "fixed": len(k_fixed)}
        print(f"   {brief:24s} before {len(k_cur):3d} | AFTER THE FIX {len(k_fixed):3d} | whole-word {len(k_word):3d} | stemmed {len(k_stem):3d} | recoverable drops {len(recov):3d} | substring-only keeps {len(sub_only):3d}")
    kept_counts = sorted(v["current"] for v in prod.values())
    fixed_counts = sorted(v["fixed"] for v in prod.values())
    print(f"   AFTER THE FIX creators kept per brief: {fixed_counts}; median {fixed_counts[len(fixed_counts) // 2]} (was {kept_counts[len(kept_counts) // 2]})")
    print(f"   creators kept by the current product filter, per brief: {kept_counts} of {n}; the hard product filter leaves a median of {kept_counts[len(kept_counts) // 2]} creators")
    print(f"   briefs with 5 or fewer creators left: {sum(c <= 5 for c in kept_counts)} of {len(kept_counts)}")
    tot_rec = sum(v["recoverable"] for v in prod.values())
    print(f"   recoverable drops over {len(BRIEFS)} briefs: {tot_rec}; a drop is 'recoverable' when the creator's text has the same word stem as the query (athlete/athletic, run/running)")
    out["product"] = prod
    if args.sample_product:
        rng = random.Random(0)
        print(f"\n   HAND-REVIEW SAMPLE: {args.sample_product} recoverable drops (current filter dropped; stemmed match keeps). Judge: should it have survived?")
        for brief, c in rng.sample(recoverable_pool, min(args.sample_product, len(recoverable_pool))):
            y, i = yt.get(c.creator_id), ig.get(c.creator_id)
            txt = " ".join(t for t in [c.category.replace("_", " ") if c.category else "", y.description if y else "", i.bio if i else ""] if t).replace("\n", " ")
            hit = next((w for w in words(txt) if stem(w) in {stem(k) for k in R._extract_keywords(brief)}), "?")
            at = max(txt.lower().find(hit), 0)
            print(f"     [{brief}] {c.name[:26]:26s} ({c.category}) stem-matched '{hit}': ...{txt[max(0, at - 40): at + 80]}...")

    if args.sample_keeps:
        rng = random.Random(0)
        print(f"\n   HAND-REVIEW SAMPLE: {args.sample_keeps} substring-only keeps (the query word is only INSIDE a longer word). Judge: is it a relevant creator?")
        for brief, c in rng.sample(sub_only_pool, min(args.sample_keeps, len(sub_only_pool))):
            y, i = yt.get(c.creator_id), ig.get(c.creator_id)
            txt = " ".join(t for t in [c.category.replace("_", " ") if c.category else "", y.description if y else "", i.bio if i else ""] if t).replace("\n", " ")
            kws = R._extract_keywords(brief)
            hit = next((k for k in kws if k in txt.lower()), "?")
            at = max(txt.lower().find(hit), 0)
            word = next((w for w in words(txt) if hit in w), hit)
            print(f"     [{brief}] {c.name[:24]:24s} ({c.category}) '{hit}' inside '{word}': ...{txt[max(0, at - 35): at + 70]}...")

    # ---- 4. no-op filters ------------------------------------------------------------------------------------------
    no_region = sum(1 for c in creators if not any([(yt.get(c.creator_id).country if yt.get(c.creator_id) else None),
                                                    (yt.get(c.creator_id).description if yt.get(c.creator_id) else None),
                                                    (ig.get(c.creator_id).bio if ig.get(c.creator_id) else None)]))
    no_prod = sum(1 for c in creators if not any([c.category, (yt.get(c.creator_id).description if yt.get(c.creator_id) else None),
                                                  (ig.get(c.creator_id).bio if ig.get(c.creator_id) else None)]))
    print("\n4. NO-OP FILTERS (creators with no text to judge are always kept)")
    print(f"   no region signal (no YouTube country/description, no Instagram bio): {pct(no_region, n)}")
    print(f"   no product signal (no category, description or bio): {pct(no_prod, n)}")
    out["noop"] = {"no_region_signal": no_region, "no_product_signal": no_prod, "creators": n}

    # ---- 5. cost-model stability ---------------------------------------------------------------------------------------
    print("\n5. COST-MODEL STABILITY (no text filters; ranking = stored baseline fusion score)")
    base_name = "flat 0.5 (this branch)"
    cost_rows = []
    for b in BUDGETS:
        sets = {}
        for name, rate in rates.items():
            _, kept, _ = run("", b, None, rate)
            sets[name] = {c.creator_id: latest.get(c.creator_id, 0.0) for c in kept}
        base = sets[base_name]
        base_top10 = [k for k, _ in sorted(base.items(), key=lambda kv: -kv[1])[:10]]
        for name, st in sets.items():
            if name == base_name:
                continue
            union = set(base) | set(st)
            jac = len(set(base) & set(st)) / len(union) if union else 1.0
            top10 = [k for k, _ in sorted(st.items(), key=lambda kv: -kv[1])[:10]]
            ov = len(set(top10) & set(base_top10))
            flips = len(set(base) ^ set(st))
            cost_rows.append({"budget": b, "model": name, "eligible": len(st), "eligible_flat": len(base), "jaccard": jac, "top10_overlap": ov, "flips": flips})
            print(f"   budget {b / 1e6:>4.0f}M | {name:42s} eligible {len(st):3d} (flat {len(base):3d}) | set overlap (Jaccard) {jac:.2f} | {flips:3d} creators flip | top-10 shared with flat {ov}/10")
    print("   rank order among creators eligible under both models is unchanged: ranking uses the fusion score and the cost model only decides who is eligible")
    out["cost_stability"] = cost_rows
    # canary: 5M India as in the demo
    can = {}
    for name, rate in rates.items():
        _, kept, _ = run("athlete", 5_000_000, "India", rate)
        can[name] = {c.creator_id: latest.get(c.creator_id, 0.0) for c in kept}
    base = can[base_name]
    print("   canary 'athlete' / 5M / India:")
    for name, st in can.items():
        top10 = [k for k, _ in sorted(st.items(), key=lambda kv: -kv[1])[:10]]
        btop = [k for k, _ in sorted(base.items(), key=lambda kv: -kv[1])[:10]]
        print(f"      {name:42s} {len(st)} eligible, top-10 shared with flat {len(set(top10) & set(btop))}/10")
    out["canary_athlete_5M_India"] = {k: len(v) for k, v in can.items()}

    (ROOT / "models" / "filter_cost_audit.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("\nsaved models/filter_cost_audit.json")


if __name__ == "__main__":
    main()
