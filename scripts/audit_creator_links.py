"""Cross-platform linking audit (PendingWork S8). READ ONLY: never writes to the database.

    python scripts\\audit_creator_links.py
    python scripts\\audit_creator_links.py --show-all      # print every row reviewed, not just the flagged ones

What "linking" means in this project: there is no separate unified-ID table. A creator
is one row in `creators` holding a YouTube handle, an Instagram handle and Reddit
subreddits; profile tables point back to it through a nullable creator_id; Reddit posts are
tied to creators through `reddit_post_creators`. This audit measures, for each kind of
link, how much independent evidence supports it, and says plainly where there is none.

Checks:
  1. Coverage          how many creators have which platforms (cross-platform = 2+).
  2. YouTube links     41 links: automatic evidence (Instagram handle in the channel
                       description, name match), split by how the handle was obtained.
  3. Instagram links   handle -> profile coverage, verified accounts, accounts never fetched.
  4. Duplicates        one handle claimed by two creators, one entity split across two rows.
  5. Reddit links      does the post text actually name the creator it is linked to, and do
                       co-occurrence edges rest on posts that name BOTH creators.
  6. Post ownership    Track A's audit of Instagram posts filed under the wrong creator,
                       re-checked against the database today.
  7. Null creator_id   how many profile rows have none, and that nothing downstream breaks.
  8. Cross-platform    how many creators and how many GAIL training pairs actually span 2+ platforms.

Results are saved to models/link_audit.json.
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHECKPOINT = ROOT / "scripts" / "ingestion" / "ownership_audit_checkpoint.json"
YT_CHECKPOINT = ROOT / "scripts" / "ingestion" / "yt_discovery_checkpoint.json"

norm_handle = lambda h: re.sub(r"^(@|u/|r/)", "", (h or "").strip().lower())
alnum = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())


def tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(t) >= 3}


def similar(a: str, b: str) -> float:
    a, b = alnum(a), alnum(b)
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion k/n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def pct(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f}% (95% CI {100 * lo:.0f}-{100 * hi:.0f}%)" if n else "0/0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-all", action="store_true")
    ap.add_argument("--sample", type=int, default=0, help="print N random Reddit links for hand review")
    ap.add_argument("--sample-weak", type=int, default=0, help="print N random Reddit links that fail the strict name test")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    url = os.environ.get("DATABASE_URL") or re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    from sqlalchemy import create_engine, text

    out: dict = {}
    with create_engine(url).connect() as c:
        q = lambda sql, **k: c.execute(text(sql), k).all()
        creators = q("select creator_id::text, name, category, youtube_handle, instagram_handle, reddit_handles from creators")
        by_id = {r[0]: r for r in creators}
        n = len(creators)

        # ---- 1. coverage -------------------------------------------------------------------
        has_yt = [r for r in creators if r[3]]
        has_ig = [r for r in creators if r[4]]
        has_rd = [r for r in creators if r[5]]
        per = collections.Counter(sum(bool(x) for x in (r[3], r[4], bool(r[5]))) for r in creators)
        multi = [r for r in creators if sum(bool(x) for x in (r[3], r[4], bool(r[5]))) >= 2]
        print("1. COVERAGE")
        print(f"   {n} creators: YouTube handle {len(has_yt)}, Instagram handle {len(has_ig)}, Reddit subreddits {len(has_rd)}")
        print(f"   platforms per creator: {dict(sorted(per.items()))}  -> only {len(multi)} of {n} ({100 * len(multi) / n:.0f}%) span 2+ platforms")
        out["coverage"] = {"creators": n, "youtube": len(has_yt), "instagram": len(has_ig), "reddit": len(has_rd),
                           "platforms_per_creator": dict(per), "multi_platform": len(multi)}

        # ---- 2. YouTube links ----------------------------------------------------------------
        yt = q("select channel_id, creator_id::text, channel_handle, title, subscriber_count, coalesce(description,'') from youtube_channels")
        ig_followers = {r[0]: r[1] for r in q("select creator_id::text, follower_count from instagram_profiles where creator_id is not null")}
        found, found_reason = set(), {}
        if YT_CHECKPOINT.exists():
            for k, v in json.loads(YT_CHECKPOINT.read_text(encoding="utf-8")).items():
                if v.get("result") == "found":
                    found.add(k)
                    found_reason[k] = v.get("reason", "")
        print("\n2. YOUTUBE LINKS")
        rows, tier = [], collections.Counter()
        for ch in yt:
            cid = ch[1]
            r = by_id.get(cid)
            if not r:
                continue
            ig = norm_handle(r[4])
            text_ = (ch[5] or "").lower()
            corroborated = bool(ig) and len(ig) >= 4 and ig in text_
            name_tok, title_tok = tokens(r[1]), tokens(ch[3])
            a_name = alnum(r[1])
            name_match = bool(name_tok and title_tok and (len(name_tok & title_tok) / len(name_tok | title_tok) >= 0.5)) \
                or similar(r[1], ch[3]) >= 0.8 or similar(r[1], ch[2]) >= 0.8 \
                or (len(a_name) >= 6 and (a_name in alnum(ch[3]) or a_name in alnum(ch[2])))
            same_handle = bool(ig) and ig == norm_handle(ch[2])
            how = "discovered+verified by script" if cid in found else "original/manual handle"
            ratio = None
            if ig_followers.get(cid) and ch[4]:
                ratio = ch[4] / ig_followers[cid]
            if corroborated:
                level = "corroborated (Instagram handle in channel description)"
            elif name_match:
                level = "name match"
            elif same_handle:
                level = "same handle text on both platforms (weak: fan accounts reuse handles)"
            else:
                level = "NO AUTOMATIC EVIDENCE"
            tier[level] += 1
            rows.append({"creator": r[1], "yt_handle": r[3], "channel_title": ch[3], "subs": ch[4], "ig_followers": ig_followers.get(cid),
                         "sub_to_follower_ratio": ratio, "how": how, "evidence": level,
                         "script_reason": found_reason.get(cid, "")})
        print(f"   {len(rows)} links; how obtained: " + ", ".join(f"{k} {v}" for k, v in collections.Counter(r["how"] for r in rows).items()))
        for k, v in tier.most_common():
            print(f"   {k}: {v}")
        weak = [r for r in rows if r["evidence"] in ("NO AUTOMATIC EVIDENCE",) or r["evidence"].startswith("same handle")
                or (r["sub_to_follower_ratio"] is not None and r["sub_to_follower_ratio"] < 0.02)]
        print("   to review by hand (weak or no evidence, or YouTube audience < 2% of the Instagram one):")
        for r in (rows if args.show_all else weak):
            ratio = f"{r['sub_to_follower_ratio']:.3f}" if r["sub_to_follower_ratio"] is not None else "-"
            print(f"     {r['creator'][:30]:30s} yt:{r['yt_handle'][:24]:24s} title:'{r['channel_title'][:34]}' subs={r['subs']} ig={r['ig_followers']} ratio={ratio} | {r['evidence'][:22]} | {r['how'][:12]} | {r['script_reason'][:70]}")
        out["youtube"] = {"links": len(rows), "evidence": dict(tier), "how_obtained": dict(collections.Counter(r["how"] for r in rows)),
                          "rows": rows}

        # ---- 3. Instagram links ---------------------------------------------------------------
        ig = q("select lower(username), creator_id::text, full_name, follower_count, is_verified from instagram_profiles where creator_id is not null")
        ig_by_user = {r[0]: r for r in ig}
        all_ig_users = {r[0] for r in q("select lower(username) from instagram_profiles")}
        fetched = [r for r in has_ig if norm_handle(r[4]) in all_ig_users]
        never = [r for r in has_ig if norm_handle(r[4]) not in all_ig_users]
        verified = [r for r in ig if r[4]]
        account_defined = [r for r in has_ig if similar(r[1], norm_handle(r[4])) >= 0.8]
        print("\n3. INSTAGRAM LINKS")
        print(f"   {len(has_ig)} creators have an Instagram handle; profile fetched for {len(fetched)}; NEVER fetched for {len(never)} ({100 * len(never) / len(has_ig):.0f}%), so those handles have no check at all")
        print(f"   platform-verified accounts among linked profiles: {len(verified)} of {len(ig)}")
        print(f"   creators whose name is (nearly) their handle, i.e. the creator row was created FROM the account: {len(account_defined)} of {len(has_ig)}")
        print("   note: creator names were back-filled from the same profiles, so name agreement is circular, not independent evidence")
        out["instagram"] = {"with_handle": len(has_ig), "profile_fetched": len(fetched), "never_fetched": len(never),
                            "verified": len(verified), "linked_profiles": len(ig), "name_is_handle": len(account_defined)}

        # ---- 4. duplicates and entity splits ---------------------------------------------------
        owners = collections.defaultdict(set)
        for r in creators:
            for p, hs in (("youtube", [r[3]]), ("instagram", [r[4]]), ("reddit", r[5] or [])):
                for h in hs:
                    if h:
                        owners[(p, norm_handle(h))].add(r[0])
        same_platform = {f"{p}:{h}": [by_id[i][1] for i in v] for (p, h), v in owners.items() if len(v) > 1}
        by_string = collections.defaultdict(set)
        for (p, h), v in owners.items():
            for i in v:
                by_string[h].add((p, i))
        cross_string = {h: [f"{by_id[i][1]} ({p})" for p, i in sorted(v)] for h, v in by_string.items() if len({i for _, i in v}) > 1}
        empty = [r for r in creators if not alnum(r[1])]
        print("\n4. DUPLICATES AND SPLITS")
        print(f"   a handle claimed by 2+ creators on the same platform: {len(same_platform)}")
        print(f"   the same handle text on different creators across platforms: {cross_string or 'none'}")
        print(f"   creators with a non-Latin name (not an error, listed so the numbers add up): {len(empty)}")
        out["duplicates"] = {"same_platform_handle_conflicts": same_platform, "cross_platform_same_string": cross_string}

        # ---- 5. Reddit links ------------------------------------------------------------------------
        links = q("""select p.post_id, p.creator_id::text, lower(coalesce(r.title,'') || ' ' || coalesce(r.body,''))
                     from reddit_post_creators p join reddit_posts r on r.post_id = p.post_id""")

        # A shared surname ("singh", "sharma", "kumar") is not evidence, so a bare name word only
        # counts when no other creator's name contains it. Full name or full handle always counts.
        token_owners = collections.Counter(t for r in creators for t in tokens(r[1]))

        def evidence(cid: str, body: str) -> str | None:
            r = by_id.get(cid)
            if not r:
                return None
            b = re.sub(r"[^a-z0-9 ]", " ", body)
            squash = alnum(body)
            full = alnum(r[1])
            if len(full) >= 4 and full in squash:
                return r[1].lower()
            for h in (norm_handle(r[4]), norm_handle(r[3])):
                if len(alnum(h)) >= 4 and alnum(h) in squash:
                    return h
            for t in tokens(r[1]):
                if len(t) >= 4 and token_owners[t] == 1 and re.search(rf"\b{re.escape(t)}\b", b):
                    return t
            return None

        def strict(cid: str, body: str) -> bool:
            """Full name or full handle appears in the post. Hand review of 30 random links found every
            such link correct (22/22) and found the errors among links that fail this test."""
            r = by_id.get(cid)
            if not r:
                return False
            squash = alnum(body)
            full = alnum(r[1])
            if len(full) >= 4 and full in squash:
                return True
            return any(len(alnum(h)) >= 4 and alnum(h) in squash for h in (norm_handle(r[4]), norm_handle(r[3])))

        def named(cid: str, body: str) -> bool:
            return evidence(cid, body) is not None

        evid = [(pid, cid, named(cid, body)) for pid, cid, body in links]
        k = sum(e for _, _, e in evid)
        strict_flags = {(pid, cid): strict(cid, body) for pid, cid, body in links}
        k_strict = sum(strict_flags.values())
        per_post = collections.defaultdict(list)
        for pid, cid, e in evid:
            per_post[pid].append((cid, e))
        multi_posts = {p: v for p, v in per_post.items() if len(v) > 1}
        pair_support = collections.defaultdict(lambda: [0, 0])
        for p, v in multi_posts.items():
            ids = [cid for cid, _ in v]
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    key = tuple(sorted((ids[i], ids[j])))
                    pair_support[key][0] += 1
                    pair_support[key][1] += int(dict(v)[ids[i]] and dict(v)[ids[j]])
        supported = sum(1 for tot, both in pair_support.values() if both > 0)
        strict_pair = collections.defaultdict(bool)
        for p, v in multi_posts.items():
            ids = [cid for cid, _ in v]
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    if strict_flags[(p, ids[i])] and strict_flags[(p, ids[j])]:
                        strict_pair[tuple(sorted((ids[i], ids[j])))] = True
        supported_strict = sum(strict_pair.values())
        print("\n5. REDDIT LINKS (post -> creator)")
        print(f"   {len(links)} links over {len(per_post)} posts; the post text names the linked creator in {pct(k, len(links))}")
        print(f"   STRICT test (full name or full handle in the post text): {pct(k_strict, len(links))}")
        print(f"   {len(multi_posts)} posts are linked to 2+ creators; they create {len(pair_support)} creator pairs;")
        print(f"   pairs where a shared post names BOTH creators in full (STRICT): {pct(supported_strict, len(pair_support))}")
        print(f"   co-occurrence pairs where at least one shared post names BOTH creators: {pct(supported, len(pair_support))}")
        print("   (a bare shared surname does not count; a link without a name is not necessarily wrong: posts reach a creator through subreddit routing)")
        if args.sample_weak:
            import random

            rng = random.Random(1)
            weak_links = [(pid, cid, body) for pid, cid, body in links if not strict_flags[(pid, cid)]]
            print(f"\n   HAND-REVIEW SAMPLE OF LINKS THAT FAIL THE STRICT TEST ({args.sample_weak} of {len(weak_links)}); judge each: about the creator?")
            for pid, cid, body in rng.sample(weak_links, min(args.sample_weak, len(weak_links))):
                print(f"     [{by_id[cid][1][:26]}] r: {body[:230].strip()!r}")
        if args.sample:
            import random

            rng = random.Random(0)
            print(f"\n   HAND-REVIEW SAMPLE ({args.sample} random links; judge whether the post really is about the creator):")
            for pid, cid, body in rng.sample(links, min(args.sample, len(links))):
                hit = evidence(cid, body)
                at = max(body.find(hit), 0) if hit else 0
                snippet = body[max(0, at - 50): at + 90].replace("\n", " ")
                print(f"     [{by_id[cid][1][:24]}] matched on '{hit}': ...{snippet}...")
        weak_pairs = [pr for pr in pair_support if not strict_pair.get(pr)]
        weak_deg = collections.Counter(c_ for pr in weak_pairs for c_ in pr)
        strict_deg = collections.Counter(c_ for pr, ok in strict_pair.items() if ok for c_ in pr)
        only_weak = [c_ for c_ in weak_deg if c_ not in strict_deg]
        print(f"   {len(weak_pairs)} pairs rest only on posts that do not name both creators in full; {len(only_weak)} creators have co-occurrence edges ONLY of that kind")
        print("   creators with the most such pairs: " + "; ".join(f"{by_id[c_][1][:24]} ({n_})" for c_, n_ in weak_deg.most_common(8)))
        big = q("""select p.post_id, count(*) n, max(left(r.title, 70)) from reddit_post_creators p
                   join reddit_posts r on r.post_id = p.post_id group by p.post_id having count(*) >= 8 order by n desc""")
        big_ids = {b[0] for b in big}
        pair_posts = collections.defaultdict(set)
        for p_, v in multi_posts.items():
            ids = sorted(cid for cid, _ in v)
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    pair_posts[(ids[i], ids[j])].add(p_)
        only_roster = sum(1 for ps in pair_posts.values() if ps <= big_ids)
        print(f"   {len(big)} roster/auction/stat posts name 8+ creators each (largest: " + "; ".join(f"{b[1]} in '{b[2]}'" for b in big[:3]) + ")")
        print(f"   co-occurrence pairs that exist ONLY because of such posts: {pct(only_roster, len(pair_posts))}  (a shared roster is a mention, not a relationship)")
        out["reddit_roster_posts"] = {"posts_8plus": len(big), "pairs_only_from_them": only_roster, "pairs": len(pair_posts)}
        out["reddit_weak_pairs"] = {"pairs": len(weak_pairs), "creators_only_weak": len(only_weak),
                                    "top": [(by_id[c_][1], n_) for c_, n_ in weak_deg.most_common(10)]}
        out["reddit"] = {"links": len(links), "name_evidenced_lenient": k, "name_evidenced_strict": k_strict,
                         "multi_creator_posts": len(multi_posts), "pairs": len(pair_support),
                         "pairs_naming_both_lenient": supported, "pairs_naming_both_strict": supported_strict}

        # ---- 6. Instagram post ownership ----------------------------------------------------------------
        print("\n6. INSTAGRAM POST OWNERSHIP (Track A audit, re-checked today)")
        if CHECKPOINT.exists():
            audit = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
            was_wrong = [p for p, v in audit.items() if norm_handle(v["stored"]) != norm_handle(v["real"])]
            cur = {r[0]: r[1] for r in q("select post_id, username from instagram_posts where post_id = any(:i)", i=list(audit))}
            still = [p for p in was_wrong if p in cur and norm_handle(cur[p]) != norm_handle(audit[p]["real"])]
            total = q("select count(*) from instagram_posts")[0][0]
            sponsored = q("select post_id from instagram_posts where is_sponsored")
            sp_audited = [r[0] for r in sponsored if r[0] in audit]
            sp_wrong_then = [p for p in sp_audited if p in was_wrong]
            print(f"   at audit time: {pct(len(was_wrong), len(audit))} of {len(audit)} audited posts were filed under the wrong account")
            print(f"   today: {len(still)} of those {len(was_wrong)} are still wrong (the rest were re-attributed)")
            print(f"   coverage: {len(audit)} of {total} posts audited ({100 * len(audit) / total:.0f}%); sponsored posts audited {len(sp_audited)} of {len(sponsored)}"
                  f" (of the audited sponsored ones, {len(sp_wrong_then)} had been wrong)")
            lo, hi = wilson(len(was_wrong), len(audit))
            # Track A added orchestrator.own_post_paths (collection-time filter) in commit 695858a on 2026-08-19.
            fetched = {r[0]: r[1] for r in q("select post_id, fetched_at from instagram_posts")}
            cutoff = "2026-08-19"
            pre = [p for p in audit if str(fetched.get(p, ""))[:10] < cutoff]
            post = [p for p in audit if str(fetched.get(p, ""))[:10] >= cutoff]
            pre_w = sum(p in was_wrong for p in pre)
            post_w = sum(p in was_wrong for p in post)
            print(f"   by fetch date (collection-time filter landed {cutoff}): audited posts fetched before it: {pct(pre_w, len(pre))} wrong; on/after it: {pct(post_w, len(post))} wrong")
            unaud = [p for p in fetched if p not in audit]
            unaud_pre = [p for p in unaud if str(fetched[p])[:10] < cutoff]
            sp_ids = {r[0] for r in sponsored}
            unaud_sp_pre = [p for p in unaud_pre if p in sp_ids]
            plo, phi = wilson(pre_w, len(pre))
            print(f"   NOT audited: {len(unaud)} posts ({len(unaud_pre)} fetched before the filter, {len(unaud) - len(unaud_pre)} after); sponsored not audited: {len(sponsored) - len(sp_audited)} ({len(unaud_sp_pre)} before the filter)")
            print(f"   at the pre-filter rate ({100 * plo:.0f}-{100 * phi:.0f}%) the {len(unaud_pre)} unaudited pre-filter posts would hold about {len(unaud_pre) * plo:.0f}-{len(unaud_pre) * phi:.0f} misattributed posts, "
                  f"{len(unaud_sp_pre) * plo:.1f}-{len(unaud_sp_pre) * phi:.1f} of them sponsored; the post-filter posts carry the lower post-filter rate")
            out["post_ownership"] = {"audited": len(audit), "wrong_at_audit": len(was_wrong), "still_wrong_today": len(still), "posts_total": total,
                                     "sponsored_total": len(sponsored), "sponsored_audited": len(sp_audited), "sponsored_wrong_at_audit": len(sp_wrong_then),
                                     "wrong_pre_filter": [pre_w, len(pre)], "wrong_post_filter": [post_w, len(post)],
                                     "unaudited_pre_filter": len(unaud_pre), "unaudited_sponsored_pre_filter": len(unaud_sp_pre)}

        # ---- 7. null creator_id ---------------------------------------------------------------------------------
        print("\n7. NULL creator_id")
        nulls = {}
        for t in ("instagram_profiles", "reddit_profiles", "youtube_channels", "instagram_posts", "youtube_videos", "reddit_posts"):
            a, b = q(f"select count(*) filter (where creator_id is null), count(*) from {t}")[0]
            nulls[t] = (a, b)
            print(f"   {t:20s} {a:6d} of {b:6d} have no creator_id")
        npost = q("select count(*) filter (where is_sponsored) from instagram_posts where creator_id is null")[0][0]
        nev, tev = q("select count(*) filter (where creator_id is null), count(*) from creator_sponsorship_events")[0]
        print(f"   {nev} of {tev} sponsorship events ({100 * nev / tev:.0f}%) have NO creator (the {npost} sponsored posts with creator_id NULL are included by the view); with no event creator they cannot seed a training pair, so those treatment labels are lost")
        out["null_creator_events"] = {"events_without_creator": nev, "events": tev}
        print("   the null profile rows are fans/commenters/brands scraped for context, not creators. Feature building reads profiles with")
        print("   `creator_id IN (known creator ids)`, which never matches NULL (regression test: backend/tests/test_feature_store.py, test_profiles_and_posts_with_no_creator_id...).")
        out["null_creator_id"] = {t: {"null": a, "total": b} for t, (a, b) in nulls.items()}

    # ---- 8. cross-platform support in the GAIL training pairs ---------------------------------------------------------
    print("\n8. CROSS-PLATFORM SUPPORT")
    try:
        from ml._scipy_compat import avoid_blocked_scipy_solver

        avoid_blocked_scipy_solver()
        import torch

        ck = torch.load(ROOT / "models" / "gail_checkpoint.pt", map_location="cpu", weights_only=False)
        pairs = ck["training_pair_details"]
        kinds = collections.Counter()
        for p in pairs:
            plats = sorted(k for k, v in (p.get("platform_lifts") or {}).items() if v and v.get("lift") is not None)
            kinds["+".join(plats) if plats else "no usable lift"] += 1
        multi_lift = sum(v for k, v in kinds.items() if "+" in k)
        print(f"   {len(pairs)} (event, neighbour) training pairs; platforms that gave a measurable lift: {dict(kinds)}")
        print("   'no usable lift' = the neighbour has activity before and after the event, but never on the SAME platform (before on one, after on another): dropped from training")
        print(f"   pairs measured on 2+ platforms: {multi_lift} of {len(pairs)}; {len(multi)} creators have handles on 2+ platforms")
        print(f"   GAIL effective labelled nodes: {ck['pair_count'].get('effective_N_labeled_nodes')}; cross_platform_only pairs: {ck['pair_count'].get('cross_platform_only')}")
        out["cross_platform_pairs"] = {"pairs": len(pairs), "by_platform_combo": dict(kinds), "measured_on_2plus": multi_lift,
                                       "pair_count_meta": {k: ck["pair_count"].get(k) for k in ("computable_pairs", "same_platform_computable", "cross_platform_only", "effective_N_labeled_nodes")}}
    except Exception as e:  # checkpoint/torch unavailable
        print(f"   skipped ({e})")

    (ROOT / "models" / "link_audit.json").write_text(json.dumps(out, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print("\nsaved models/link_audit.json")


if __name__ == "__main__":
    main()
