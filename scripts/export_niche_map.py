"""Niche Map data (22 Nov 2026): every creator with content vectors, placed on a 2D map by what their content is like.

    python scripts/export_niche_map.py      # writes frontend/public/niche_map.json

Real data only. Content = the CLIP (thumbnails, 512) and BERT (titles/captions, 768) parts of each creator's feature
vector from the final GAIL-R run (660 creators, see load_vectors), each part scaled to unit length so neither dominates; the two
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


def load_vectors(cur):
    """22 Nov 2026: the FINAL GAIL-R run's creator vectors (660 creators, data of 21 Nov), saved in
    models/gail_r_inputs_final_22nov.pt in the order of train_prod_model.py's query (creators ORDER BY name), standardised
    with models/feature_scaler_final_small_21nov.json. The order is checked against each row's stored category one-hot."""
    from ml.schema import CREATOR_CATEGORIES
    z = torch.load(ROOT / "models" / "gail_r_inputs_final_22nov.pt", map_location="cpu", weights_only=False)
    s = json.loads((ROOT / "models" / "feature_scaler_final_small_21nov.json").read_text())
    x = z["data"]["creator"].x.float() * torch.tensor(s["std"]) + torch.tensor(s["mean"])
    cur.execute("select creator_id::text, name, category from creators order by name")
    rows = cur.fetchall()
    assert len(rows) == x.size(0), f"{len(rows)} creators now vs {x.size(0)} vectors: re-run the final inputs"
    oh = x[:, -len(CREATOR_CATEGORIES):]
    ok = sum(int(c in CREATOR_CATEGORIES and int(oh[i].argmax()) == CREATOR_CATEGORIES.index(c)) or int(c not in CREATOR_CATEGORIES)
             for i, (_cid, _n, c) in enumerate(rows))
    assert ok == len(rows), f"creator order check failed ({ok}/{len(rows)})"
    return [r[0] for r in rows], {r[0]: r[1] for r in rows}, x


def main() -> int:
    import psycopg2
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    ids, names, x = load_vectors(cur)
    clip, bert = x[:, :CLIP_DIM], x[:, CLIP_DIM:CLIP_DIM + BERT_DIM]
    unit = lambda m: m / m.norm(dim=1, keepdim=True).clamp(min=1e-8)  # noqa: E731
    # Missing parts are zero before standardising; after undoing it they are ~0.005 of rounding, so 0.01 separates them.
    has_clip, has_bert = clip.abs().max(1).values > 0.01, bert.abs().max(1).values > 0.01
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
    out = {"source": "final GAIL-R run inputs (21 Nov data): creator content vectors (CLIP 512 + BERT 768), PCA to 2D; niche by keywords",
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
