"""GET /alerts returns creator names with each alert, so the Monitoring page shows names immediately (26 Oct 2026: the page used to show raw ids for about 11 s
while it waited for /feature-store/creators)."""
import uuid

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import Creator, RiskAlert
from app.routers.alerts import list_alerts


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_alerts_carry_the_creator_and_the_collaborator_name():
    with _session() as s:
        a, b = Creator(name="Flagged Creator"), Creator(name="Source Collaborator")
        s.add(a)
        s.add(b)
        s.commit()
        s.refresh(a)
        s.refresh(b)
        s.add(RiskAlert(creator_id=a.creator_id, severity="low", reason="propagated", source="sentiment_propagation", propagated_from_creator_id=b.creator_id))
        s.add(RiskAlert(creator_id=b.creator_id, severity="high", reason="direct", source="manual"))
        s.commit()
        out = {r.reason: r for r in list_alerts(session=s)}
    assert out["propagated"].creator_name == "Flagged Creator" and out["propagated"].propagated_from_name == "Source Collaborator"
    assert out["direct"].creator_name == "Source Collaborator" and out["direct"].propagated_from_name is None


def test_alerts_for_an_unknown_creator_still_return_with_no_name():
    with _session() as s:
        s.add(RiskAlert(creator_id=uuid.uuid4(), severity="low", reason="orphan", source="manual"))
        s.commit()
        [row] = list_alerts(session=s)
    assert row.creator_name is None and row.propagated_from_name is None


def test_no_alerts_gives_an_empty_list():
    with _session() as s:
        assert list_alerts(session=s) == []
