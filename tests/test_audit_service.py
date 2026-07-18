"""Unit tests for AuditService (Phase 1.5 PR 5)."""
import pytest

from app.db.session import SessionLocal
from app.models.audit import AuditEvent
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_record_persists_all_fields(db):
    service = AuditService(AuditRepository(db))
    service.record(
        "auth.login.success",
        category="authentication",
        outcome="success",
        actor_user_id="user_1",
        target_user_id="user_2",
        resource_type="dashboard_access_grant",
        resource_id="grant_1",
        reason_code="SOME_REASON",
        metadata={"revoked_count": 3},
    )
    row = db.query(AuditEvent).one()
    assert row.event_name == "auth.login.success"
    assert row.category == "authentication"
    assert row.outcome == "success"
    assert row.actor_user_id == "user_1"
    assert row.target_user_id == "user_2"
    assert row.resource_type == "dashboard_access_grant"
    assert row.resource_id == "grant_1"
    assert row.reason_code == "SOME_REASON"
    assert row.event_metadata == {"revoked_count": 3}


def test_record_defaults_optional_fields_to_none(db):
    service = AuditService(AuditRepository(db))
    service.record("auth.logout", category="authentication", outcome="success")
    row = db.query(AuditEvent).one()
    assert row.actor_user_id is None
    assert row.target_user_id is None
    assert row.resource_type is None
    assert row.resource_id is None
    assert row.reason_code is None
    assert row.event_metadata is None


class _FailingRepository:
    def save(self, event):
        raise RuntimeError("db unavailable")


def test_record_fails_open_on_repository_error():
    """Fail-open is the explicit architecture-review decision: an audit
    write failure must never propagate to the caller."""
    service = AuditService(_FailingRepository())
    service.record("auth.login.success", category="authentication", outcome="success")
