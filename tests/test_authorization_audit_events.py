"""Integration tests for authorization-denial/grant audit events (Phase 1.5 PR 5)."""
from app.db.session import SessionLocal
from app.models.audit import AuditEvent
from tests.auth_test_helpers import auth_headers, register_and_login


def _denied_events():
    db = SessionLocal()
    try:
        return db.query(AuditEvent).filter(AuditEvent.event_name == "authorization.access_denied").all()
    finally:
        db.close()


def test_cross_student_read_denial_is_recorded(client):
    victim_id, _ = register_and_login(client, "authz-victim@example.com")
    _, attacker_token = register_and_login(client, "authz-attacker@example.com")

    resp = client.get(f"/api/v1/students/{victim_id}/knowledge-profile", headers=auth_headers(attacker_token))
    assert resp.status_code == 403

    rows = _denied_events()
    assert any(r.reason_code == "STUDENT_READ_ACCESS_DENIED" and r.target_user_id == victim_id for r in rows)


def test_student_write_denial_is_recorded(client):
    victim_id, _ = register_and_login(client, "authz-write-victim@example.com")
    _, attacker_token = register_and_login(client, "authz-write-attacker@example.com")

    resp = client.post(f"/api/v1/dashboard/students/{victim_id}/snapshots", headers=auth_headers(attacker_token))
    assert resp.status_code == 403

    rows = _denied_events()
    assert any(r.reason_code == "STUDENT_WRITE_ACCESS_DENIED" and r.target_user_id == victim_id for r in rows)


def test_admin_only_denial_is_recorded(client):
    _, student_token = register_and_login(client, "authz-nonadmin@example.com")

    resp = client.post("/api/v1/skills", json={"code": "x", "name": "X", "domain": "algebra"}, headers=auth_headers(student_token))
    assert resp.status_code == 403

    rows = _denied_events()
    assert any(r.reason_code == "NOT_ADMIN" for r in rows)


def test_ensure_self_denial_is_recorded(client):
    victim_id, _ = register_and_login(client, "authz-self-victim@example.com")
    _, attacker_token = register_and_login(client, "authz-self-attacker@example.com")

    resp = client.get(f"/api/v1/dashboard/viewers/{victim_id}/overview", headers=auth_headers(attacker_token))
    assert resp.status_code == 403

    rows = _denied_events()
    assert any(r.reason_code == "NOT_SELF" and r.target_user_id == victim_id for r in rows)
