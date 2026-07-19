"""Integration tests for rate limiting on /api/v1/auth/* (Phase 1.5 PR 6).

Rate limiting defaults off (RATE_LIMIT_ENABLED=false) -- the rest of the
suite exercises the auth endpoints hundreds of times with no awareness
of rate limiting at all, which is itself a regression test for "opt-in
only." Every test in this file explicitly opts in via enable_rate_limiting.
"""
import os

import pytest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.audit import AuditEvent
from app.services.rate_limiter_service import get_rate_limiter

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def enable_rate_limiting():
    """Mirrors tests/test_api_key_protection.py's enable_api_key fixture:
    low, test-friendly limits for the duration of the test, restoring
    prior env and limiter state after."""
    overrides = {
        "RATE_LIMIT_ENABLED": "true",
        "RATE_LIMIT_LOGIN_IP_MAX_ATTEMPTS": "3",
        "RATE_LIMIT_LOGIN_IP_WINDOW_SECONDS": "300",
        "RATE_LIMIT_LOGIN_ACCOUNT_MAX_ATTEMPTS": "2",
        "RATE_LIMIT_LOGIN_ACCOUNT_WINDOW_SECONDS": "300",
        "RATE_LIMIT_AUTH_IP_MAX_ATTEMPTS": "3",
        "RATE_LIMIT_AUTH_IP_WINDOW_SECONDS": "300",
    }
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    get_settings.cache_clear()
    get_rate_limiter().reset()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        get_rate_limiter().reset()


def _audit_rows(event_name):
    db = SessionLocal()
    try:
        return db.query(AuditEvent).filter(AuditEvent.event_name == event_name).all()
    finally:
        db.close()


def test_rate_limiting_disabled_by_default(client):
    """No fixture enabling it -- the default is off, so this must never 429."""
    for i in range(10):
        r = client.post("/api/v1/auth/login", json={"email": f"nobody{i}@example.com", "password": PASSWORD})
        assert r.status_code == 401


def test_login_ip_tier_blocks_after_max_attempts(client, enable_rate_limiting):
    # Distinct emails per call so the (tighter) account tier never trips
    # first -- isolates the IP tier specifically.
    for i in range(3):
        r = client.post("/api/v1/auth/login", json={"email": f"ip-tier-{i}@example.com", "password": PASSWORD})
        assert r.status_code == 401
    blocked = client.post("/api/v1/auth/login", json={"email": "ip-tier-3@example.com", "password": PASSWORD})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


def test_login_account_tier_blocks_before_ip_tier_for_one_target_email(client, enable_rate_limiting):
    # Same email every time -- the account tier (max 2) trips before the
    # IP tier (max 3) would.
    email = "account-tier@example.com"
    for _ in range(2):
        r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 401
    blocked = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert blocked.status_code == 429

    rows = _audit_rows("auth.login.rate_limited")
    assert any(row.reason_code == "RATE_LIMIT_ACCOUNT" for row in rows)


def test_account_tier_is_keyed_on_normalized_email(client, enable_rate_limiting):
    """Case/whitespace variants of the same address must share one counter
    -- otherwise an attacker trivially bypasses the account tier."""
    allowed_variants = ["variant@example.com", "  VARIANT@Example.com  "]
    for email in allowed_variants:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 401
    blocked = client.post("/api/v1/auth/login", json={"email": "Variant@example.com", "password": PASSWORD})
    assert blocked.status_code == 429


def test_register_shares_the_coarse_auth_ip_tier(client, enable_rate_limiting):
    for i in range(3):
        r = client.post("/api/v1/auth/register", json={"email": f"reg-ip-{i}@example.com", "password": PASSWORD})
        assert r.status_code == 201
    blocked = client.post("/api/v1/auth/register", json={"email": "reg-ip-3@example.com", "password": PASSWORD})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


def test_rate_limit_response_includes_standard_headers(client, enable_rate_limiting):
    for i in range(3):
        client.post("/api/v1/auth/login", json={"email": f"headers-{i}@example.com", "password": PASSWORD})
    blocked = client.post("/api/v1/auth/login", json={"email": "headers-3@example.com", "password": PASSWORD})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) > 0
    assert blocked.headers["X-RateLimit-Limit"] == "3"
    assert blocked.headers["X-RateLimit-Remaining"] == "0"
    assert int(blocked.headers["X-RateLimit-Reset"]) > 0


def test_rate_limit_denial_is_recorded_in_audit_trail(client, enable_rate_limiting):
    for i in range(3):
        client.post("/api/v1/auth/login", json={"email": f"audit-{i}@example.com", "password": PASSWORD})
    client.post("/api/v1/auth/login", json={"email": "audit-3@example.com", "password": PASSWORD})

    rows = _audit_rows("auth.login.rate_limited")
    assert any(row.reason_code == "RATE_LIMIT_IP" and row.outcome == "denied" for row in rows)


def test_rate_limit_error_body_does_not_reveal_which_tier_tripped(client, enable_rate_limiting):
    for i in range(3):
        client.post("/api/v1/auth/login", json={"email": f"generic-{i}@example.com", "password": PASSWORD})
    blocked = client.post("/api/v1/auth/login", json={"email": "generic-3@example.com", "password": PASSWORD})
    body = blocked.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["details"] is None
    assert "ip" not in body["error"]["message"].lower()
    assert "account" not in body["error"]["message"].lower()
