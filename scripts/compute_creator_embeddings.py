"""Embed every creator once and save models/creator_embeddings.npz (PendingWork S2).

Reads the database through the feature store (read only) and runs each
creator's thumbnails through CLIP and their scrubbed text through both CLIP's
text encoder and BERT, using the existing FeatureExtractor. Saves vectors, availability flags and the two
metadata values, so the API never has to touch the database or the images to
score a creator. Re-run it after the dataset changes.

    python scripts\\compute_creator_embeddings.py

Thumbnails are downloaded (up to 5 per creator, expired URLs are skipped). The
CLIP and BERT weights must already be in the Hugging Face cache or will be
downloaded on first use.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))


def database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    return re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')


def main() -> None:
    os.environ["DATABASE_URL"] = database_url()
    from ml._scipy_compat import avoid_blocked_scipy_solver

    avoid_blocked_scipy_solver()  # transformers imports scipy.optimize; see ml/_scipy_compat.py
    from sqlmodel import Session, create_engine

    from app.feature_store import build_creator_features
    from ml.creator_embeddings import bert_mean_vector, clip_text_vector
    from ml.feature_extraction import FeatureExtractor

    with Session(create_engine(os.environ["DATABASE_URL"])) as s:
        records = build_creator_features(s)
    n = len(records)
    print(f"{n} creators; loading CLIP and BERT (about a minute)...", flush=True)
    extractor = FeatureExtractor(max_thumbnails=5)

    clip = np.zeros((n, 512), dtype=np.float32)
    bert = np.zeros((n, 768), dtype=np.float32)
    clip_text = np.zeros((n, 512), dtype=np.float32)
    has_img = np.zeros(n, dtype=bool)
    has_text = np.zeros(n, dtype=bool)
    t0 = time.time()
    for i, r in enumerate(records):
        if r.thumbnail_urls:
            v = extractor._clip_embedding(r.thumbnail_urls).numpy()
            if np.any(v):  # all thumbnails failed to download -> zeros -> not available
                clip[i], has_img[i] = v, True
        if r.raw_text and r.raw_text.strip():
            bert[i], clip_text[i], has_text[i] = bert_mean_vector(extractor, r.raw_text), clip_text_vector(extractor, r.raw_text), True
        if (i + 1) % 25 == 0 or i + 1 == n:
            print(f"  {i + 1}/{n} ({time.time() - t0:.0f}s)", flush=True)

    out = ROOT / "models" / "creator_embeddings.npz"
    np.savez_compressed(
        out,
        ids=np.array([str(r.creator_id) for r in records]),
        clip=clip, bert=bert, clip_text=clip_text, has_img=has_img, has_text=has_text,
        engagement=np.array([np.nan if r.engagement_rate is None else r.engagement_rate for r in records], dtype=np.float64),
        log_reach=np.array([np.nan if r.log_subscriber_count is None else r.log_subscriber_count for r in records], dtype=np.float64),
    )
    print(f"saved {out}: images for {int(has_img.sum())}, text for {int(has_text.sum())}, "
          f"neither for {int((~has_img & ~has_text).sum())}")


if __name__ == "__main__":
    main()
