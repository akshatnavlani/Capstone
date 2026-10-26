"""Live check of the three fusion inputs for the verified 150 creators: real value, or the neutral fallback? READ ONLY.

    python scripts/check_live_scores.py        (run from the repository root; about two minutes: it loads CLIP and BERT)

Run it after every retrain. The spillover line should show far fewer 'isolated' creators once the shared-brand relation is in the graph the model reads
(26 Oct 2026: 145 of the 150 were 'isolated', 4 'inferred', 1 'trained'; sentiment 149 scored; creator feature 150 scored).
"""
import collections
import os
import statistics as st
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, ROOT)
os.environ.pop("CREATOR_FEATURES_DISABLED", None)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import psycopg2  # noqa: E402
from dotenv import dotenv_values  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.creator_features import get_feature_scores  # noqa: E402
from app.database import engine  # noqa: E402
from app.models import Creator  # noqa: E402
from app.spillover import get_spillover_batch  # noqa: E402
from app.temporal import get_temporal_batch  # noqa: E402

url = os.environ.get("DATABASE_URL") or dotenv_values(os.path.join(ROOT, ".env"))["DATABASE_URL"]
cur = psycopg2.connect(url).cursor()
cur.execute("select creator_id::text from creator_verification where creator_id is not null and link_level in ('confirmed','probable')")
ver = [r[0] for r in cur.fetchall()]
with Session(engine) as s:
    creators = s.exec(select(Creator).limit(1000)).all()
    ids = [str(c.creator_id) for c in creators]
    print(f"creators in the app table: {len(ids)}; verified 150 present: {len(set(ids) & set(ver))}")
    sp = get_spillover_batch([c.creator_id for c in creators])
    tm = get_temporal_batch(s)
t0 = time.time()
fm = None
while fm is None and time.time() - t0 < 240:
    fm = get_feature_scores("whey protein")
    time.sleep(2)
print(f"feature models ready after {time.time() - t0:.0f}s: {fm is not None}")
for name, mapping in (("SPILLOVER", sp), ("SENTIMENT/RISK", tm), ("CREATOR FEATURE (CLIP/BERT)", fm or {})):
    c = collections.Counter(mapping[i]["basis"] if i in mapping else "missing" for i in ver)
    print(f"{name}: {dict(c)}")


def spread(label, vals):
    if vals:
        print(f"{label}: n {len(vals)}, min {min(vals):.2f}, median {st.median(vals):.2f}, max {max(vals):.2f}, sd {st.pstdev(vals):.2f}")


spread("feature scores for 'whey protein'", [fm[i]["score"] for i in ver if fm and i in fm and fm[i]["basis"] == "scored"])
spread("sentiment/risk scores", [tm[i]["sentiment_risk_score"] for i in ver if i in tm and tm[i]["basis"] == "scored"])
spread("spillover percentile (trained/inferred)", [sp[i]["spillover_unit"] for i in ver if i in sp and sp[i]["basis"] in ("trained", "inferred")])
