"""What-if spillover scenario (31 Oct 2026): the REAL creator graph and the REAL, current sponsorships combined with an ASSUMED spillover strength.

WHY. The real data does not measure spillover: with 60 exposed observations the best estimate is about zero and effects above roughly 1.5x are ruled out (CAPSTONE_NEXT_STEPS.md).
So the app cannot show a measured spillover for any creator. This module lets a brand ask "if spillover were X, which creators would it reach?" and answers with the same exposure
the GAIL-R model reads (the share of a creator's linked collaborators that were sponsored recently), multiplied by the strength the user chooses.

WHAT IT IS NOT. It is not an estimate and it never changes a score, a ranking or a confidence interval. The strength is an assumption chosen by the user; the response says so.

    exposure      = sponsored collaborators in the last SPONSOR_WINDOW_DAYS / all linked collaborators
    projected     = exp(effect_log * exposure) - 1      (effect_log: 0.25 is about +28%, 0.5 about +65%, 1.0 about +172% for a fully exposed creator)
"""
import math
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app import feature_store
from app.models import Creator, InstagramPost, YouTubeVideo

SPONSOR_WINDOW_DAYS = 30
MAX_EFFECT_LOG = 2.0


def neighbour_sets(edges) -> dict[uuid.UUID, set[uuid.UUID]]:
    """Unordered neighbours of every creator from the collaboration edges (each pair appears once per direction)."""
    out: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for e in edges:
        if e.source_creator_id != e.target_creator_id:
            out[e.source_creator_id].add(e.target_creator_id)
            out[e.target_creator_id].add(e.source_creator_id)
    return out


def exposure(neighbours: set, sponsored: set) -> float:
    """Share of the linked collaborators that were sponsored recently; 0 for a creator with no links."""
    return len(neighbours & sponsored) / len(neighbours) if neighbours else 0.0


def projected_change(effect_log: float, share: float) -> float:
    """Expected relative change in engagement if spillover were `effect_log` (log scale) for a fully exposed creator, scaled by the exposed share."""
    return math.exp(effect_log * share) - 1.0


def recently_sponsored(session: Session, as_of: datetime | None = None, days: int = SPONSOR_WINDOW_DAYS) -> set[uuid.UUID]:
    cutoff = (as_of or datetime.now(timezone.utc)) - timedelta(days=days)
    yt = session.exec(select(YouTubeVideo.creator_id).where(YouTubeVideo.is_sponsored == True, YouTubeVideo.published_at >= cutoff)).all()  # noqa: E712
    ig = session.exec(select(InstagramPost.creator_id).where(InstagramPost.is_sponsored == True, InstagramPost.posted_at >= cutoff)).all()  # noqa: E712
    ig_paid = session.exec(select(InstagramPost.creator_id).where(InstagramPost.has_paid_partnership_label == True, InstagramPost.posted_at >= cutoff)).all()  # noqa: E712
    return {c for c in [*yt, *ig, *ig_paid] if c is not None}


def build_scenario(session: Session, effect_log: float, as_of: datetime | None = None) -> dict:
    effect_log = max(0.0, min(MAX_EFFECT_LOG, effect_log))
    neighbours = neighbour_sets(feature_store.build_collaboration_edges(session))
    sponsored = recently_sponsored(session, as_of)
    names = {c.creator_id: c.name for c in session.exec(select(Creator)).all()}
    rows = []
    for cid, nb in neighbours.items():
        share = exposure(nb, sponsored)
        hit = sorted(n for n in (nb & sponsored))
        rows.append({
            "creator_id": cid,
            "linked_collaborators": len(nb),
            "sponsored_collaborators": len(hit),
            "sponsored_names": [names.get(n, str(n)) for n in hit[:3]],
            "exposure": round(share, 3),
            "projected_change_pct": round(100 * projected_change(effect_log, share), 1),
        })
    rows.sort(key=lambda r: (-r["exposure"], -r["linked_collaborators"]))
    return {
        "assumed_effect_log": effect_log,
        "window_days": SPONSOR_WINDOW_DAYS,
        "creators_with_links": len(rows),
        "creators_exposed": sum(1 for r in rows if r["exposure"] > 0),
        "note": ("An assumption, not a measurement: the real data shows no detectable spillover (best estimate about zero; effects above about 1.5x are ruled out). "
                 "This shows who spillover would reach if it were the strength you chose. It does not change any score."),
        "rows": rows,
    }
