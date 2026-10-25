"""Prod training entrypoint — train ONCE on ALL computable pairs.

This is the loadable artifact producer for Track C (P1.6 unblock). Unlike
`scripts/train_holdout_round3.py` (LEAVE-ONE-OUT for evaluation, 10 folds),
this trains a SINGLE model on every computable (event, neighbour) pair from
the fresh `pair_count.py` canonical definition, then saves a checkpoint
Track C can `torch.load`.

Reuses `ml/gail_model.py`, `ml/training.py`, `ml/schema.py`. Handles the
two data-quality bugs already fixed in `compute_training_pair_deltas.py`:
  1. NULL→0 coalesce on sparse engagement columns fabricated fake lifts.
     Fix: exclude posts where BOTH engagement cols are NULL (fully-unmeasured)
     is not enough; require BOTH cols non-null (fully-measured) to count a
     post at all (see Layer 2 in that file).
  2. Partial measurement bias — same fix.

Also normalizes creator features before the propensity head so propensity
does not saturate to 1.000 on held-out nodes (Round 3 finding GRAPH_SCHEMA:
799, CAPSTONE_NEXT_STEPS 795).

Saves to `models/gail_checkpoint.pt` (state_dict + config + feature_scaler
+ training_pair_ids + git SHA + pair_count 4-reading). Also writes
`models/feature_scaler.json` separately.

Usage:
  DATABASE_URL=... .venv\\Scripts\\python.exe scripts/train_prod_model.py
  # optional: pass 4 feature-store JSONs to reuse pre-dumped files instead of live DB feature build:
  #   .venv\\Scripts\\python.exe scripts/train_prod_model.py creators.json collab.json cooccur.json sponsorships.json

Deterministic: seed 0, scaler computed from training data only, 100 epochs.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
from datetime import timedelta
import subprocess
import sys
from pathlib import Path

import torch

# ---------------------------------------------------------------------------
# Env handling — load .env like Track A's orchestrator (per-worktree .env)
# ---------------------------------------------------------------------------

def load_env() -> dict:
    env = dict(os.environ)
    # try repo-root .env and track-a .env as fallbacks
    candidates = [
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / "track-a-data-infra" / ".env",
    ]
    for p in candidates:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    env.setdefault(k, v)
                    os.environ.setdefault(k, v)
            break
    return env

ENV = load_env()

# Track-A ingestion dir for fresh pair_count import
import psycopg2  # noqa: E402

# Track A's canonical pair definition. Imported through _track_a because
# pair_count's own `from orchestrator import ENV` otherwise drags in the
# ingestion orchestrator, which refuses to import without the opencli browser
# tool on PATH. See scripts/_track_a.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _track_a import import_pair_count  # noqa: E402

pair_count_compute = import_pair_count(ENV).compute

from ml.feature_extraction import FeatureExtractor, RawCreatorRecord  # noqa: E402
from ml.bot_detection import load_bot_scores  # noqa: E402
from ml.engagement_lift import (  # noqa: E402
    PLATFORM_TABLES,
    platform_engagement,
    platform_lift,
    row_target,
    lift_from_posts,
    load_platform_posts,
)
from ml.feature_scaling import compute_feature_scaler  # noqa: E402
from ml.gail_model import GAILModel  # noqa: E402
from ml.target_clustering import (  # noqa: E402
    DEFAULT_WINDOW_DAYS,
    cluster_events,
    per_creator_targets,
    summarize,
)
from ml.time_indexed_treatment import (  # noqa: E402
    build_control_observations,
    matched_did,
    build_observations,
    drop_self_sponsored,
    group_by_span,
    sponsorship_dates,
    treatment_in_span,
)
from ml.schema import (  # noqa: E402
    BRAND_METADATA_DIM,
    CREATOR_FEATURE_DIM,
    NUM_BRAND_CATEGORIES,
    empty_hetero_data,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Must match backend/app/feature_store.py CREATOR_CATEGORIES exactly
CREATOR_CATEGORIES = (
    "athlete",
    "team",
    "league",
    "fitness_influencer",
    "lifestyle_influencer",
    "other",
)

# E8. Embedding width, overridable so the capacity ablation is one command:
#     $env:GAIL_HIDDEN_CHANNELS=128; python scripts/train_prod_model.py
#
# The default stays 16 deliberately. E8 was specified as "raise hidden dim to
# 128" on the assumption the model was under-capacity. The 2026-10-23 run shows
# the opposite: with 16 labelled nodes it already fits in-sample to MSE 0.0068
# (99.7% below the always-zero baseline) and the prediction barely moves when
# exposure is zeroed -- mean |mu(e,X) - mu(0,X)| = 0.027 on targets spanning
# +/-4. The head is reading each creator's target off a 1,289-dimensional
# embedding that uniquely identifies them, so it has no need of exposure at all.
# Eight times the width makes that worse, not better. The knob exists because
# the ablation belongs in the write-up; the default should not change until
# cross-fitting shows the model generalising at all.
HIDDEN_CHANNELS = int(os.environ.get("GAIL_HIDDEN_CHANNELS", "16"))
HEADS = 2
EPOCHS = 100
# P3. Control observations on by default; GAIL_CONTROLS=0 is the treated-only
# ablation (the P2 run: 15 exposed observations, no T = 0 data).
USE_CONTROLS = os.environ.get("GAIL_CONTROLS", "1") != "0"
# P3b. Which lift is the target. "log" = log((median_after+1)/(median_before+1)),
# chosen for scale, before seeing any estimate on it. GAIL_LIFT=median restores
# the ratio-minus-one lift of every earlier run.
LIFT_STATISTIC = os.environ.get("GAIL_LIFT", "log")
LIFT_KEY = {"log": "log_lift", "median": "robust_lift"}[LIFT_STATISTIC]
LR = 1e-2
SEED = 0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def category_one_hot(category: str | None) -> list[int]:
    vec = [0] * len(CREATOR_CATEGORIES)
    if category in CREATOR_CATEGORIES:
        vec[CREATOR_CATEGORIES.index(category)] = 1
    return vec




def build_targets_from_canonical(cur, creator_id_to_index: dict[str, int], num_creators: int):
    """Build per-creator target from canonical pair_count rows + per-platform lifts.

    Steps:
      1. compute() gives canonical (event, neighbour) rows where straddle holds
         across ALL platforms pooled (cross-platform straddle counts).
      2. For each canonical row, check each platform for a SAME-platform
         before/after with BOTH engagement cols present — only those give a
         lift (after_avg - before_avg)/(before_avg+1).
      3. A neighbour appearing in multiple events/platforms gets mean(lifts).
      4. Cross-platform-only straddle rows (no same-platform lift) are counted
         separately, not silently averaged across incompatible units.
    """
    summary = pair_count_compute(cur)
    good_rows = [r for r in summary["_rows"] if r[5] > 0 and r[6] > 0]
    print(f"Canonical computable pairs (pair_count.py): {len(good_rows)}")
    print(f"  checks_evaluated={summary['checks_evaluated']} events_total={summary['events_total']} "
          f"directed={summary['distinct_directed_creator_pairs']} undirected={summary['distinct_undirected_creator_pairs']} "
          f"events_yielding={summary['distinct_events_yielding_pairs']} collab_edge_pairs={summary['collab_edge_pairs']}")

    lifts_by_neighbour: dict[str, list[float]] = {}
    same_platform_rows = 0
    cross_platform_only = 0
    detailed: list[dict] = []

    for row in good_rows:
        event_creator_id, item_id, event_platform, event_date, neighbour_id, _, _ = row
        platform_lifts: dict[str, dict] = {}
        for platform in PLATFORM_TABLES:
            before, after = platform_engagement(cur, neighbour_id, platform, event_date, DEFAULT_WINDOW_DAYS)
            if before and after:
                # Shared with compute_training_pair_deltas.py via
                # ml/engagement_lift.py. Previously each script carried its own
                # copy of this formula, so a fix to one left the model training
                # on the other.
                platform_lifts[platform] = platform_lift(before, after)
        if platform_lifts:
            same_platform_rows += 1
            mean_lift = row_target(platform_lifts, statistic="mean")
            robust_lift = row_target(platform_lifts, statistic="median")
            log_lift = row_target(platform_lifts, statistic="log")
            lifts_by_neighbour.setdefault(neighbour_id, []).append(robust_lift)
            detailed.append({
                "event_creator_id": event_creator_id,
                "item_id": item_id,
                "event_platform": event_platform,
                "event_date": str(event_date),
                "neighbour_id": neighbour_id,
                "platform_lifts": platform_lifts,
                "mean_lift": mean_lift,
                "robust_lift": robust_lift,
                "log_lift": log_lift,
            })
        else:
            cross_platform_only += 1
            detailed.append({
                "event_creator_id": event_creator_id,
                "item_id": item_id,
                "event_platform": event_platform,
                "event_date": str(event_date),
                "neighbour_id": neighbour_id,
                "platform_lifts": {},
                "mean_lift": None,
                "robust_lift": None,
                "log_lift": None,
            })

    # E2: cluster rows that measure the SAME engagement change before averaging.
    # Previously `target[creator] = mean(all that creator's lifts)`, which let one
    # engagement change recorded N times dominate that creator's own target, and
    # gave a creator backed by one repeated measurement the same training weight
    # as one backed by several independent events.
    #
    # `per_creator_targets` averages within a cluster (one observation measured
    # repeatedly), then across clusters (genuinely separate observations), and
    # returns how many clusters back each target. That count becomes the node's
    # sample weight in the loss.
    target = torch.zeros(num_creators, dtype=torch.float32)
    sample_weight = torch.zeros(num_creators, dtype=torch.float32)
    # `robust_lift` is the median-based target (ml/engagement_lift.py). The
    # mean-based one is kept in `detailed` for the checkpoint record, but the
    # model trains on the median: on the 2026-10-19 data the mean-based target
    # had stdev 6.893 and a max of +34.724, both produced by single viral posts.
    lift_rows = [d for d in detailed if d["robust_lift"] is not None]
    clustered = per_creator_targets(
        lift_rows, window_days=DEFAULT_WINDOW_DAYS, value_key="robust_lift"
    )
    for nid, (value, n_clusters) in clustered.items():
        if nid in creator_id_to_index:
            idx = creator_id_to_index[nid]
            target[idx] = value
            sample_weight[idx] = float(n_clusters)

    cluster_stats = summarize(cluster_events(lift_rows, window_days=DEFAULT_WINDOW_DAYS))
    print(f"E2 clustering (window {DEFAULT_WINDOW_DAYS}d): {cluster_stats['rows']} rows -> "
          f"{cluster_stats['clusters']} independent observations across "
          f"{len(clustered)} creators")
    if cluster_stats["largest"]:
        cid, n = cluster_stats["largest"][0]
        print(f"  largest cluster {n} rows ({cluster_stats['max_cluster_share']:.0%}) -- {cid}")
        if cluster_stats["max_cluster_share"] > 0.3:
            print("  !! one engagement change dominates; quote the cluster count, not the row count")

    n_labeled = len(clustered)
    print(f"Same-platform-computable lifts: {same_platform_rows}/{len(good_rows)} "
          f"(cross-platform-only straddle, no lift: {cross_platform_only}/{len(good_rows)})")
    if n_labeled:
        vals = [statistics.mean(v) for v in lifts_by_neighbour.values()]
        vals_sorted = sorted(vals)
        print(f"Lift distribution (mean lift per neighbour, N={n_labeled}): "
              f"min={vals_sorted[0]:.4f} median={statistics.median(vals_sorted):.4f} "
              f"mean={statistics.mean(vals_sorted):.4f} max={vals_sorted[-1]:.4f}")

    return target, lifts_by_neighbour, summary, detailed, sample_weight


def _reconnect(conn, database_url: str):
    """Replace a connection that may have gone stale. Returns (conn, cur).

    Closing the old one is best-effort: if the pooler already dropped it, the
    close itself raises, and that is exactly the case this exists to survive.
    """
    try:
        conn.close()
    except Exception:
        pass
    fresh = psycopg2.connect(database_url)
    return fresh, fresh.cursor()


def build_creator_features(cur, extractor: FeatureExtractor):
    """Build creator features via DB + CLIP/BERT (mirrors feature_store logic but via psycopg2).

    Raw text = scrubbed join of: youtube channel description + instagram bio +
               up to 20 youtube title/description + up to 20 instagram captions.
    Thumbnails = up to 20 youtube thumbnail_url + up to 20 instagram thumbnail_url (if any).
    Metadata: log_subscriber_count (max of yt subs / ig followers), engagement_rate,
              reputation_score always None (no source), category_one_hot.
    """
    # Fetch creators
    cur.execute("select creator_id::text, name, category, youtube_handle, instagram_handle, reddit_handles from creators order by name")
    creator_rows = cur.fetchall()
    if not creator_rows:
        raise RuntimeError("No creators found")

    # Pre-fetch youtube channels / instagram profiles for all creators
    cur.execute("select creator_id::text, subscriber_count, description, title from youtube_channels")
    yt_by_creator = {r[0]: r for r in cur.fetchall()}
    cur.execute("select creator_id::text, follower_count, bio, full_name from instagram_profiles")
    ig_by_creator = {r[0]: r for r in cur.fetchall()}

    # E14. Pre-fetch per-creator content BEFORE the extraction loop.
    #
    # These two queries used to run inside the loop, once per creator, which
    # meant the database connection had to survive the whole CLIP/BERT pass --
    # over half an hour for 390 creators, mostly idle between queries. Supabase's
    # pooler closes idle connections, and the run died at creator 53/390 with
    # "server closed the connection unexpectedly", losing eight minutes of
    # extraction. Fetching up front means the connection is finished with before
    # the slow work starts.
    #
    # ORDER BY is deliberate. The per-creator queries used `limit 20` with no
    # ordering, so which twenty rows arrived was up to Postgres and could differ
    # between runs -- the module docstring claims determinism, and for feature
    # extraction that was not true. Ordering by date takes the twenty most
    # recent, which is both reproducible and the more defensible definition:
    # a creator's current content describes them better than whichever rows the
    # planner happened to return first.
    def _grouped(sql: str, per_creator: int = 20) -> dict[str, list]:
        cur.execute(sql)
        out: dict[str, list] = {}
        for row in cur.fetchall():
            bucket = out.setdefault(row[0], [])
            if len(bucket) < per_creator:
                bucket.append(row[1:])
        return out

    yt_videos_by_creator = _grouped(
        "select creator_id::text, title, description, thumbnail_url, view_count, "
        "like_count, comment_count from youtube_videos "
        "order by creator_id, published_at desc nulls last"
    )
    ig_posts_by_creator = _grouped(
        "select creator_id::text, caption, thumbnail_url, like_count, comment_count "
        "from instagram_posts order by creator_id, posted_at desc nulls last"
    )
    print(f"Pre-fetched content for {len(yt_videos_by_creator)} creators with YouTube videos, "
          f"{len(ig_posts_by_creator)} with Instagram posts (connection no longer needed)")

    # Engagement helper needs videos/posts per creator for rate
    # We'll compute engagement_rate lazily per creator inside loop

    # E14. Feature cache, keyed by a hash of the exact inputs CLIP and BERT see.
    #
    # Extraction is the slow part of this script -- around half an hour for 390
    # creators -- and nothing about it changes between runs unless the creator's
    # content changes. Hashing the record rather than the creator id means the
    # cache invalidates itself when Track A scrapes new posts for someone: their
    # text and thumbnails change, so does the hash, and that creator alone is
    # recomputed. A corrupt or unreadable cache is ignored rather than fatal.
    cache_path = Path(__file__).resolve().parents[1] / "models" / "feature_cache.pt"
    try:
        feature_cache: dict[str, torch.Tensor] = torch.load(cache_path, weights_only=True)
        print(f"Feature cache: {len(feature_cache)} entries from {cache_path.name}")
    except Exception:
        feature_cache = {}
        print("Feature cache: starting empty")
    cache_hits = 0

    vecs = []
    id_to_index: dict[str, int] = {}
    order: list[str] = []
    id_to_name: dict[str, str] = {}
    id_to_category: dict[str, str] = {}

    # For raw_text we need scrub_text — import from track-c if available, else simple fallback
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "track-c-fusion-backend"))
        from backend.app.text_processing import scrub_text  # type: ignore
    except Exception:
        def scrub_text(t: str) -> str:  # fallback: lower + strip
            import re
            return re.sub(r"\s+", " ", (t or "").strip())

    for idx, (cid, name, category, yt_handle, ig_handle, reddit_handles) in enumerate(creator_rows):
        # limit per-creator content fetch to 20 each (matches feature_store)
        yt_videos = yt_videos_by_creator.get(cid, [])
        ig_posts = ig_posts_by_creator.get(cid, [])

        yt_row = yt_by_creator.get(cid)
        ig_row = ig_by_creator.get(cid)

        # log_subscriber_count = log1p(max(yt subs, ig followers))
        yt_subs = 0
        if yt_row and yt_row[1]:
            try:
                yt_subs = int(yt_row[1])
            except Exception:
                yt_subs = 0
        ig_followers = 0
        if ig_row and ig_row[1]:
            try:
                ig_followers = int(ig_row[1])
            except Exception:
                ig_followers = 0
        reach = max(yt_subs, ig_followers)
        log_subscriber_count = math.log1p(reach) if reach else None

        # engagement_rate = (likes+comments)/reach pooled (same as feature_store)
        total_eng = 0
        total_reach = 0
        for _title, _desc, _thumb, v_views, v_likes, v_comments in yt_videos:
            if v_views:
                try:
                    vv = int(v_views)
                except Exception:
                    vv = 0
                if vv:
                    total_eng += (int(v_likes or 0) + int(v_comments or 0))
                    total_reach += vv
        if ig_row and ig_row[1]:
            try:
                ig_f = int(ig_row[1])
            except Exception:
                ig_f = 0
            if ig_f:
                for _cap, _thumb, p_likes, p_comments in ig_posts:
                    total_eng += (int(p_likes or 0) + int(p_comments or 0))
                    total_reach += ig_f
        engagement_rate = (total_eng / total_reach) if total_reach else None

        # raw_text
        parts: list[str] = []
        if yt_row and yt_row[2]:
            parts.append(yt_row[2])
        if ig_row and ig_row[2]:
            parts.append(ig_row[2])
        for title, desc, *_ in yt_videos:
            if title:
                parts.append(title)
            if desc:
                parts.append(desc)
        for cap, *_ in ig_posts:
            if cap:
                parts.append(cap)
        raw_text = scrub_text(" ".join(parts))

        # thumbnails
        thumbs: list[str] = []
        for _t, _d, thumb, *_ in yt_videos:
            if thumb:
                thumbs.append(thumb)
        for _c, thumb, *_ in ig_posts:
            if thumb:
                thumbs.append(thumb)

        record = RawCreatorRecord(
            category_one_hot=category_one_hot(category),
            log_subscriber_count=log_subscriber_count,
            engagement_rate=engagement_rate,
            reputation_score=None,
            raw_text=raw_text,
            thumbnail_urls=thumbs[:20],
        )
        cache_key = hashlib.sha256(
            repr((
                record.category_one_hot,
                record.log_subscriber_count,
                record.engagement_rate,
                record.reputation_score,
                record.raw_text,
                record.thumbnail_urls,
            )).encode("utf-8")
        ).hexdigest()

        cached = feature_cache.get(cache_key)
        if cached is not None and cached.shape[0] == CREATOR_FEATURE_DIM:
            cache_hits += 1
            vec = cached
        else:
            print(f"  [{idx+1}/{len(creator_rows)}] extracting features for {name!r} "
                  f"(yt_subs={yt_subs} ig_followers={ig_followers} thumbs={len(thumbs)})...")
            vec = extractor.extract(record)
            feature_cache[cache_key] = vec
        assert vec.shape[0] == CREATOR_FEATURE_DIM, f"dim mismatch {vec.shape[0]} != {CREATOR_FEATURE_DIM}"
        vecs.append(vec)
        id_to_index[cid] = idx
        order.append(cid)
        id_to_name[cid] = name
        id_to_category[cid] = category or "other"

    print(f"Features: {cache_hits}/{len(creator_rows)} from cache, "
          f"{len(creator_rows) - cache_hits} extracted")
    if cache_hits < len(creator_rows):
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(feature_cache, cache_path)
        except Exception as exc:  # a cache that cannot be written is not fatal
            print(f"  (could not write feature cache: {exc})")

    x = torch.stack(vecs)
    return x, id_to_index, order, id_to_name, id_to_category


def load_collab_edges(cur, id_to_index: dict[str, int]):
    """Both directions, weight = count per unordered pair (deduped)."""
    # Resolve handles like feature_store does (case-insensitive, prefix stripped)
    cur.execute("select creator_id::text, youtube_handle, instagram_handle, reddit_handles from creators")
    raw_owners = {"youtube": {}, "instagram": {}, "reddit": {}}
    # Use defaultdict sets to detect ambiguous handles
    from collections import defaultdict
    owners = {"youtube": defaultdict(set), "instagram": defaultdict(set), "reddit": defaultdict(set)}

    def norm(h: str) -> str:
        if not h:
            return ""
        h = h.strip().lower()
        for p in ("@", "u/", "r/"):
            if h.startswith(p):
                h = h[len(p):]
        return h

    for cid, yt, ig, rh in cur.fetchall():
        if yt:
            owners["youtube"][norm(yt)].add(cid)
        if ig:
            owners["instagram"][norm(ig)].add(cid)
        for h in rh or []:
            owners["reddit"][norm(h)].add(cid)
    handle_map = {p: {h: next(iter(s)) for h, s in d.items() if len(s) == 1} for p, d in owners.items()}

    cur.execute("select creator_id::text, platform, handle from creator_related_accounts where relation_type='frequent_collaborator'")
    pair_weights: dict[tuple[str, str], int] = defaultdict(int)
    for cid, platform, handle in cur.fetchall():
        if not handle:
            continue
        target = handle_map.get(platform, {}).get(norm(handle))
        if target and target != cid:
            pair = tuple(sorted((str(cid), str(target))))
            pair_weights[pair] += 1

    src, dst, w = [], [], []
    for (a, b), weight in pair_weights.items():
        if a in id_to_index and b in id_to_index:
            ia, ib = id_to_index[a], id_to_index[b]
            src.extend([ia, ib])
            dst.extend([ib, ia])
            w.extend([float(weight), float(weight)])
    if not src:
        return torch.empty((2, 0), dtype=torch.long), torch.empty((0, 1), dtype=torch.float32)
    edge_index = torch.tensor([src, dst], dtype=torch.long)
    edge_attr = torch.tensor(w, dtype=torch.float32).unsqueeze(-1)
    return edge_index, edge_attr


def load_cooccurrence_edges(cur, id_to_index: dict[str, int]):
    from collections import defaultdict
    import itertools
    cur.execute("select post_id::text, creator_id::text from reddit_post_creators")
    creators_by_post: dict[str, set[str]] = defaultdict(set)
    for post_id, cid in cur.fetchall():
        creators_by_post[post_id].add(cid)
    pair_weights: dict[tuple[str, str], int] = defaultdict(int)
    for cids in creators_by_post.values():
        if len(cids) < 2:
            continue
        for a, b in itertools.combinations(sorted(cids), 2):
            pair_weights[(a, b)] += 1
    src, dst, w = [], [], []
    for (a, b), weight in pair_weights.items():
        if a in id_to_index and b in id_to_index:
            ia, ib = id_to_index[a], id_to_index[b]
            src.extend([ia, ib])
            dst.extend([ib, ia])
            w.extend([float(weight), float(weight)])
    if not src:
        return torch.empty((2, 0), dtype=torch.long), torch.empty((0, 1), dtype=torch.float32)
    return torch.tensor([src, dst], dtype=torch.long), torch.tensor(w, dtype=torch.float32).unsqueeze(-1)


def load_brands(cur):
    cur.execute("select brand_id::text, name, category, follower_count, post_count, is_verified, youtube_handle, instagram_handle, reddit_handle from brands")
    rows = cur.fetchall()
    vecs = []
    id_to_index: dict[str, int] = {}
    for i, (bid, name, category, follower_count, post_count, is_verified, yt, ig, rd) in enumerate(rows):
        num_platforms = sum(1 for h in (yt, ig, rd) if h)
        metadata = [
            math.log1p(follower_count) if follower_count else 0.0,
            math.log1p(post_count) if post_count else 0.0,
            float(bool(is_verified)),
            float(num_platforms),
        ]
        metadata += [0.0] * NUM_BRAND_CATEGORIES
        assert len(metadata) == BRAND_METADATA_DIM
        vecs.append(torch.tensor(metadata, dtype=torch.float32))
        id_to_index[bid] = i
    if not vecs:
        return torch.empty((0, BRAND_METADATA_DIM), dtype=torch.float32), id_to_index
    return torch.stack(vecs), id_to_index


def load_sponsorship_dates(cur) -> dict:
    """Dated sponsorship events per creator, for time-indexed treatment (P2).

    Uses the SAME event definition as Track A's pair_count (Clause 1): on
    Instagram, `is_sponsored OR has_paid_partnership_label`. The previous
    `load_treatment` read `creator_sponsorship_events`, which uses
    `is_sponsored` only, so a creator sponsored only via Instagram's native
    label could generate training pairs while having T = 0. One definition now
    drives both. P0 found the label-carrying events 33/33 genuine.
    """
    cur.execute(
        """
        select creator_id::text, posted_at from instagram_posts
         where (is_sponsored or has_paid_partnership_label)
           and posted_at is not null and creator_id is not null
        union all
        select creator_id::text, published_at from youtube_videos
         where is_sponsored and published_at is not null and creator_id is not null
        union all
        select creator_id::text, posted_at from reddit_posts
         where is_sponsored and posted_at is not null and creator_id is not null
        """
    )
    return sponsorship_dates(cur.fetchall())


def main() -> int:
    # Windows cp1252 stdout crashes on creator names outside its charset (see
    # scripts/train_holdout_round3.py). Match that handling here.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("=== Track B prod training (ALL pairs, normalized propensity) ===")
    database_url = ENV.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not set (check .env)")
        return 1

    # Optional JSON inputs (if caller prefers pre-dumped feature-store files)
    # When provided, we still query DB for pair_count/targets to ensure freshness,
    # but creator features/edges come from those files.
    use_json = len(sys.argv) == 5

    print("Loading CLIP + BERT (real pretrained models)...")
    extractor = FeatureExtractor(max_thumbnails=5)

    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    # Pair-count freshness check happens inside build_targets_from_canonical via the same cur
    # Build creator features & graph structure
    if use_json:
        # --- JSON path (not recommended for prod, but supported) ---
        import json as _json
        creators_path, collab_path, cooccur_path, sponsorship_path = sys.argv[1:5]
        # Load creator features from JSON via extractor
        with open(creators_path, encoding="utf-8") as f:
            records = _json.load(f)
        vecs, id_to_index, order, id_to_name = [], {}, [], {}
        for i, r in enumerate(records):
            rec = RawCreatorRecord(
                category_one_hot=r["category_one_hot"],
                log_subscriber_count=r["log_subscriber_count"],
                engagement_rate=r["engagement_rate"],
                reputation_score=r["reputation_score"],
                raw_text=r["raw_text"],
                thumbnail_urls=r["thumbnail_urls"],
            )
            print(f"  [{i+1}/{len(records)}] extracting features for {r['name']!r}...")
            vecs.append(extractor.extract(rec))
            id_to_index[r["creator_id"]] = i
            order.append(r["creator_id"])
            id_to_name[r["creator_id"]] = r["name"]
        creator_x = torch.stack(vecs)
        num_creators = creator_x.size(0)
        # edges from JSON
        with open(collab_path, encoding="utf-8") as f:
            collab_rows = _json.load(f)
        with open(cooccur_path, encoding="utf-8") as f:
            cooccur_rows = _json.load(f)
        def _edges_from_rows(rows):
            if not rows:
                return torch.empty((2,0), dtype=torch.long), torch.empty((0,1), dtype=torch.float32)
            src = torch.tensor([id_to_index[r["source_creator_id"]] for r in rows if r["source_creator_id"] in id_to_index and r["target_creator_id"] in id_to_index])
            # proper handling: build lists to avoid missing
            s, d, w = [], [], []
            for r in rows:
                a, b = r["source_creator_id"], r["target_creator_id"]
                if a in id_to_index and b in id_to_index:
                    s.append(id_to_index[a]); d.append(id_to_index[b]); w.append(float(r["weight"]))
            if not s:
                return torch.empty((2,0), dtype=torch.long), torch.empty((0,1), dtype=torch.float32)
            return torch.tensor([s,d], dtype=torch.long), torch.tensor(w, dtype=torch.float32).unsqueeze(-1)
        collab_index, collab_attr = _edges_from_rows(collab_rows)
        cooccur_index, cooccur_attr = _edges_from_rows(cooccur_rows)
        # Same stale-connection exposure as the DB path below: this branch also
        # runs CLIP/BERT over every creator before querying again.
        conn, cur = _reconnect(conn, database_url)
        brand_x, brand_id_to_index = load_brands(cur)
        # sponsorship edges not needed for training except maybe reporting — build empty
        sponsors_index = torch.empty((2,0), dtype=torch.long)
        sponsored_by_index = torch.empty((2,0), dtype=torch.long)
    else:
        creator_x, id_to_index, order, id_to_name, _ = build_creator_features(cur, extractor)
        num_creators = creator_x.size(0)
        print(f"Creator features: {num_creators} creators, dim {creator_x.shape[1]}")

        # E14b. Reconnect before the remaining queries.
        #
        # Feature extraction can take half an hour on a cold cache, during which
        # this connection is idle. Supabase's pooler closes idle connections, so
        # the next query fails with "server closed the connection unexpectedly"
        # -- which is how two runs died, once at creator 53/390 and once at
        # load_collab_edges with all 390 already extracted. Everything from here
        # on is fast, so a single reconnect is enough; nothing needs to span the
        # slow part.
        conn, cur = _reconnect(conn, database_url)

        collab_index, collab_attr = load_collab_edges(cur, id_to_index)
        cooccur_index, cooccur_attr = load_cooccurrence_edges(cur, id_to_index)
        brand_x, brand_id_to_index = load_brands(cur)
        print(f"Edges: collab {collab_index.size(1)} directed ({collab_index.size(1)//2} undirected), "
              f"co_occurs {cooccur_index.size(1)} directed")

    # Build HeteroData
    data = empty_hetero_data()
    data["creator"].x = creator_x
    data["brand"].x = brand_x
    data["creator", "collaborates_with", "creator"].edge_index = collab_index
    data["creator", "collaborates_with", "creator"].edge_attr = collab_attr
    data["creator", "co_occurs_with", "creator"].edge_index = cooccur_index
    data["creator", "co_occurs_with", "creator"].edge_attr = cooccur_attr
    data["brand", "sponsors", "creator"].edge_index = torch.empty((2,0), dtype=torch.long)
    data["creator", "sponsored_by", "brand"].edge_index = torch.empty((2,0), dtype=torch.long)
    # Populate sponsors/sponsored_by for completeness (from sponsorship view)
    try:
        cur.execute("select brand_id::text, creator_id::text from creator_sponsorship_events where brand_id is not null")
        rows = cur.fetchall()
        b_idx, c_idx = [], []
        for bid, cid in rows:
            if bid in brand_id_to_index and cid in id_to_index:
                b_idx.append(brand_id_to_index[bid]); c_idx.append(id_to_index[cid])
        if b_idx:
            data["brand", "sponsors", "creator"].edge_index = torch.tensor([b_idx, c_idx], dtype=torch.long)
            data["creator", "sponsored_by", "brand"].edge_index = torch.tensor([c_idx, b_idx], dtype=torch.long)
    except Exception as e:
        print(f"Warning: sponsorship edges build failed: {e}")

    # P2. Dated sponsorship events, one definition shared with pair_count.
    spons_dates = load_sponsorship_dates(cur)
    ever = [c for c in spons_dates if c in id_to_index]
    print(f"Sponsorship events: {sum(len(v) for v in spons_dates.values())} dated; "
          f"{len(ever)}/{num_creators} creators sponsored at some point")

    # Targets from canonical pair_count + platform_engagement (both-engagement-cols fix).
    # The per-creator target it returns is superseded by observations below.
    _, lifts_by_neighbour, pair_summary, detailed, _ = build_targets_from_canonical(
        cur, id_to_index, num_creators
    )

    # P2b. Drop rows where the NEIGHBOUR ran their own sponsorship inside the
    # window: their lift mixes their own direct effect into the "spillover".
    lift_rows = [d for d in detailed if d["robust_lift"] is not None]
    kept_rows, self_sponsored = drop_self_sponsored(lift_rows, spons_dates, DEFAULT_WINDOW_DAYS)
    for d in self_sponsored:
        d["excluded"] = "neighbour_own_sponsorship_in_window"
    print(f"\nP2b: dropped {len(self_sponsored)}/{len(lift_rows)} lift rows -- the neighbour "
          f"ran their own sponsorship within +/-{DEFAULT_WINDOW_DAYS}d of the event")
    for d in self_sponsored:
        print(f"  dropped  {id_to_name.get(d['neighbour_id'], d['neighbour_id'])[:28]:28s} "
              f"event {str(d['event_date'])[:10]} by "
              f"{id_to_name.get(d['event_creator_id'], d['event_creator_id'])[:28]}")

    # P2. One observation per cluster (same clustering rule as E2), each
    # carrying the span of dates it measures.
    observations = [
        o for o in build_observations(kept_rows, DEFAULT_WINDOW_DAYS, LIFT_KEY)
        if o.neighbour_id in id_to_index
    ]
    n_obs = len(observations)
    labeled_ids = sorted({o.neighbour_id for o in observations})
    labeled_idx = [id_to_index[c] for c in labeled_ids]
    print(f"\nObservations: {n_obs} independent, across {len(labeled_ids)} creators")
    for o in observations:
        print(f"  {id_to_name.get(o.neighbour_id, o.neighbour_id)[:28]:28s} "
              f"{o.start}..{o.end}  rows={o.n_rows:<2} lift={o.value:+.4f}")

    if not observations:
        print("ERROR: no observations left -- cannot train")
        conn.close()
        return 1

    # Per-creator target, kept only for the checkpoint record and inference
    # display. Training no longer uses it: it supervises observations.
    target = torch.zeros(num_creators, dtype=torch.float32)
    for cid in labeled_ids:
        vals = [o.value for o in observations if o.neighbour_id == cid]
        target[id_to_index[cid]] = sum(vals) / len(vals)

    # Feature normalization — per-dim z-score, saved for inference
    mean, std = compute_feature_scaler(creator_x)
    # Apply normalization BEFORE training (so propensity head sees normalized features)
    x_norm = (creator_x - mean) / std
    data["creator"].x = x_norm
    print(f"Feature scaler: mean abs {mean.abs().mean():.4f}, std mean {std.mean():.4f} "
          f"(propensity head will receive normalized features — fixes saturation)")

    from ml.causal_regularization import doubly_robust_effect, has_sponsored_neighbor
    from ml.gail_loss import GAILLossWeights, compute_gail_loss

    torch.manual_seed(SEED)
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM, hidden_channels=HIDDEN_CHANNELS, heads=HEADS)

    num_creators_t = data["creator"].x.size(0)
    collab_edge_index = data["creator", "collaborates_with", "creator"].edge_index
    collab_edge_weight = data["creator", "collaborates_with", "creator"].edge_attr

    # E12a. The consistency penalty must see every relation exposure travels
    # through (collaborates_with AND co_occurs_with), or the loss penalises
    # exposure the model was built to give.
    interference_edge_index = torch.cat(
        [collab_edge_index, data["creator", "co_occurs_with", "creator"].edge_index],
        dim=1,
    )

    # P2. One treatment vector per distinct observation span. E12b still holds
    # within each: own sponsorship PROPAGATES through the exposure module, and
    # the loss uses the interference indicator ("has a sponsored neighbour")
    # derived from it -- now for that window only.
    passes = []
    for (start, end), group in sorted(group_by_span(observations).items()):
        t_p = treatment_in_span(spons_dates, id_to_index, num_creators_t, start, end)
        has_p = has_sponsored_neighbor(interference_edge_index, t_p)
        mask_p = torch.zeros(num_creators_t, dtype=torch.bool)
        target_p = torch.zeros(num_creators_t, dtype=torch.float32)
        for o in group:
            idx = id_to_index[o.neighbour_id]
            mask_p[idx] = True
            target_p[idx] = o.value
        passes.append({
            "span": (start, end), "obs": group, "treatment": t_p,
            "has_sponsored": has_p, "interference": has_p.to(torch.float32),
            "mask": mask_p, "target": target_p,
        })
    n_spons = [int(p["treatment"].sum().item()) for p in passes]
    print(f"\nP2: {len(passes)} treatment windows; sponsored creators per window "
          f"min={min(n_spons)} median={statistics.median(n_spons)} max={max(n_spons)} "
          f"(all-time: {len(ever)})")

    # Each observation exists because a collaborator was sponsored inside its
    # window, so it should be exposed. If not, the graph lacks the edge
    # pair_count used, and the lift is being read as an UNEXPOSED outcome.
    not_exposed = [
        o for p in passes for o in p["obs"]
        if not bool(p["has_sponsored"][id_to_index[o.neighbour_id]])
    ]
    if not_exposed:
        print(f"  !! {len(not_exposed)}/{n_obs} observations have NO sponsored neighbour "
              f"in their own window in the graph:")
        for o in not_exposed:
            print(f"     {id_to_name.get(o.neighbour_id, o.neighbour_id)[:28]:28s} {o.start}..{o.end}")
        print("     pair_count's edge (handle match) is missing from the graph's edges")

    # P3. Control observations: creators with NO sponsored neighbour and NO own
    # sponsorship in a window, measured around the SAME event dates with the
    # same lift. They join that window's pass, so they share its treatment
    # vector and enter the loss with interference = 0 -- the first T = 0 data
    # the model has seen. GAIL_CONTROLS=0 recovers the P2 (treated-only) run.
    treated_obs = list(observations)
    controls = []
    if USE_CONTROLS:
        posts_by_platform = {pl: load_platform_posts(cur, pl) for pl in PLATFORM_TABLES}
        index_to_id = {v: k for k, v in id_to_index.items()}
        reserved: dict[str, list] = {}
        for o in treated_obs:
            reserved.setdefault(o.neighbour_id, []).append(o.span)
        windows = []
        for p in passes:
            eligible = [
                index_to_id[j] for j in range(num_creators_t)
                if j in index_to_id and not bool(p["has_sponsored"][j]) and not bool(p["treatment"][j])
            ]
            dates = sorted({d for o in p["obs"] for d in o.event_dates})
            windows.append((p["span"], dates, eligible))
        controls = build_control_observations(
            windows,
            lambda cid, d: lift_from_posts(
                posts_by_platform, cid, d, DEFAULT_WINDOW_DAYS, statistic=LIFT_STATISTIC
            ),
            reserved_spans=reserved,
        )
        pass_by_span = {p["span"]: p for p in passes}
        for c in controls:
            p = pass_by_span[c.span]
            idx = id_to_index[c.neighbour_id]
            assert not p["mask"][idx], "a creator appears twice in one window"
            p["mask"][idx] = True
            p["target"][idx] = c.value
            p["obs"].append(c)
    observations = treated_obs + controls
    n_obs = len(observations)

    print(f"\nTarget: {LIFT_KEY} (GAIL_LIFT={LIFT_STATISTIC})")
    print(f"P3: {len(treated_obs)} exposed + {len(controls)} control observations "
          f"(controls {'ON' if USE_CONTROLS else 'OFF -- GAIL_CONTROLS=0'})")
    for p in passes:
        n_t = sum(o.exposed for o in p["obs"])
        print(f"  {p['span'][0]}..{p['span'][1]}  exposed={n_t:<2} control={len(p['obs']) - n_t}")
    if controls:
        cv = sorted(c.value for c in controls)
        print(f"  control lift: min={cv[0]:+.3f} median={statistics.median(cv):+.3f} "
              f"max={cv[-1]:+.3f}  (exposed median "
              f"{statistics.median(o.value for o in treated_obs):+.3f})")

    # Model-free check, computed before any training: within each window,
    # exposed lift minus control lift. If the GNN's estimate and this disagree
    # wildly, believe this one first.
    did = matched_did(observations)
    print(f"\nMatched DiD (no model): {did['estimate']:+.4f}  SE {did['se']:.4f}  "
          f"[{did['estimate'] - 1.96 * did['se']:+.4f}, {did['estimate'] + 1.96 * did['se']:+.4f}]  "
          f"over {did['n_treated']} exposed vs {did['n_control']} controls in {did['windows']} windows")
    print(f"  median version (robust to single extreme creators): {did['median_estimate']:+.4f}")
    if did["treated_without_control"]:
        print(f"  {did['treated_without_control']} exposed observations had no control in their window "
              f"and are left out of this estimate")

    # E10. Bot scores, reported not enforced (see load_bot_scores).
    bot_scores = load_bot_scores(cur, id_to_index)
    flagged = {cid for cid, v in bot_scores.items() if v["is_bot_flagged"]}
    print(f"Bot detection: {len(flagged)}/{len(bot_scores)} creators flagged "
          f"(threshold 0.6, heuristic, nothing excluded)")
    flagged_labeled = [id_to_name.get(c, c) for c in labeled_ids if c in flagged]
    if flagged_labeled:
        print(f"  !! flagged creators among the {len(labeled_ids)} LABELLED nodes: "
              f"{', '.join(flagged_labeled)}")
        print("     their measured lift carries the same weight as everyone else's; "
              "decide deliberately whether to keep them")

    # Treatment for inference/ranking: who is sponsored NOW, i.e. in the last
    # window up to the latest event in the data -- the same kind of quantity
    # the model was trained on, rather than an all-time flag.
    latest = max(d for v in spons_dates.values() for d in v)
    treatment = treatment_in_span(
        spons_dates, id_to_index, num_creators_t,
        latest - timedelta(days=DEFAULT_WINDOW_DAYS), latest,
    )
    print(f"Inference treatment: {int(treatment.sum().item())} creators sponsored in the "
          f"{DEFAULT_WINDOW_DAYS}d up to {latest}")

    loss_weights = GAILLossWeights()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    treatments = [p["treatment"] for p in passes]
    history = []
    for epoch in range(EPOCHS):
        model.train()
        optimizer.zero_grad()
        preds, _, propensity = model.forward_multi(data, treatments)
        # E12c: AIPW pseudo-outcome. P2: one loss per window, weighted by its
        # share of observations, so every observation counts equally and the
        # graph-wide regularisers keep their single-pass scale.
        loss = torch.zeros(())
        comps: dict[str, float] = {}
        for p, pred in zip(passes, preds):
            share = len(p["obs"]) / n_obs
            loss_p, comps_p = compute_gail_loss(
                pred, p["target"], propensity, collab_edge_index, collab_edge_weight,
                p["has_sponsored"], loss_weights, prediction_mask=p["mask"],
                treatment=p["interference"], dr_mode="aipw",
            )
            loss = loss + share * loss_p
            for k, v in comps_p.items():
                comps[k] = comps.get(k, 0.0) + share * v
        loss.backward()
        optimizer.step()
        history.append(comps)
        if (epoch + 1) % 20 == 0 or epoch == 0:
            print(f"  epoch {epoch+1}/{EPOCHS}: total={comps['total']:.4f} pred={comps['prediction']:.4f} "
                  f"overlap={comps['overlap']:.4f} prop_mean={propensity.mean().item():.3f} "
                  f"prop_min={propensity.min().item():.3f} max={propensity.max().item():.3f}")

    # Final evaluation, per observation, each against its own window's treatment.
    model.eval()
    with torch.no_grad():
        preds, exposures, final_prop = model.forward_multi(data, treatments)
        # E12d. The counterfactual: exposure zeroed, embedding unchanged. Since P1
        # the embedding carries no treatment, so this is a real "no sponsored
        # neighbours" prediction.
        mu_unexposed = model.predict_unexposed(data)
        per_obs = []
        for p, pred, expo in zip(passes, preds, exposures):
            tau_p = doubly_robust_effect(
                pred, mu_unexposed, p["target"], p["interference"], final_prop
            )
            for o in p["obs"]:
                idx = id_to_index[o.neighbour_id]
                per_obs.append({
                    "creator_id": o.neighbour_id,
                    "kind": "exposed" if o.exposed else "control",
                    "name": id_to_name.get(o.neighbour_id, o.neighbour_id),
                    "span": f"{o.start}..{o.end}",
                    "rows": o.n_rows,
                    "target": o.value,
                    "pred": float(pred[idx].item()),
                    "sq_err": float((pred[idx].item() - o.value) ** 2),
                    "propensity": float(final_prop[idx].item()),
                    "exposed": bool(p["has_sponsored"][idx]),
                    "exposure": float(expo[idx].item()),
                    "mu_e_minus_mu_0": float((pred[idx] - mu_unexposed[idx]).item()),
                    "tau": float(tau_p[idx].item()),
                })

        targets_t = torch.tensor([r["target"] for r in per_obs])
        preds_t = torch.tensor([r["pred"] for r in per_obs])
        mse = float(((preds_t - targets_t) ** 2).mean().item())
        baseline_mse = float((targets_t ** 2).mean().item())
        per_node_sorted = sorted(per_obs, key=lambda r: r["sq_err"], reverse=True)
        print(f"\n=== Prod training result (N={n_obs} observations, {EPOCHS} epochs) ===")
        print(f"MSE trained: {mse:.4f}  baseline (always 0): {baseline_mse:.4f}  "
              f"improvement: {(baseline_mse - mse) / max(baseline_mse, 1e-12) * 100:.1f}%")
        exposed_rows = [r for r in per_obs if r["kind"] == "exposed"]
        control_rows = [r for r in per_obs if r["kind"] == "control"]
        if control_rows:
            c_mse = statistics.mean(r["sq_err"] for r in control_rows)
            print(f"Control observations: {len(control_rows)}, MSE {c_mse:.4f}")
        print("Exposed observations (sorted by sq_err descending):")
        for r in sorted(exposed_rows, key=lambda r: r["sq_err"], reverse=True):
            print(f"  {r['name'][:28]:28s} {r['span']} target={r['target']:+.3f} "
                  f"pred={r['pred']:+.3f} exposure={r['exposure']:.3f} "
                  f"sq_err={r['sq_err']:.3f} prop={r['propensity']:.3f}")
        print(f"Propensity stats: mean={final_prop.mean().item():.3f} min={final_prop.min().item():.3f} "
              f"max={final_prop.max().item():.3f}")
        if control_rows:
            print(f"  propensity on exposed obs: mean "
                  f"{statistics.mean(r['propensity'] for r in exposed_rows):.3f}; on controls: mean "
                  f"{statistics.mean(r['propensity'] for r in control_rows):.3f}")
        gap = statistics.mean(abs(r["mu_e_minus_mu_0"]) for r in exposed_rows)
        print(f"Mean |mu(e,X) - mu(0,X)| on exposed observations: {gap:.4f}  "
              f"(0.017 without controls; near zero means the head ignores exposure)")

        # In-sample AIPW. Two summaries: over every observation (the AIPW ATE,
        # which the controls dominate numerically) and over the exposed ones,
        # which is the population the spillover question is about. Still
        # in-sample: cross-fitting (P5) is what makes either quotable.
        taus = torch.tensor([r["tau"] for r in per_obs])
        ate = float(taus.mean().item())
        n_clusters = n_obs
        naive_se = float(taus.std(unbiased=True).item() / n_obs ** 0.5) if n_obs > 1 else float("nan")
        tau_exp = torch.tensor([r["tau"] for r in exposed_rows])
        mean_tau_exposed = float(tau_exp.mean().item())

        print("\n=== Causal estimate (AIPW spillover effect, in-sample) ===")
        print(f"ATE (all {n_obs} observations): {ate:+.4f}")
        print(f"Naive SE:                      {naive_se:.4f}")
        print(f"Rough 95% interval:            [{ate - 1.96 * naive_se:+.4f}, {ate + 1.96 * naive_se:+.4f}]")
        print(f"Mean tau on the {len(exposed_rows)} exposed:    {mean_tau_exposed:+.4f}")
        print(f"Matched DiD (no model), for comparison: {did['estimate']:+.4f}  SE {did['se']:.4f}"
              f"  (median version {did['median_estimate']:+.4f})")
        print("  SEs ignore nuisance-model uncertainty and assume independent")
        print("  observations, so they understate the true width. Do not quote them bare.")
        tau_sorted = sorted(per_obs, key=lambda r: -abs(r["tau"]))
        print("Largest per-observation effects (|tau| descending, top 15):")
        for r in tau_sorted[:15]:
            print(f"  {r['kind']:7s} {r['name'][:28]:28s} {r['span']} tau={r['tau']:+.3f}")

        # E12e. The learned transmission shares: which relation carries
        # spillover. This is an explainability claim in the write-up and no
        # artifact recorded it -- `transmission_shares()` was defined and never
        # called anywhere in the codebase.
        beta = model.transmission_shares()
        print("\nLearned transmission shares (beta):")
        for rel, share in sorted(beta.items(), key=lambda kv: -kv[1]):
            print(f"  {rel:24s} {share:.3f}")

    # Save checkpoint
    models_dir = Path(__file__).resolve().parents[1] / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    scaler = {"mean": mean.tolist(), "std": std.tolist()}
    # Also store full creator tensors for offline inference (no DB needed at inference time)
    # Keep edge indices as lists for JSON-serializable scaler, but tensors for checkpoint
    checkpoint = {
        "state_dict": model.state_dict(),
        "config": {
            "creator_feature_dim": CREATOR_FEATURE_DIM,
            "hidden_channels": HIDDEN_CHANNELS,
            "heads": HEADS,
            "backbone_sees_treatment": model.backbone_sees_treatment,
            "epochs": EPOCHS,
            "lr": LR,
            "seed": SEED,
            "loss_weights": {"prediction": loss_weights.prediction, "overlap": loss_weights.overlap,
                             "smoothness": loss_weights.smoothness, "consistency": loss_weights.consistency},
        },
        "feature_scaler": scaler,
        "training_pair_ids": labeled_ids,
        "training_pair_details": detailed,
        "git_sha": get_git_sha(),
        "pair_count": {
            "computable_pairs": pair_summary["computable_pairs"],
            "checks_evaluated": pair_summary["checks_evaluated"],
            "distinct_directed_creator_pairs": pair_summary["distinct_directed_creator_pairs"],
            "distinct_undirected_creator_pairs": pair_summary["distinct_undirected_creator_pairs"],
            "distinct_events_yielding_pairs": pair_summary["distinct_events_yielding_pairs"],
            "events_total": pair_summary["events_total"],
            "collab_edge_pairs": pair_summary["collab_edge_pairs"],
            "fail_no_before_only": pair_summary["fail_no_before_only"],
            "fail_no_after_only": pair_summary["fail_no_after_only"],
            "fail_neighbour_silent": pair_summary["fail_neighbour_silent"],
            "same_platform_computable": len([d for d in detailed if d["mean_lift"] is not None]),
            "cross_platform_only": len([d for d in detailed if d["mean_lift"] is None]),
            "effective_N_labeled_nodes": len(labeled_idx),
            # E12f. The number to quote. `effective_N_labeled_nodes` above counts
            # creators; E2 established that several of a creator's rows can be one
            # engagement change measured repeatedly, so the honest sample size is
            # the count of independent CLUSTERS. Both are recorded because they
            # differ and the difference is a finding.
            "effective_N_clusters": n_clusters,
        },
        # E12. The causal estimate and the learned transmission shares -- the two
        # outputs the thesis actually argues from. Neither was previously saved.
        "causal_estimate": {
            "ate_per_observation": ate,
            "naive_se": naive_se,
            "n_independent_observations": n_clusters,
            "dr_mode": "aipw",
            "in_sample": True,
            "target": LIFT_KEY,
            "treatment_definition": (
                "has_sponsored_neighbour within the observation's own measurement "
                "window (P2); sponsorship = is_sponsored OR Instagram paid-partnership label"
            ),
            "excluded_self_sponsored_rows": len(self_sponsored),
            "n_exposed": len(treated_obs),
            "n_control": len(controls),
            "mean_tau_exposed": mean_tau_exposed,
            "matched_did": did,
            "per_observation_tau": tau_sorted,
            "se_caveat": (
                "Assumes independent observations and ignores uncertainty in the "
                "propensity and outcome models. A floor on the true width."
            ),
        },
        "observations": [
            {"creator_id": o.neighbour_id, "start": str(o.start), "end": str(o.end),
             "rows": o.n_rows, "value": o.value, "cluster_id": o.cluster_id,
             "exposed": o.exposed}
            for o in observations
        ],
        "transmission_shares": beta,
        # E10. Heuristic, reported for inspection -- no pair was excluded on it.
        "bot_scores": bot_scores,
        "graph": {
            "num_creators": num_creators,
            "num_brands": brand_x.size(0),
            "collab_edges_directed": int(collab_index.size(1)),
            "coocc_edges_directed": int(cooccur_index.size(1)),
            "creator_ids_order": order,
            "creator_id_to_name": id_to_name,
        },
        # For offline inference without DB / without re-extracting CLIP/BERT
        "tensors": {
            "creator_x_raw": creator_x,  # unnormalized, for reference
            "creator_x_norm": x_norm,
            "brand_x": brand_x,
            "collab_edge_index": collab_index,
            "collab_edge_attr": collab_attr,
            "coocc_edge_index": cooccur_index,
            "coocc_edge_attr": cooccur_attr,
            # P2: sponsored in the window up to `treatment_as_of`, not all-time.
            "treatment": treatment,
            "target": target,
        },
        "treatment_as_of": str(latest),
        "training_stats": {
            "mse_trained": mse,
            "baseline_mse": baseline_mse,
            "per_node": per_node_sorted,
            "final_propensity_mean": float(final_prop.mean().item()),
            "final_propensity_min": float(final_prop.min().item()),
            "final_propensity_max": float(final_prop.max().item()),
            "history_last": history[-1] if history else {},
        },
    }

    ckpt_path = models_dir / "gail_checkpoint.pt"
    torch.save(checkpoint, ckpt_path)
    print(f"\nSaved checkpoint to {ckpt_path} ({ckpt_path.stat().st_size / 1024:.1f} KB)")

    scaler_path = models_dir / "feature_scaler.json"
    with open(scaler_path, "w", encoding="utf-8") as f:
        json.dump(scaler, f, indent=2)
    print(f"Saved scaler to {scaler_path}")

    # Also write a tiny training_pair_ids.json for inspectability
    with open(models_dir / "training_pair_ids.json", "w", encoding="utf-8") as f:
        json.dump(labeled_ids, f, indent=2)
    print(f"Saved training pair ids to {models_dir / 'training_pair_ids.json'}")

    conn.close()
    # Emit machine-readable report for CI
    print("\n---REPORT---")
    print(json.dumps({
        "computable_pairs": pair_summary["computable_pairs"],
        "directed": pair_summary["distinct_directed_creator_pairs"],
        "undirected": pair_summary["distinct_undirected_creator_pairs"],
        "events_yielding": pair_summary["distinct_events_yielding_pairs"],
        "effective_N": len(labeled_idx),
        "mse_trained": mse,
        "baseline_mse": baseline_mse,
        "ckpt": str(ckpt_path),
        "git_sha": checkpoint["git_sha"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())