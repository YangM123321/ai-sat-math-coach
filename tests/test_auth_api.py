"""API-level tests for Phase 1.5 PR 3 authentication endpoints.

Register requires the shared API key (not exercised in most tests here
since REQUIRE_API_KEY defaults to false, matching every other endpoint's
test convention in this suite -- see tests/test_api_key_protection.py
for the dedicated API-key-requirement coverage). Login/refresh/logout
require no API key at all (see API_KEY_EXEMPT_V1_PATHS in that file).
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.models.user import RefreshToken, User

EMAIL = "student@example.com"
PASSWORD = "correct-horse-battery-staple"


def register(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def register_and_login(client, email=EMAIL, password=PASSWORD):
    register(client, email, password)
    return login(client, email, password).json()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# --- register -----------------------------------------------------------

def test_register_creates_least_privileged_user(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "student"
    assert body["is_active"] is True
    assert body["is_email_verified"] is False
    assert "password_hash" not in body


def test_register_rejects_caller_supplied_role(client):
    r = client.post("/api/v1/auth/register", json={"email": "attempt@example.com", "password": PASSWORD, "role": "admin"})
    assert r.status_code == 422


def test_register_rejects_duplicate_email(client):
    register(client)
    r = register(client)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_register_normalizes_email_for_duplicate_check(client):
    register(client, email="Student@Example.com")
    r = register(client, email="  student@EXAMPLE.com  ")
    assert r.status_code == 409


def test_register_rejects_short_password(client):
    r = client.post("/api/v1/auth/register", json={"email": "short@example.com", "password": "short"})
    assert r.status_code == 422


def test_register_rejects_malformed_email(client):
    r = client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": PASSWORD})
    assert r.status_code == 422


# --- login ----------------------------------------------------------------

def test_login_succeeds_and_returns_tokens(client):
    register(client)
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["access_token"]
    assert body["refresh_token"]
    assert "password_hash" not in body
    assert "token_hash" not in body


def test_login_rejects_wrong_password(client):
    register(client)
    r = login(client, password="wrong-password")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_rejects_nonexistent_email(client):
    r = login(client, email="nobody@example.com")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_rejects_disabled_account(client, db):
    register(client)
    user = db.query(User).filter(User.email == EMAIL).one()
    user.is_active = False
    db.commit()

    r = login(client)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_error_is_byte_identical_across_failure_reasons(client, db):
    register(client)
    wrong_password_body = login(client, password="wrong-password").json()
    nonexistent_body = login(client, email="nobody@example.com").json()

    user = db.query(User).filter(User.email == EMAIL).one()
    user.is_active = False
    db.commit()
    disabled_body = login(client).json()

    assert wrong_password_body == nonexistent_body == disabled_body


def test_login_normalizes_email_before_lookup(client):
    register(client, email="student@example.com")
    r = login(client, email="  Student@EXAMPLE.com  ")
    assert r.status_code == 200


# --- refresh ----------------------------------------------------------------

def test_refresh_rotates_tokens(client):
    tokens = register_and_login(client)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    rotated = r.json()
    assert rotated["access_token"] != tokens["access_token"]
    assert rotated["refresh_token"] != tokens["refresh_token"]


def test_refresh_old_token_fails_after_rotation(client):
    tokens = register_and_login(client)
    client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


def test_refresh_reuse_of_rotated_token_revokes_all_sessions(client):
    session_a = register_and_login(client)
    session_b = login(client).json()

    # Rotate session A once (this is the legitimate use of that token).
    client.post("/api/v1/auth/refresh", json={"refresh_token": session_a["refresh_token"]})

    # Replaying the now-superseded session-A token is reuse of a rotated
    # token -- must be rejected AND must revoke every active session for
    # this user, including session B's still-otherwise-valid token.
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": session_a["refresh_token"]})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    session_b_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": session_b["refresh_token"]})
    assert session_b_refresh.status_code == 401
    assert session_b_refresh.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


def test_refresh_rejects_unknown_token(client):
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


def test_refresh_rejects_expired_token_without_mass_revocation(client, db):
    session_a = register_and_login(client)
    session_b = login(client).json()

    row = db.query(RefreshToken).filter(RefreshToken.user_id == db.query(User).filter(User.email == EMAIL).one().id).order_by(RefreshToken.created_at).first()
    # Simulate a token issued a while ago that has since expired, without
    # violating the schema's ck_refresh_tokens_expires_after_created
    # CHECK constraint (expires_at must stay strictly after created_at).
    row.created_at = datetime.now(timezone.utc) - timedelta(days=40)
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": session_a["refresh_token"]})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    # Plain expiry (not reuse-of-rotated) must NOT trigger mass revocation.
    still_good = client.post("/api/v1/auth/refresh", json={"refresh_token": session_b["refresh_token"]})
    assert still_good.status_code == 200


def test_refresh_rejects_token_of_disabled_user(client, db):
    tokens = register_and_login(client)
    user = db.query(User).filter(User.email == EMAIL).one()
    user.is_active = False
    db.commit()

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


# --- logout (Bearer refresh token, no request body) ------------------------

def test_logout_revokes_specific_session_only(client):
    session_a = register_and_login(client)
    session_b = login(client).json()

    r = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {session_a['refresh_token']}"})
    assert r.status_code == 204

    a_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": session_a["refresh_token"]})
    assert a_refresh.status_code == 401

    b_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": session_b["refresh_token"]})
    assert b_refresh.status_code == 200


def test_logout_is_idempotent(client):
    tokens = register_and_login(client)
    first = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    second = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert first.status_code == 204
    assert second.status_code == 204


def test_logout_with_unknown_token_is_a_silent_no_op(client):
    r = client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 204


def test_logout_without_credential_is_rejected(client):
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


# --- logout-all (Bearer access token) ---------------------------------------

def test_logout_all_revokes_every_session(client):
    session_a = register_and_login(client)
    session_b = login(client).json()

    r = client.post("/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {session_a['access_token']}"})
    assert r.status_code == 200
    assert r.json()["revoked_count"] == 2

    for tokens in (session_a, session_b):
        refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert refreshed.status_code == 401


def test_logout_all_without_access_token_is_rejected(client):
    r = client.post("/api/v1/auth/logout-all")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_TOKEN"


def test_logout_all_rejects_malformed_access_token(client):
    r = client.post("/api/v1/auth/logout-all", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_TOKEN"


def test_logout_all_rejects_a_disabled_users_still_unexpired_token(client, db):
    tokens = register_and_login(client)
    user = db.query(User).filter(User.email == EMAIL).one()
    user.is_active = False
    db.commit()

    r = client.post("/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_TOKEN"


# --- no secrets leak into responses or logs --------------------------------

def test_no_password_or_hash_material_in_register_or_login_responses(client):
    register_body = register(client).json()
    login_body = login(client).json()
    for body in (register_body, login_body):
        assert "password" not in body
        assert "password_hash" not in body
        assert "token_hash" not in body


def test_no_password_or_tokens_appear_in_logs(client, caplog):
    with caplog.at_level("INFO"):
        register(client)
        tokens = login(client).json()
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert PASSWORD not in log_text
    assert tokens["access_token"] not in log_text
    assert tokens["refresh_token"] not in log_text
