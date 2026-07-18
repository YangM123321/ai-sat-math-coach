"""Integration test for the administrative access-grant audit event (Phase 1.5 PR 5)."""
from app.db.session import SessionLocal
from app.models.audit import AuditEvent
from tests.auth_test_helpers import auth_headers, register_and_login


def test_grant_creation_records_access_granted_event(client):
    admin_id, admin_token = register_and_login(client, "grant-admin@example.com", role="admin")
    admin = auth_headers(admin_token)
    teacher_id, _ = register_and_login(client, "grant-teacher@example.com", role="teacher")
    student_id, _ = register_and_login(client, "grant-student@example.com")

    resp = client.post(
        "/api/v1/dashboard/access-grants",
        json={"viewer_id": teacher_id, "student_id": student_id, "role": "teacher"},
        headers=admin,
    )
    assert resp.status_code == 201
    grant_id = resp.json()["id"]

    db = SessionLocal()
    try:
        row = db.query(AuditEvent).filter(AuditEvent.event_name == "authorization.access_granted").one()
    finally:
        db.close()

    assert row.category == "authorization"
    assert row.outcome == "success"
    assert row.actor_user_id == admin_id
    assert row.target_user_id == student_id
    assert row.resource_type == "dashboard_access_grant"
    assert row.resource_id == grant_id
    assert row.event_metadata == {"viewer_id": teacher_id, "role": "teacher"}
