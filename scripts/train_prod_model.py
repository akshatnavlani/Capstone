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

import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

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
TRACK_A_INGESTION = Path(__file__).resolve().parents[2] / "track-a-data-infra" / "scripts" / "ingestion"
if TRACK_A_INGESTION.exists():
    sys.path.insert(0, str(TRACK_A_INGESTION))

import psycopg2  # noqa: E402
from pair_count import compute as pair_count_compute  # noqa: E402

from ml.feature_extraction import FeatureExtractor, RawCreatorRecord  # noqa: E402
from ml.gail_model import GAILModel  # noqa: E402
from ml.schema import (  # noqa: E402
    BRAND_METADATA_DIM,
    CREATOR_FEATURE_DIM,
    NUM_BRAND_CATEGORIES,
    empty_hetero_data,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLATFORM_TABLES = {
    "instagram": ("instagram_posts", "posted_at", "like_count", "comment_count"),
    "youtube": ("youtube_videos", "published_at", "view_count", "like_count"),
    "reddit": ("reddit_posts", "posted_at", "score", "num_comments"),
}

# Must match backend/app/feature_store.py CREATOR_CATEGORIES exactly
CREATOR_CATEGORIES = (
    "athlete",
    "team",
    "league",
    "fitness_influencer",
    "lifestyle_influencer",
    "other",
)

HIDDEN_CHANNELS = 16
HEADS = 2
EPOCHS = 100
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


def compute_feature_scaler(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Per-dim mean/std over N creators. Std clamped to avoid div/0."""
    mean = x.mean(dim=0)
    std = x.std(dim=0, unbiased=False)
    std = std.clamp(min=1e-6)
    # One-hot dims have tiny std; keep them as-is — clamping prevents explosion
    return mean, std


def platform_engagement(cur, creator_id: str, platform: str, event_date):
    """Real (fully-measured) engagement only — BOTH cols must be non-null.

    Layer 1 fix: coalesce NULL→0 fabricated million-percent lifts (28% of
    instagram_posts have like_count, 39% have comment_count, and the missingness
    is temporally skewed — pre-2026 posts are mostly both-NULL).
    Layer 2 fix: even after excluding both-NULL, posts with only the smaller
    metric measured (comment_count present, like_count NULL) still bias the avg.
    So require BOTH columns non-null, per compute_training_pair_deltas.py.
    """
    table, date_col, e1, e2 = PLATFORM_TABLES[platform]
    cur.execute(
        f"select {date_col}, {e1}, {e2} "
        f"from {table} where creator_id::text = %s and {date_col} is not null "
        f"and {e1} is not null and {e2} is not null order by {date_col}",
        (creator_id,),
    )
    rows = cur.fetchall()
    before = [e1v + e2v for d, e1v, e2v in rows if d < event_date]
    after = [e1v + e2v for d, e1v, e2v in rows if d > event_date]
    return before, after


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
            before, after = platform_engagement(cur, neighbour_id, platform, event_date)
            if before and after:
                before_avg = statistics.mean(before)
                after_avg = statistics.mean(after)
                lift = (after_avg - before_avg) / (before_avg + 1)
                platform_lifts[platform] = {
                    "n_before": len(before),
                    "n_after": len(after),
                    "avg_before": before_avg,
                    "avg_after": after_avg,
                    "lift": lift,
                }
        if platform_lifts:
            same_platform_rows += 1
            mean_lift = statistics.mean(v["lift"] for v in platform_lifts.values())
            lifts_by_neighbour.setdefault(neighbour_id, []).append(mean_lift)
            detailed.append({
                "event_creator_id": event_creator_id,
                "item_id": item_id,
                "event_platform": event_platform,
                "event_date": str(event_date),
                "neighbour_id": neighbour_id,
                "platform_lifts": platform_lifts,
                "mean_lift": mean_lift,
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
            })

    target = torch.zeros(num_creators, dtype=torch.float32)
    for nid, lifts in lifts_by_neighbour.items():
        if nid in creator_id_to_index:
            target[creator_id_to_index[nid]] = statistics.mean(lifts)

    n_labeled = len(lifts_by_neighbour)
    print(f"Same-platform-computable lifts: {same_platform_rows}/{len(good_rows)} "
          f"(cross-platform-only straddle, no lift: {cross_platform_only}/{len(good_rows)})")
    if n_labeled:
        vals = [statistics.mean(v) for v in lifts_by_neighbour.values()]
        vals_sorted = sorted(vals)
        print(f"Lift distribution (mean lift per neighbour, N={n_labeled}): "
              f"min={vals_sorted[0]:.4f} median={statistics.median(vals_sorted):.4f} "
              f"mean={statistics.mean(vals_sorted):.4f} max={vals_sorted[-1]:.4f}")

    return target, lifts_by_neighbour, summary, detailed


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

    # Engagement helper needs videos/posts per creator for rate
    # We'll compute engagement_rate lazily per creator inside loop

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
        cur.execute("select title, description, thumbnail_url, view_count, like_count, comment_count from youtube_videos where creator_id::text=%s limit 20", (cid,))
        yt_videos = cur.fetchall()
        cur.execute("select caption, thumbnail_url, like_count, comment_count from instagram_posts where creator_id::text=%s limit 20", (cid,))
        ig_posts = cur.fetchall()

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
        print(f"  [{idx+1}/{len(creator_rows)}] extracting features for {name!r} (yt_subs={yt_subs} ig_followers={ig_followers} thumbs={len(thumbs)})...")
        vec = extractor.extract(record)
        assert vec.shape[0] == CREATOR_FEATURE_DIM, f"dim mismatch {vec.shape[0]} != {CREATOR_FEATURE_DIM}"
        vecs.append(vec)
        id_to_index[cid] = idx
        order.append(cid)
        id_to_name[cid] = name
        id_to_category[cid] = category or "other"

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


def load_treatment(cur, id_to_index: dict[str, int], num_creators: int):
    cur.execute("select distinct creator_id::text from creator_sponsorship_events")
    sponsored = {r[0] for r in cur.fetchall()}
    t = torch.zeros(num_creators, dtype=torch.float32)
    for cid in sponsored:
        if cid in id_to_index:
            t[id_to_index[cid]] = 1.0
    return t


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
        brand_x, brand_id_to_index = load_brands(cur)
        # sponsorship edges not needed for training except maybe reporting — build empty
        sponsors_index = torch.empty((2,0), dtype=torch.long)
        sponsored_by_index = torch.empty((2,0), dtype=torch.long)
    else:
        creator_x, id_to_index, order, id_to_name, _ = build_creator_features(cur, extractor)
        num_creators = creator_x.size(0)
        print(f"Creator features: {num_creators} creators, dim {creator_x.shape[1]}")
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

    treatment = load_treatment(cur, id_to_index, num_creators)
    n_sponsored = int(treatment.sum().item())
    print(f"Treatment: {n_sponsored}/{num_creators} creators have is_sponsored event")

    # Targets from canonical pair_count + platform_engagement (both-engagement-cols fix)
    target, lifts_by_neighbour, pair_summary, detailed = build_targets_from_canonical(cur, id_to_index, num_creators)
    labeled_idx = [id_to_index[cid] for cid in lifts_by_neighbour if cid in id_to_index]
    labeled_ids = [cid for cid in lifts_by_neighbour if cid in id_to_index]
    print(f"Labeled creator-nodes (distinct neighbours with same-platform lift): {len(labeled_idx)}")
    for cid, lifts in lifts_by_neighbour.items():
        if cid in id_to_index:
            print(f"  {id_to_name.get(cid, cid)[:30]:30s} N={len(lifts)} mean_lift={statistics.mean(lifts):+.4f}")

    if not labeled_idx:
        print("ERROR: no labeled nodes — cannot train")
        conn.close()
        return 1

    # Feature normalization — per-dim z-score, saved for inference
    mean, std = compute_feature_scaler(creator_x)
    # Apply normalization BEFORE training (so propensity head sees normalized features)
    x_norm = (creator_x - mean) / std
    data["creator"].x = x_norm
    print(f"Feature scaler: mean abs {mean.abs().mean():.4f}, std mean {std.mean():.4f} "
          f"(propensity head will receive normalized features — fixes saturation)")

    # Training — single model on ALL pairs
    from ml.causal_regularization import has_sponsored_neighbor
    from ml.gail_loss import GAILLossWeights, compute_gail_loss

    torch.manual_seed(SEED)
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM, hidden_channels=HIDDEN_CHANNELS, heads=HEADS)

    # Use full mask for supervised term (all labeled nodes)
    num_creators_t = data["creator"].x.size(0)
    train_mask = torch.zeros(num_creators_t, dtype=torch.bool)
    train_mask[labeled_idx] = True

    collab_edge_index = data["creator", "collaborates_with", "creator"].edge_index
    collab_edge_weight = data["creator", "collaborates_with", "creator"].edge_attr
    has_sponsored = has_sponsored_neighbor(collab_edge_index, treatment)
    loss_weights = GAILLossWeights()

    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    history = []
    for epoch in range(EPOCHS):
        model.train()
        optimizer.zero_grad()
        prediction, exposure, propensity = model(data, treatment)
        loss, comps = compute_gail_loss(
            prediction, target, propensity, collab_edge_index, collab_edge_weight,
            has_sponsored, loss_weights, prediction_mask=train_mask, treatment=treatment,
        )
        loss.backward()
        optimizer.step()
        history.append(comps)
        if (epoch + 1) % 20 == 0 or epoch == 0:
            print(f"  epoch {epoch+1}/{EPOCHS}: total={comps['total']:.4f} pred={comps['prediction']:.4f} "
                  f"overlap={comps['overlap']:.4f} prop_mean={propensity.mean().item():.3f} "
                  f"prop_min={propensity.min().item():.3f} max={propensity.max().item():.3f}")

    # Final evaluation on trained nodes
    model.eval()
    with torch.no_grad():
        final_pred, _, final_prop = model(data, treatment)
        labeled_pred = final_pred[labeled_idx]
        labeled_target = target[labeled_idx]
        mse = F.mse_loss(labeled_pred, labeled_target).item()
        baseline_mse = (labeled_target ** 2).mean().item()
        per_node = []
        for idx, cid in zip(labeled_idx, labeled_ids):
            per_node.append({
                "creator_id": cid,
                "name": id_to_name.get(cid, cid),
                "target": float(target[idx].item()),
                "pred": float(final_pred[idx].item()),
                "sq_err": float((final_pred[idx] - target[idx]) ** 2),
                "propensity": float(final_prop[idx].item()),
            })
        per_node_sorted = sorted(per_node, key=lambda r: r["sq_err"], reverse=True)
        print(f"\n=== Prod training result (N={len(labeled_idx)} labeled nodes, {EPOCHS} epochs) ===")
        print(f"MSE trained: {mse:.4f}  baseline (always 0): {baseline_mse:.4f}  "
              f"improvement: {(baseline_mse - mse) / baseline_mse * 100:.1f}%")
        print("Per-node (sorted by sq_err descending — Kohli outlier expected):")
        for r in per_node_sorted:
            print(f"  {r['name'][:28]:28s} target={r['target']:+.3f} pred={r['pred']:+.3f} sq_err={r['sq_err']:.3f} prop={r['propensity']:.3f}")
        print(f"Propensity stats: mean={final_prop.mean().item():.3f} min={final_prop.min().item():.3f} max={final_prop.max().item():.3f} "
              f"(saturation to 1.000 fixed if max < 0.999)")

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
        },
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
            "treatment": treatment,
            "target": target,
        },
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
