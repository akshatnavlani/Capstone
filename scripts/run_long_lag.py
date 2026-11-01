"""Lag detection on the LONG history (months, not the 18 days of growth readings). READ ONLY on the database; writes models/long_lag.json.

    python scripts/run_long_lag.py [--placebo 1000] [--power] [--out models/long_lag.json]

WHY (29 Oct 2026): the growth-reading lag test (scripts/run_snapshot_lag.py) rests on readings collected since 11 Oct, so only 65 clean Instagram posts qualify. Two kinds of
data reach back much further and are already in the database:

  * every collected YouTube comment carries its own publish time (165,862 comments, 34,309 of them on videos more than 72 hours old, from 148 creators, Mar to Oct 2026 and
    earlier): comments arriving on a creator's OLDER videos are a record of audience attention, even when no growth reading was taken;
  * every YouTube upload and Instagram post has a time (59,000 videos, 1,084 posts, from 20 Dec 2023 / 20 Feb 2024): posting behaviour over 2 years.

Same method as the growth-reading test (ml/temporal/snapshot_lag.py): around each Instagram post, the creator's activity in 12-hour windows from 48 h before to 48 h after is
compared with the creator's own rate before the post, against a placebo at the same hour of day on other days. Tests:
  control        YouTube upload -> comments on that channel (must be detected, or the method is broken)
  ig_to_comments Instagram post -> comments arriving on YouTube videos older than 72 h (attention reaching the catalogue)
  ig_to_comments_pure   same, only Instagram posts with no YouTube upload within 24 h
  ig_to_uploads  Instagram post -> YouTube uploads (does the creator upload sooner after posting on Instagram?)
CAVEAT: comments were collected as the newest comments per video at one moment, so older months hold fewer comments; each unit is compared with its own surrounding rate, which
removes most of that, but it is an approximation. With --power it also plants a known extra number of comments 12-36 h after real posts (SIMULATED) to show what size the test can find.
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_snapshot_lag as lag  # noqa: E402
from ml.temporal.snapshot_lag import WUnit, weighted_event_study  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
V = "(select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed','probable'))"


def load(cur):
    cur.execute(f"select video_id, creator_id::text, extract(epoch from published_at)/3600.0 from youtube_videos where creator_id in {V} and published_at is not null")
    pub = {v: (c, float(h)) for v, c, h in cur.fetchall()}
    uploads = defaultdict(list)
    for c, h in pub.values():
        uploads[c].append(h)
    cur.execute(f"select c.video_id, extract(epoch from c.published_at)/3600.0 from youtube_comments c where c.video_id in (select video_id from youtube_videos where creator_id in {V}) and c.published_at is not null")
    comments_all, comments_cat = defaultdict(list), defaultdict(list)
    for vid, h in cur.fetchall():
        if vid not in pub:
            continue
        cid, born = pub[vid]
        comments_all[cid].append(float(h))
        if float(h) - born > 72.0:
            comments_cat[cid].append(float(h))
    cur.execute(f"select creator_id::text, extract(epoch from posted_at)/3600.0 from instagram_posts where creator_id in {V} and posted_at is not null")
    ig = defaultdict(list)
    for c, h in cur.fetchall():
        ig[c].append(float(h))
    srt = lambda d: {k: np.sort(np.array(v)) for k, v in d.items()}  # noqa: E731
    return srt(uploads), srt(comments_all), srt(comments_cat), srt(ig)


def units_for(events, series, span, margin=48.0):
    out = []
    for cid, ev in events.items():
        s = series.get(cid)
        if s is None or len(s) < 20:
            continue
        lo, hi = span(cid, s)
        for e in ev:
            if lo + margin <= e <= hi - margin:
                out.append(WUnit(float(e), s, np.ones(len(s)), lo, hi, cid))
    return out


def plant(units, s, rng):
    out = []
    for u in units:
        if s == 0:
            out.append(u)
            continue
        rate = float(u.weights.sum()) / max(u.hi - u.lo, 1.0)
        n_extra = max(int(round(s * rate * 24.0)), 0)
        extra = u.t0 + rng.uniform(12.0, 36.0, size=n_extra)
        t = np.concatenate([u.times, extra])
        t.sort()
        out.append(WUnit(u.t0, t, np.ones(len(t)), u.lo, u.hi, u.creator))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--placebo", type=int, default=1000)
    ap.add_argument("--power", action="store_true")
    ap.add_argument("--out", default=str(lag.ROOT / "models" / "long_lag.json"))
    args = ap.parse_args()
    import psycopg2

    conn = psycopg2.connect(lag.database_url(), connect_timeout=15)
    conn.set_session(readonly=True)
    uploads, comments_all, comments_cat, ig = load(conn.cursor())
    conn.close()
    span_of = lambda cid, s: (float(s[0]), float(s[-1]))  # noqa: E731   the period in which the creator's own series is observed
    now_h = datetime.now(timezone.utc).timestamp() / 3600.0

    pure_events = {c: np.array([e for e in ev if not len(uploads.get(c, [])) or np.min(np.abs(uploads[c] - e)) > 24]) for c, ev in ig.items()}
    sets = {
        "control: YouTube upload -> comments on that channel": units_for(uploads, comments_all, span_of),
        "ig_to_comments: Instagram post -> comments on YouTube videos older than 72 h": units_for(ig, comments_cat, span_of),
        "ig_to_comments_pure: same, only Instagram posts with no YouTube upload within 24 h": units_for(pure_events, comments_cat, span_of),
        "ig_to_uploads: Instagram post -> YouTube uploads": units_for(ig, uploads, lambda cid, s: (float(s[0]), now_h)),
    }
    results = []
    for name, units in sets.items():
        study = weighted_event_study(units, lag.EDGES, lag.N_PRE, n_placebo=args.placebo, seed=7)
        r = lag.summarise(name, study, "")
        results.append(r)
        if r["status"] != "ok":
            print(f"- {name}: {r['status']}", flush=True)
            continue
        print(f"- {name}\n    units {r['n_units']}, creators {r['n_creators']}")
        print("    window      " + "  ".join(f"{w:>9}" for w in r["windows"]))
        print("    excess      " + "  ".join(f"{x:9.3f}" for x in r["excess_in_units_of_the_creators_mean_rate"]))
        print("    p (1-sided) " + "  ".join(f"{x:9.3f}" for x in r["p_one_sided"]))
        print(f"    smallest p after the event: {r['smallest_p_after_event']:.4f} in {r['window_of_smallest_p']} -> {'DETECTED (survives correction)' if r['detected_after_correction'] else 'not detected after correction'}", flush=True)
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "method_check_passed": bool(results[0].get("detected_after_correction")), "results": results,
           "limits": "comments are the newest comments per video collected at one moment, so older months are thinner; each unit is compared with its own surrounding rate. Posting and attention are not sales."}
    if args.power:
        units = sets["ig_to_comments: Instagram post -> comments on YouTube videos older than 72 h"]
        power = {}
        for s in (0.0, 0.05, 0.1, 0.25, 0.5):
            hits = 0
            reps = 5
            for k in range(reps):
                st = weighted_event_study(plant(units, s, np.random.default_rng(100 * k + int(s * 100))), lag.EDGES, lag.N_PRE, n_placebo=300, seed=7 + k)
                hits += int(st is not None and float(st.p_values[lag.AFTER].min()) < 0.0125)
            power[str(s)] = hits / reps
            print(f"  SIMULATED +{s * 100:3.0f}% extra comments 12-36 h after a post: found in {hits}/{reps}", flush=True)
        out["simulated_power"] = {"how": "extra comments of s x the creator's own mean rate x 24 h, spread over 12-36 h after each real Instagram post; found = smallest after-event p < 0.0125", "found_share": power}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
