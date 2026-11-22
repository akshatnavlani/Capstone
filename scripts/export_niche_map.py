"""Niche Map data (22 Nov 2026): every creator the app's model knows, placed on a 2D map by its CONTENT vectors.

    python scripts/export_niche_map.py      # writes frontend/public/niche_map.json

Real data only. Content = the CLIP (thumbnails, 512) and BERT (titles/captions, 768) parts of each creator's feature
vector in the app checkpoint (models/gail_checkpoint.pt), each part scaled to unit length so neither dominates; the two
axes are the top-2 principal components. Creators close together post similar-looking, similar-sounding content.
Niche = a keyword rule on the creator's name and YouTube channel title/description (shown on screen as "by keywords").
READ ONLY on the database.
"""
import json
import re
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
sys.path.insert(0, str(ROOT))
from ml.schema import BERT_DIM, CLIP_DIM  # noqa: E402
from orchestrator import load_env  # noqa: E402

NICHES = [  # first match wins
    ("Yoga and wellness", r"\byog|yoga|meditat|spiritual|mindful|wellness|ayurved|pranayam|heartfulness"),
    ("Nutrition and health", r"nutrition|diet|dietitian|doctor|\bdr\b|physio|health|recipe|food|weight ?loss"),
    ("Running and endurance", r"\brun(ner|ning|s)?\b|marathon|cycling|cyclist|triathlon|endurance"),
    ("Gym and bodybuilding", r"gym|bodybuild|muscle|physique|ifbb|powerlift|calisthenic|workout|fitness|transformation|strength"),
]
SPORTS = {"athlete", "team", "league"}


def main() -> int:
    ck = torch.load(ROOT / "models" / "gail_checkpoint.pt", map_location="cpu", weights_only=False)
    ids = ck["graph"]["creator_ids_order"]
    names = ck["graph"]["creator_id_to_name"]
    x = ck["tensors"]["creator_x_raw"].float()
    clip, bert = x[:, :CLIP_DIM], x[:, CLIP_DIM:CLIP_DIM + BERT_DIM]
    unit = lambda m: m / m.norm(dim=1, keepdim=True).clamp(min=1e-8)  # noqa: E731
    has_clip, has_bert = clip.abs().sum(1) > 0, bert.abs().sum(1) > 0
    # 115 creators have text but no thumbnail vector: a zero thumbnail part would make the first axis just "has
    # thumbnails or not". Their thumbnail part is set to the average thumbnail vector instead (neutral after centring).
    uc, ub = unit(clip), unit(bert)
    uc[~has_clip] = uc[has_clip].mean(0)
    ub[~has_bert] = ub[has_bert].mean(0)
    content = torch.cat([uc, ub], dim=1)
    has = has_clip | has_bert
    c = content - content[has].mean(0)
    _, s, v = torch.linalg.svd(c[has], full_matrices=False)
    xy = c @ v[:2].T
    share = (s[:2] ** 2 / (s ** 2).sum()).tolist()

    import psycopg2
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    cur.execute("""select c.creator_id::text, c.category, coalesce(max(y.title), ''), coalesce(max(y.description), ''), max(y.subscriber_count)
                   from creators c left join youtube_channels y on y.creator_id = c.creator_id group by 1, 2""")
    meta = {r[0]: r[1:] for r in cur.fetchall()}

    # Robust scaling: the 2nd-98th percentile range fills the map; the few extreme outliers are pinned to the edge, so
    # they do not squash everyone else into a corner. Relative positions inside that range are unchanged.
    lo, hi = torch.quantile(xy[has], 0.02, dim=0), torch.quantile(xy[has], 0.98, dim=0)
    pts = []
    for i, cid in enumerate(ids):
        if not bool(has[i]):
            continue
        cat, title, desc, subs = meta.get(str(cid), ("other", "", "", None))
        text = f"{names.get(cid, '')} {title} {desc}".lower()
        niche = "Sports and athletes" if cat in SPORTS else next((n for n, pat in NICHES if re.search(pat, text)), "Lifestyle and other")
        p = ((xy[i] - lo) / (hi - lo).clamp(min=1e-8)).clamp(0, 1).tolist()
        pts.append({"creator_id": str(cid), "name": names.get(cid, ""), "category": cat, "niche": niche,
                    "subscribers": subs, "x": round(p[0], 4), "y": round(p[1], 4)})
    out = {"source": "models/gail_checkpoint.pt creator content vectors (CLIP 512 + BERT 768), PCA to 2D; niche by keywords",
           "creators": len(pts), "variance_shown": [round(t, 4) for t in share], "points": pts}
    dest = ROOT / "frontend" / "public" / "niche_map.json"
    dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    counts = {}
    for p in pts:
        counts[p["niche"]] = counts.get(p["niche"], 0) + 1
    print(f"{len(pts)} creators -> {dest}; variance shown {share[0]:.1%} + {share[1]:.1%}; niches {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
