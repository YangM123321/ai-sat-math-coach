"""Integration tests for authentication audit events (Phase 1.5 PR 5)."""
from app.db.session import SessionLocal
from app.models.audit import AuditEvent
from app.models.user import User

PASSWORD = "correct-horse-battery-staple"


def _audit_rows():
    db = SessionLocal()
    try:
        return db.query(AuditEvent).order_by(AuditEvent.created_at).all()
    finally:
        db.close()


def _events(rows, name):
    return [r for r in rows if r.event_name == name]


def test_register_success_and_duplicate_failure_recorded(client):
    r1 = client.post("/api/v1/auth/register", json={"email": "aud1@example.com", "password": PASSWORD})
    assert r1.status_code == 201
    user_id = r1.json()["id"]
    r2 = client.post("/api/v1/auth/register", json={"email": "aud1@example.com", "password": PASSWORD})
    assert r2.status_code == 409

    rows = _audit_rows()
    success = _events(rows, "auth.register.success")
    failure = _events(rows, "auth.register.failure")
    assert len(success) == 1 and success[0].actor_user_id == user_id
    assert len(failure) == 1 and failure[0].reason_code == "EMAIL_ALREADY_REGISTERED"
    assert failure[0].actor_user_id is None


def test_login_success_and_failure_reasons_recorded(client):
    client.post("/api/v1/auth/register", json={"email": "aud2@example.com", "password": PASSWORD})
    ok = client.post("/api/v1/auth/login", json={"email": "aud2@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    bad_pw = client.post("/api/v1/auth/login", json={"email": "aud2@example.com", "password": "wrong-password"})
    assert bad_pw.status_code == 401
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert unknown.status_code == 401

    rows = _audit_rows()
    assert len(_events(rows, "auth.login.success")) == 1
    failures = _events(rows, "auth.login.failure")
    reasons = {r.reason_code for r in failures}
    assert reasons == {"INVALID_PASSWORD", "ACCOUNT_NOT_FOUND"}
    invalid_password_row = next(r for r in failures if r.reason_code == "INVALID_PASSWORD")
    not_found_row = next(r for r in failures if r.reason_code == "ACCOUNT_NOT_FOUND")
    assert invalid_password_row.target_user_id is not None
    assert not_found_row.target_user_id is None


def test_inactive_login_records_account_inactive_reason(client):
    r = client.post("/api/v1/auth/register", json={"email": "aud3@example.com", "password": PASSWORD})
    user_id = r.json()["id"]
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        user.is_active = False
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/v1/auth/login", json={"email": "aud3@example.com", "password": PASSWORD})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    rows = _events(_audit_rows(), "auth.login.failure")
    inactive_row = next(r for r in rows if r.reason_code == "ACCOUNT_INACTIVE")
    assert inactive_row.target_user_id == user_id


def test_refresh_success_reuse_and_generic_failure_recorded(client):
    client.post("/api/v1/auth/register", json={"email": "aud4@example.com", "password": PASSWORD})
    tokens = client.post("/api/v1/auth/login", json={"email": "aud4@example.com", "password": PASSWORD}).json()

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert rotated.status_code == 200

    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401

    unknown = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert unknown.status_code == 401

    rows = _audit_rows()
    assert len(_events(rows, "auth.refresh.success")) == 1
    reuse_rows = _events(rows, "auth.refresh_token.reuse_detected")
    assert len(reuse_rows) == 1
    assert reuse_rows[0].outcome == "denied"
    generic_failures = _events(rows, "auth.refresh.failure")
    assert any(r.reason_code == "TOKEN_NOT_FOUND" for r in generic_failures)


def test_logout_and_logout_all_recorded(client):
    client.post("/api/v1/auth/register", json={"email": "aud5@example.com", "password": PASSWORD})
    tokens_a = client.post("/api/v1/auth/login", json={"email": "aud5@example.com", "password": PASSWORD}).json()
    tokens_b = client.post("/api/v1/auth/login", json={"email": "aud5@example.com", "password": PASSWORD}).json()

    logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {tokens_a['refresh_token']}"})
    assert logout_resp.status_code == 204

    logout_all_resp = client.post("/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {tokens_b['access_token']}"})
    assert logout_all_resp.status_code == 200
    assert logout_all_resp.json()["revoked_count"] == 1

    rows = _audit_rows()
    assert len(_events(rows, "auth.logout")) == 1
    logout_all_rows = _events(rows, "auth.logout_all")
    assert len(logout_all_rows) == 1
    assert logout_all_rows[0].event_metadata == {"revoked_count": 1}


def test_no_secrets_appear_in_any_audit_row(client):
    client.post("/api/v1/auth/register", json={"email": "aud6@example.com", "password": PASSWORD})
    tokens = client.post("/api/v1/auth/login", json={"email": "aud6@example.com", "password": PASSWORD}).json()
    client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})

    rows = _audit_rows()
    secrets = [PASSWORD, tokens["access_token"], tokens["refresh_token"]]
    assert rows
    for row in rows:
        pieces = [row.event_name, row.reason_code, row.resource_type, row.resource_id, row.request_id, row.ip_address, row.user_agent]
        blob = " ".join(str(p) for p in pieces if p is not None) + " " + str(row.event_metadata)
        for secret in secrets:
            assert secret not in blob
