"""Collect everything the Analysis tab shows into one file: models/analysis_dashboard.json.
READ ONLY on the database. Served by GET /analysis (backend/app/routers/analysis.py).

    python scripts\\export_analysis_dashboard.py      (about a minute: loads CLIP and BERT for the feature score)

Gathers the saved results of S1 (lag tests), S3 (fusion calibration), S7 (filter and cost) and S8
(linking audit), and computes what the interactive parts need:
  - the daily performance curves of the creators who are on both YouTube and Instagram (lag slider)
  - for six briefs, each creator's three fusion inputs (weight sliders re-rank live in the browser)
  - for the same briefs, the top creators by feature score and what each score is built from
  - the live risk alerts and the audience-mood summary
Rerun this after any of the audit scripts to refresh the tab.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

BRIEFS = ["fitness", "cricket bat and gear", "chess coaching", "makeup and skincare", "smartphone reviews", "yoga and wellness classes"]
# Text-method AUC measured in S2 against category-derived relevance (fitness: 78 matching creators, cricket: 6).
S2_AUC = {
    "fitness": {"BERT pooler output": 0.71, "BERT mean-pooled": 0.74, "CLIP text": 0.83, "CLIP text + BERT mean (used)": 0.85},
    "cricket bat and gear": {"BERT pooler output": 0.42, "BERT mean-pooled": 0.48, "CLIP text": 0.65, "CLIP text + BERT mean (used)": 0.57},
}


# Hand-judged samples from the S7 and S8 reports (one reviewer, small samples; the commands that
# regenerate each sample are in the audit scripts). Kept here so the tab shows them with the data.
HAND_REVIEW_S7 = {
    "region_unknown_split": {"india": 45, "foreign": 7, "cannot_tell": 8, "n": 60, "note": "judged by name, language and context"},
    "product_recovered_sensible": {"correct": 39, "n": 40, "note": "athlete creators recovered by stemming for an athletic product"},
    "substring_only_keeps": {"accidents": 13, "n": 24, "note": "3-letter words such as 'mat' and 'bat' matched inside other words"},
}
HAND_REVIEW_S8 = {
    "reddit_strict_sample": {"correct": 22, "n": 22},
    "reddit_weak_sample": {"correct": 8, "wrong": 27, "unclear": 5, "n": 40},
    "collab_pairs_sample": {"plausible": 30, "same_entity": 2, "cannot_judge": 8, "clearly_false": 0, "n": 40},
    "non_creator_accounts": {"low": 14, "high": 17, "reviewed": 135, "classifier_flags": 0},
    "youtube_doubtful": {"low": 2, "high": 4, "links": 41},
}


def load(name: str):
    return json.loads((ROOT / "models" / name).read_text(encoding="utf-8"))


def rnd(a, n=3):
    return [None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n) for x in a]


def gail_scaling():
    p = ROOT / "models" / "semisynth_scale.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = [{"scenario": k, "exposed": int(n), "mean_abs_error": v["mean_abs_error"], "reps": v["reps"]}
            for k, per in d["results"].items() for n, v in per.items() if v.get("mean_abs_error") is not None]
    return {"planted_effect": d["planted_effect"], "noise": d["noise"], "rows": rows}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    url = os.environ.get("DATABASE_URL") or re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    os.environ["DATABASE_URL"] = url
    os.environ["CREATOR_FEATURES_DISABLED"] = "1"  # we call the scorer directly below
    from ml._scipy_compat import avoid_blocked_scipy_solver

    avoid_blocked_scipy_solver()
    from sqlalchemy import text
    from sqlmodel import Session, create_engine, select

    from app import creator_features as cf
    from app.models import Creator
    from app.spillover import get_spillover_batch
    from app.temporal import get_temporal_batch
    from ml.creator_embeddings import QueryEmbedder
    from ml.feature_extraction import FeatureExtractor
    from ml.temporal.performance_lag import daily_series, performance_scores

    engine = create_engine(url)
    with Session(engine) as s:
        creators = s.exec(select(Creator)).all()
        ids = [str(c.creator_id) for c in creators]
        sp = get_spillover_batch(ids)
        tm = get_temporal_batch(s)
        alerts = s.exec(text("""select a.severity, cr.name, src.name, a.reason, a.created_at from riskalert a
                               join creators cr on cr.creator_id = a.creator_id
                               left join creators src on src.creator_id = a.propagated_from_creator_id
                               where a.source = 'sentiment_propagation' and not a.resolved order by a.id""")).all()
        yt = s.exec(text("""select creator_id::text, published_at, comment_count, coalesce(fetched_at, now()) from youtube_videos
                            where creator_id is not null and published_at is not null and comment_count is not null""")).all()
        ig = s.exec(text("""select creator_id::text, posted_at, comment_count, coalesce(fetched_at, now()) from instagram_posts
                            where creator_id is not null and posted_at is not null and comment_count is not null""")).all()

    names = {str(c.creator_id): c.name for c in creators}

    # ---- S1: audience mood ---------------------------------------------------------------------
    sent_art = load("temporal_sentiment.json")["creators"]
    safety = np.array([c["safety_score"] for c in sent_art])
    hist, edges = np.histogram(safety, bins=10, range=(0.3, 0.9))
    sentiment = {
        "scored": len(sent_art), "total": len(creators), "mean": round(float(safety.mean()), 3), "min": round(float(safety.min()), 3),
        "max": round(float(safety.max()), 3), "histogram": [{"lo": round(float(edges[i]), 2), "hi": round(float(edges[i + 1]), 2), "n": int(hist[i])} for i in range(10)],
        "lowest": [{"name": c["name"], "safety": round(c["safety_score"], 3), "comments": c["n_comments"]} for c in sorted(sent_art, key=lambda c: c["safety_score"])[:8]],
        "highest": [{"name": c["name"], "safety": round(c["safety_score"], 3), "comments": c["n_comments"]} for c in sorted(sent_art, key=lambda c: -c["safety_score"])[:8]],
    }
    alert_rows = [{"severity": a[0], "creator": a[1], "source": a[2], "reason": a[3]} for a in alerts]

    # ---- S1: same-creator curves for the lag slider ----------------------------------------------------
    def per_creator(rows):
        by: dict[str, list] = {}
        for cid, ts, cm, fetched in rows:
            by.setdefault(cid, []).append((ts, cm, fetched))
        out = {}
        for cid, items in by.items():
            days = np.array([int(t.timestamp() // 86400) for t, _, _ in items])
            age = np.array([(f - t).total_seconds() / 86400 for t, _, f in items])
            z = performance_scores([cm for _, cm, _ in items], age, 6)
            if z is not None:
                out[cid] = daily_series(days, z)
        return out

    yts, igs = per_creator(yt), per_creator(ig)
    curves = [{"name": names.get(c, c), "youtube": [[d, round(v, 3)] for d, v in sorted(yts[c].items())],
               "instagram": [[d, round(v, 3)] for d, v in sorted(igs[c].items())]} for c in yts if c in igs]

    # ---- S2 + S3: three fusion inputs per brief ---------------------------------------------------------------
    art = cf.load_artifact()
    embedder = QueryEmbedder.from_extractor(FeatureExtractor(max_thumbnails=5))
    pos = {cid: i for i, cid in enumerate(art["ids"])}
    meta = [{"id": c, "name": names[c], "category": next(x.category for x in creators if str(x.creator_id) == c), "basis": sp[c]["basis"]} for c in ids]
    spill = rnd([sp[c]["spillover_unit"] for c in ids])
    sent_v = rnd([tm.get(c, {}).get("sentiment_risk_score", 0.5) for c in ids])
    briefs, s2_briefs = {}, {}
    for b in BRIEFS:
        res = cf.score_query(b, art, embedder)
        feat = [res[c]["score"] if c in res else 0.5 for c in ids]
        briefs[b] = {"spillover": spill, "sentiment": sent_v, "feature": rnd(feat)}
        top = sorted(ids, key=lambda c: -(res[c]["score"] if c in res else 0.5))[:10]
        s2_briefs[b] = []
        for c in top:
            i = pos.get(c)
            s2_briefs[b].append({"name": names[c], "score": round(res[c]["score"], 3), "has_image": bool(art["has_img"][i]) if i is not None else False,
                                 "has_text": bool(art["has_text"][i]) if i is not None else False,
                                 "engagement": None if i is None or not np.isfinite(art["engagement"][i]) else round(float(art["engagement"][i]), 4),
                                 "reach": None if i is None or not np.isfinite(art["log_reach"][i]) else round(float(np.expm1(art["log_reach"][i]))) })
    s2 = {"auc": S2_AUC, "briefs": s2_briefs,
          "coverage": {"creators": len(ids), "with_text": int(art["has_text"].sum()), "with_thumbnails": int(art["has_img"].sum()),
                       "with_neither": int((~art["has_text"] & ~art["has_img"]).sum()),
                       "with_engagement": int(np.isfinite(art["engagement"]).sum()), "with_reach": int(np.isfinite(art["log_reach"]).sum())}}

    # ---- S9: live results (lag on the growth readings, spillover on the real network, detection curve, data inventory) ------------------
    ver_ids = {r[0] for r in create_engine(url).connect().execute(text(
        "select creator_id::text from creator_verification where creator_id is not null and link_level in ('confirmed','probable')")).all()}
    V = "(select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed','probable'))"
    STRONG = "('official_label','spoken','creator_comment','disclosure_tag')"
    with create_engine(url).connect() as conn:
        def one(q: str) -> int:
            return int(conn.execute(text(q)).scalar() or 0)
        inventory = {
            "verified_creators": len(ver_ids),
            "youtube_videos": one(f"select count(*) from youtube_videos where creator_id in {V}"),
            "youtube_comments": one(f"select count(*) from youtube_comments where video_id in (select video_id from youtube_videos where creator_id in {V})"),
            "growth_readings": one("select count(*) from post_snapshots"),
            "days_of_readings": one("select count(distinct fetched_at::date) from post_snapshots"),
            "instagram_creators": one(f"select count(distinct creator_id) from instagram_posts where creator_id in {V}"),
            "instagram_posts": one(f"select count(*) from instagram_posts where creator_id in {V}"),
            "sponsorship_events": one("select count(*) from creator_sponsorship_events where creator_id is not null"),
            "strong_evidence_events": one(f"select count(*) from creator_sponsorship_events where creator_id is not null and sponsorship_evidence in {STRONG}"),
            "sponsoring_creators": one("select count(distinct creator_id) from creator_sponsorship_events where creator_id is not null"),
        }
    basis_counts: dict[str, int] = {}
    for c in ids:
        if c in ver_ids:
            basis_counts[sp[c]["basis"]] = basis_counts.get(sp[c]["basis"], 0) + 1
    # creators of the 150 with at least one graph link: what the saved model reads (collaboration + co-occurrence), then plus the shared-brand relation
    from app.feature_store import build_co_occurrence_edges, build_collaboration_edges, build_mention_edges, build_shared_brand_edges

    with Session(engine) as graph_session:
        base_edges = build_collaboration_edges(graph_session) + build_co_occurrence_edges(graph_session)
        brand_edges = build_shared_brand_edges(graph_session)
        mention_edges = build_mention_edges(graph_session)

    def linked(edges) -> set[str]:
        return {str(x) for e in edges for x in (e.source_creator_id, e.target_creator_id)} & ver_ids

    graph_links = {"of": len(ver_ids), "today": len(linked(base_edges)), "shared_brand_alone": len(linked(brand_edges)), "with_shared_brand": len(linked(base_edges + brand_edges)),
                   "mentions_alone": len(linked(mention_edges)), "with_shared_brand_and_mentions": len(linked(base_edges + brand_edges + mention_edges))}
    lag_live = load("snapshot_lag.json")
    s9 = {
        "as_of": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "inventory": inventory,
        "spillover_basis_counts": basis_counts,
        "graph_links": graph_links,
        "placebo": load("spillover_placebo_test.json"),
        "lag": {"days_of_readings": lag_live["days_of_readings"], "method_check": lag_live["method_check"], "limits": lag_live["limits"],
                "results": [{k: r.get(k) for k in ("name", "n_units", "n_creators", "smallest_p_after_event", "window_of_smallest_p", "detected_after_correction", "note")} for r in lag_live["results"]]},
        "spillover_restricted_150": load("spillover_effect_restricted150.json"),
        "semisynthetic": load("sim_semisynthetic_benchmark.json"),
        "sim_lag_power": load("sim_lag_power.json"),
        "label_quality": {k: v for k, v in load("sponsorship_quality.json").items() if k not in ("suggested_to_label",)},
        # Detection curve on REAL outcomes with a planted effect: scripts/run_power_analysis.py (real structure: the 11 real exposed rows against the real controls).
        # Each share list follows the script's DELTAS: [0 (false alarm), 0.25, 0.50, 0.75, 1.00, 1.50].
        "power_curve": [
            {"exposed": int(n), "effect_0.25": round(100 * s[1]), "effect_0.50": round(100 * s[2]), "effect_0.75": round(100 * s[3]), "effect_1.00": round(100 * s[4]), "false_alarm": round(100 * s[0])}
            for n, s in load("power_analysis.json")["real_structure"]["share_detected"].items()
        ],
        # Hybrid what-if (31 Oct 2026): extra exposed creators are SIMULATED by picking real creators at random and planting the effect on their real outcomes (the "stand_ins" variant:
        # false alarms stay near 3%). It shows how many exposed cases would be needed; it is never used in a score or reported as a finding.
        "power_curve_simulated": [
            {"exposed": int(n), "effect_0.25": round(100 * s[1]), "effect_0.50": round(100 * s[2]), "effect_0.75": round(100 * s[3]), "effect_1.00": round(100 * s[4]), "false_alarm": round(100 * s[0])}
            for n, s in load("power_analysis.json")["stand_ins"]["share_detected"].items()
        ],
        "power_real_exposed": int(load("power_analysis.json")["real_exposed"]),
        # SIMULATED accuracy of GAIL-R as the number of exposed creators grows (run_semisynth_scale.py, real graph and features, planted effect); absent until that run has been copied to models/
        "gail_scaling": gail_scaling(),
        "label_noise": load("label_noise_sensitivity.json") if (ROOT / "models" / "label_noise_sensitivity.json").exists() else None,
        "spillover_cases": load("spillover_cases.json") if (ROOT / "models" / "spillover_cases.json").exists() else None,
        # E4 and E5 (31 Oct 2026, scripts/run_e4_e5.py): SIMULATED benchmark plus the real-data E5 sensitivity
        "e4_e5": load("e4_e5_results.json") if (ROOT / "models" / "e4_e5_results.json").exists() else None,
    }

    # S10 (30 Oct 2026): the YouTube-vs-Instagram comparison, Granger, ad fatigue, long lag, promotion behaviour and the GAIL real-data results, each from its own results file
    pairs, fat, ll, promo = load("platform_pairs.json"), load("ad_fatigue.json"), load("long_lag.json"), load("promotion_behaviour.json")
    s10 = {
        "pairs": {k: pairs[k] for k in ("window_hours", "pairs", "creators_with_pairs", "median_difference", "median_difference_adjusted", "share_pairs_instagram_better_adjusted",
                                         "pairs_with_text_overlap", "median_difference_with_overlap", "placebo", "calibration_subtracted", "granger", "limits")}
                 | {"stronger_platform_counts": {k: sum(c["stronger_platform"] == k for c in pairs["creators"]) for k in ("Instagram", "YouTube", "balanced", "not enough pairs")}},
        "ad_fatigue": {k: fat[k] for k in ("window_days", "creators", "organic_videos", "results", "limits")},
        "long_lag": {"method_check_passed": ll["method_check_passed"], "limits": ll["limits"],
                     "results": [{k: r.get(k) for k in ("name", "n_units", "n_creators", "smallest_p_after_event", "window_of_smallest_p", "detected_after_correction")} for r in ll["results"]]},
        "promotion": {"disclosure": promo["disclosure"], "response": promo["response"], "limits": promo["limits"]},
        "gail": load("gail_real_results.json"),
        "power": {k: v for k, v in load("power_analysis.json").items() if k in ("real_exposed", "real_controls", "real_estimate", "real_se", "deltas", "reps", "real_structure", "limits")},
    }

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "s10": s10,
        "s9": s9,
        "s1": {"sentiment": sentiment, "alerts": alert_rows, "lag_posting": load("temporal_lag.json"), "lag_event": load("event_lag.json"),
               "lag_same_creator": load("same_creator_lag.json"), "curves": curves},
        "s2": s2,
        "s3": {"calibration": load("fusion_calibration.json"), "baseline_weights": [0.2, 0.4, 0.4], "creators": meta, "briefs": briefs},
        "s7": {**load("filter_cost_audit.json"), "hand_review": HAND_REVIEW_S7},
        "s8": {**load("link_audit.json"), "hand_review": HAND_REVIEW_S8},
    }
    # the youtube/instagram row lists in link_audit can be long; the tab only needs the summaries
    out["s8"].get("youtube", {}).pop("rows", None)
    (ROOT / "models" / "analysis_dashboard.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size = (ROOT / "models" / "analysis_dashboard.json").stat().st_size
    print(f"saved models/analysis_dashboard.json ({size / 1024:.0f} KB): {len(curves)} creators with both platforms, {len(alert_rows)} alerts, {len(briefs)} briefs x {len(ids)} creators")


if __name__ == "__main__":
    main()
