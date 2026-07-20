"""Integration tests for general /api/v1/* rate limiting (Phase 1.5 PR 14).

Rate limiting defaults off (RATE_LIMIT_API_ENABLED=false) -- the rest of
the suite exercises every domain route with no awareness of this control
at all, which is itself a regression test for "opt-in only" (mirrors
tests/test_rate_limiting_auth_api.py's own framing for PR6). Every test
in this file that needs PR14 active explicitly opts in via one of the two
fixtures below, and every fixture resets only get_api_rate_limiter() --
never get_rate_limiter() (PR6's own, separate instance) -- per the
approved architecture review's PR6/PR14 capacity-isolation decision (§11).
"""

import os

import pytest

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app, protected_api_router
from app.models.audit import AuditEvent
from app.api.dependencies import (
    rate_limit_api_admin,
    rate_limit_api_expensive,
    rate_limit_api_read,
    rate_limit_api_write,
)
from app.services.rate_limiter_service import get_api_rate_limiter
from tests.auth_test_helpers import auth_headers, register_and_login

SECURITY_HEADER_NAMES = (
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
)


def _apply_env(overrides: dict) -> dict:
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    get_settings.cache_clear()
    return previous


def _restore_env(previous: dict) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture
def enable_api_category_rate_limiting():
    """Tight authenticated category tiers, a generous perimeter tier --
    isolates read/write/expensive/administrative tier behavior from the
    perimeter tier."""
    overrides = {
        "RATE_LIMIT_API_ENABLED": "true",
        "RATE_LIMIT_API_PERIMETER_MAX_ATTEMPTS": "1000",
        "RATE_LIMIT_API_PERIMETER_WINDOW_SECONDS": "300",
        "RATE_LIMIT_API_READ_MAX_ATTEMPTS": "3",
        "RATE_LIMIT_API_READ_WINDOW_SECONDS": "300",
        "RATE_LIMIT_API_WRITE_MAX_ATTEMPTS": "3",
        "RATE_LIMIT_API_WRITE_WINDOW_SECONDS": "300",
        "RATE_LIMIT_API_EXPENSIVE_MAX_ATTEMPTS": "3",
        "RATE_LIMIT_API_EXPENSIVE_WINDOW_SECONDS": "300",
        "RATE_LIMIT_API_ADMIN_MAX_ATTEMPTS": "3",
        "RATE_LIMIT_API_ADMIN_WINDOW_SECONDS": "300",
        "RATE_LIMIT_MAX_STORED_KEYS": "1000",
    }
    previous = _apply_env(overrides)
    get_api_rate_limiter().reset()
    try:
        yield
    finally:
        _restore_env(previous)
        get_api_rate_limiter().reset()


@pytest.fixture
def enable_api_perimeter_rate_limiting():
    """A tight perimeter tier, generous authenticated category tiers --
    isolates the perimeter tier specifically."""
    overrides = {
        "RATE_LIMIT_API_ENABLED": "true",
        "RATE_LIMIT_API_PERIMETER_MAX_ATTEMPTS": "3",
        "RATE_LIMIT_API_PERIMETER_WINDOW_SECONDS": "300",
        "RATE_LIMIT_API_READ_MAX_ATTEMPTS": "1000",
        "RATE_LIMIT_API_READ_WINDOW_SECONDS": "300",
        "RATE_LIMIT_API_WRITE_MAX_ATTEMPTS": "1000",
        "RATE_LIMIT_API_WRITE_WINDOW_SECONDS": "300",
        "RATE_LIMIT_API_EXPENSIVE_MAX_ATTEMPTS": "1000",
        "RATE_LIMIT_API_EXPENSIVE_WINDOW_SECONDS": "300",
        "RATE_LIMIT_API_ADMIN_MAX_ATTEMPTS": "1000",
        "RATE_LIMIT_API_ADMIN_WINDOW_SECONDS": "300",
        "RATE_LIMIT_MAX_STORED_KEYS": "1000",
    }
    previous = _apply_env(overrides)
    get_api_rate_limiter().reset()
    try:
        yield
    finally:
        _restore_env(previous)
        get_api_rate_limiter().reset()


def _audit_rows(event_name):
    db = SessionLocal()
    try:
        return db.query(AuditEvent).filter(AuditEvent.event_name == event_name).all()
    finally:
        db.close()


@pytest.fixture
def admin(client):
    _, token = register_and_login(client, "pr14-admin@example.com", role="admin")
    return auth_headers(token)


@pytest.fixture
def student(client):
    student_id, token = register_and_login(client, "pr14-student@example.com")
    return student_id, auth_headers(token)


def seed_skill(client, headers, code="pr14_skill"):
    r = client.post(
        "/api/v1/skills",
        json={
            "code": code,
            "name": "PR14 Skill",
            "domain": "algebra",
            "description": "d",
            "parent_code": None,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text


# --- Disabled by default -----------------------------------------------------


def test_api_rate_limiting_disabled_by_default(client, student):
    _, headers = student
    for _ in range(20):
        r = client.get("/api/v1/skills", headers=headers)
        assert r.status_code == 200


# --- Independence from PR6's own flag ---------------------------------------


def test_pr14_disabled_never_429s_even_with_pr6_enabled(client, student):
    """Enabling PR6's rate_limit_enabled must not turn on any PR14 tier."""
    previous = _apply_env(
        {
            "RATE_LIMIT_ENABLED": "true",
            "RATE_LIMIT_AUTH_IP_MAX_ATTEMPTS": "2",
            "RATE_LIMIT_AUTH_IP_WINDOW_SECONDS": "300",
        }
    )
    try:
        _, headers = student
        for _ in range(20):
            r = client.get("/api/v1/skills", headers=headers)
            assert r.status_code == 200
    finally:
        _restore_env(previous)


def test_pr6_untouched_when_only_pr14_enabled(client):
    """Enabling PR14 must not turn on PR6's own authentication tiers --
    login remains unthrottled (rate_limit_enabled stays false)."""
    previous = _apply_env(
        {
            "RATE_LIMIT_API_ENABLED": "true",
            "RATE_LIMIT_API_PERIMETER_MAX_ATTEMPTS": "1000",
            "RATE_LIMIT_API_PERIMETER_WINDOW_SECONDS": "300",
        }
    )
    try:
        for i in range(10):
            r = client.post(
                "/api/v1/auth/login",
                json={"email": f"pr6-untouched-{i}@example.com", "password": "x"},
            )
            assert r.status_code == 401
    finally:
        _restore_env(previous)


# --- Perimeter tier -----------------------------------------------------------


def test_perimeter_tier_blocks_after_max_attempts(
    client, student, enable_api_perimeter_rate_limiting
):
    _, headers = student
    for _ in range(3):
        r = client.get("/api/v1/skills", headers=headers)
        assert r.status_code == 200
    blocked = client.get("/api/v1/skills", headers=headers)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


def test_perimeter_tier_is_consumed_even_by_unauthenticated_requests(
    client, enable_api_perimeter_rate_limiting
):
    """The perimeter tier runs before require_api_key/get_current_user --
    it must still be consumed (and eventually trip) by requests that will
    ultimately fail authentication."""
    for _ in range(3):
        r = client.get("/api/v1/skills")
        assert r.status_code == 401
    blocked = client.get("/api/v1/skills")
    assert blocked.status_code == 429


def test_perimeter_and_category_buckets_are_both_consumed(client, student):
    """Option A (architecture review §13): every protected_api_router
    request consumes both its perimeter bucket and its category bucket.
    A tight perimeter denies a request even though the category tier
    alone would still have allowed it."""
    _, headers = student
    previous = _apply_env(
        {
            "RATE_LIMIT_API_ENABLED": "true",
            "RATE_LIMIT_API_PERIMETER_MAX_ATTEMPTS": "1",
            "RATE_LIMIT_API_PERIMETER_WINDOW_SECONDS": "300",
            "RATE_LIMIT_API_READ_MAX_ATTEMPTS": "1000",
            "RATE_LIMIT_API_READ_WINDOW_SECONDS": "300",
            "RATE_LIMIT_MAX_STORED_KEYS": "1000",
        }
    )
    get_api_rate_limiter().reset()
    try:
        first = client.get("/api/v1/skills", headers=headers)
        assert first.status_code == 200
        second = client.get("/api/v1/skills", headers=headers)
        assert (
            second.status_code == 429
        )  # perimeter tripped, not the (generous) read tier
    finally:
        _restore_env(previous)
        get_api_rate_limiter().reset()


def test_perimeter_denial_short_circuits_the_category_dependency_and_route_body(
    client, admin
):
    """A perimeter denial must raise before FastAPI ever resolves the
    route's own category dependency or runs the route body -- proven
    here by a route with an observable side effect (creating a skill
    row). If the category dependency or route body ran anyway, either
    the second skill would exist, or a RATE_LIMIT_ADMIN audit row (which
    only the category dependency's own _raise_if_denied call can write)
    would exist."""
    previous = _apply_env(
        {
            "RATE_LIMIT_API_ENABLED": "true",
            "RATE_LIMIT_API_PERIMETER_MAX_ATTEMPTS": "1",
            "RATE_LIMIT_API_PERIMETER_WINDOW_SECONDS": "300",
            "RATE_LIMIT_API_ADMIN_MAX_ATTEMPTS": "1000",
            "RATE_LIMIT_API_ADMIN_WINDOW_SECONDS": "300",
            "RATE_LIMIT_MAX_STORED_KEYS": "1000",
        }
    )
    get_api_rate_limiter().reset()
    try:
        first = client.post(
            "/api/v1/skills",
            json={
                "code": "perimeter_short_circuit_1",
                "name": "First Skill",
                "domain": "algebra",
                "description": "d",
                "parent_code": None,
            },
            headers=admin,
        )
        assert first.status_code == 201

        second = client.post(
            "/api/v1/skills",
            json={
                "code": "perimeter_short_circuit_2",
                "name": "Second Skill",
                "domain": "algebra",
                "description": "d",
                "parent_code": None,
            },
            headers=admin,
        )
        assert second.status_code == 429

        rows = _audit_rows("api.rate_limited")
        assert not any(row.reason_code == "RATE_LIMIT_ADMIN" for row in rows)
        assert any(row.reason_code == "RATE_LIMIT_PERIMETER" for row in rows)

        from app.models.knowledge import Skill

        db = SessionLocal()
        try:
            assert (
                db.query(Skill)
                .filter(Skill.code == "perimeter_short_circuit_2")
                .first()
                is None
            )
        finally:
            db.close()
    finally:
        _restore_env(previous)
        get_api_rate_limiter().reset()


# --- Authenticated category tiers --------------------------------------------


def test_read_tier_blocks_after_max_attempts(
    client, student, enable_api_category_rate_limiting
):
    _, headers = student
    for _ in range(3):
        r = client.get("/api/v1/skills", headers=headers)
        assert r.status_code == 200
    blocked = client.get("/api/v1/skills", headers=headers)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"

    rows = _audit_rows("api.rate_limited")
    assert any(
        row.reason_code == "RATE_LIMIT_READ" and row.category == "authorization"
        for row in rows
    )


def test_write_tier_blocks_after_max_attempts(
    client, admin, student, enable_api_category_rate_limiting
):
    sid, headers = student
    seed_skill(client, admin)
    for i in range(3):
        r = client.post(
            "/api/v1/mastery/evidence",
            json={
                "student_id": sid,
                "skill_code": "pr14_skill",
                "evidence_type": "diagnostic_attempt",
                "source_id": f"src-{i}",
                "is_correct": False,
                "error_category": "procedural_error",
                "difficulty": "medium",
                "diagnostic_confidence": 0.9,
                "occurred_at": "2026-01-01T00:00:00Z",
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text
    blocked = client.post(
        "/api/v1/mastery/evidence",
        json={
            "student_id": sid,
            "skill_code": "pr14_skill",
            "evidence_type": "diagnostic_attempt",
            "source_id": "src-blocked",
            "is_correct": False,
            "error_category": "procedural_error",
            "difficulty": "medium",
            "diagnostic_confidence": 0.9,
            "occurred_at": "2026-01-01T00:00:00Z",
        },
        headers=headers,
    )
    assert blocked.status_code == 429

    rows = _audit_rows("api.rate_limited")
    assert any(row.reason_code == "RATE_LIMIT_WRITE" for row in rows)


def test_expensive_tier_blocks_after_max_attempts(
    client, admin, student, enable_api_category_rate_limiting
):
    sid, headers = student
    seed_skill(client, admin)

    def create_session():
        return client.post(
            "/api/v1/tutor/sessions",
            json={
                "student_id": sid,
                "skill_code": "pr14_skill",
                "problem_text": "2x=4, x=?",
            },
            headers=headers,
        )

    for _ in range(3):
        r = create_session()
        assert r.status_code == 201, r.text
    blocked = create_session()
    assert blocked.status_code == 429

    rows = _audit_rows("api.rate_limited")
    assert any(row.reason_code == "RATE_LIMIT_EXPENSIVE" for row in rows)


def test_admin_tier_blocks_after_max_attempts(
    client, admin, enable_api_category_rate_limiting
):
    def create_skill(i):
        return client.post(
            "/api/v1/skills",
            json={
                "code": f"admin_tier_{i}",
                "name": "Admin Tier Skill",
                "domain": "algebra",
                "description": "d",
                "parent_code": None,
            },
            headers=admin,
        )

    for i in range(3):
        r = create_skill(i)
        assert r.status_code == 201, r.text
    blocked = create_skill("blocked")
    assert blocked.status_code == 429

    rows = _audit_rows("api.rate_limited")
    assert any(row.reason_code == "RATE_LIMIT_ADMIN" for row in rows)


# --- Identity isolation -------------------------------------------------------


def test_two_users_never_share_an_authenticated_bucket(
    client, enable_api_category_rate_limiting
):
    _, token_a = register_and_login(client, "pr14-iso-user-a@example.com")
    _, token_b = register_and_login(client, "pr14-iso-user-b@example.com")
    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    for _ in range(3):
        assert client.get("/api/v1/skills", headers=headers_a).status_code == 200
    assert client.get("/api/v1/skills", headers=headers_a).status_code == 429

    # A different user, same TestClient (same underlying "IP"), is
    # unaffected -- their authenticated read bucket is entirely separate.
    assert client.get("/api/v1/skills", headers=headers_b).status_code == 200


def test_teacher_spanning_multiple_students_is_limited_once_holistically(
    client, admin, enable_api_category_rate_limiting
):
    """Keying on the caller's own user.id (never a path-supplied
    student_id) means a teacher with grants across many students is
    bounded once, holistically, by their own account -- not per student
    (architecture review §6)."""
    student_1, _ = register_and_login(client, "pr14-teacher-student-1@example.com")
    student_2, _ = register_and_login(client, "pr14-teacher-student-2@example.com")
    teacher_id, teacher_token = register_and_login(
        client, "pr14-teacher@example.com", role="teacher"
    )
    teacher_headers = auth_headers(teacher_token)

    seed_skill(client, admin)
    for sid in (student_1, student_2):
        evidence = client.post(
            "/api/v1/mastery/evidence",
            json={
                "student_id": sid,
                "skill_code": "pr14_skill",
                "evidence_type": "diagnostic_attempt",
                "source_id": f"seed-{sid}",
                "is_correct": False,
                "error_category": "procedural_error",
                "difficulty": "medium",
                "diagnostic_confidence": 0.9,
                "occurred_at": "2026-01-01T00:00:00Z",
            },
            headers=admin,
        )
        assert evidence.status_code == 201, evidence.text
        grant = client.post(
            "/api/v1/dashboard/access-grants",
            json={"viewer_id": teacher_id, "student_id": sid, "role": "teacher"},
            headers=admin,
        )
        assert grant.status_code == 201

    targets = [student_1, student_2, student_1]
    for sid in targets:
        r = client.get(f"/api/v1/dashboard/students/{sid}", headers=teacher_headers)
        assert r.status_code == 200

    blocked = client.get(
        f"/api/v1/dashboard/students/{student_2}", headers=teacher_headers
    )
    assert blocked.status_code == 429


# --- Exemptions ----------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["/health", "/ready", "/docs", "/redoc", "/openapi.json"]
)
def test_exempt_paths_never_429(client, path, enable_api_perimeter_rate_limiting):
    for _ in range(10):
        r = client.get(path)
        assert r.status_code != 429


def test_auth_routes_never_consume_pr14_buckets(
    client, enable_api_perimeter_rate_limiting
):
    """auth_router is never wrapped by protected_api_router -- register/
    login/refresh/logout/logout-all must never receive a PR14 429,
    however tight the PR14 perimeter tier is configured."""
    for i in range(10):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": f"never-pr14-{i}@example.com", "password": "x"},
        )
        assert r.status_code == 401


# --- Response contract: headers, request id, envelope -----------------------


def test_pr14_429_preserves_security_headers_and_request_id(
    client, student, enable_api_perimeter_rate_limiting
):
    _, headers = student
    for _ in range(3):
        client.get("/api/v1/skills", headers=headers)
    blocked = client.get("/api/v1/skills", headers=headers)
    assert blocked.status_code == 429
    for name in SECURITY_HEADER_NAMES:
        assert name in blocked.headers
    assert "x-request-id" in blocked.headers


def test_pr14_429_includes_standard_rate_limit_headers(
    client, student, enable_api_perimeter_rate_limiting
):
    _, headers = student
    for _ in range(3):
        client.get("/api/v1/skills", headers=headers)
    blocked = client.get("/api/v1/skills", headers=headers)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) > 0
    assert blocked.headers["X-RateLimit-Limit"] == "3"
    assert blocked.headers["X-RateLimit-Remaining"] == "0"
    assert int(blocked.headers["X-RateLimit-Reset"]) > 0


def test_pr14_429_body_matches_the_existing_error_envelope(
    client, student, enable_api_perimeter_rate_limiting
):
    _, headers = student
    for _ in range(3):
        client.get("/api/v1/skills", headers=headers)
    blocked = client.get("/api/v1/skills", headers=headers)
    body = blocked.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["details"] is None


# --- Future-route safety net (architecture review §16, Option C) ------------


def _iter_effective_protected_routes():
    """Yields (methods, path, dependencies) for every route reachable
    through protected_api_router, with dependencies merged across every
    router level (protected_api_router's own + each domain router's own
    + each individual route's own).

    FastAPI 0.119+ (this repo's installed version) resolves
    include_router() lazily through a private _IncludedRouter /
    _EffectiveRouteContext mechanism instead of eagerly flattening
    sub-router routes into APIRouter.routes at include_router() call
    time -- so protected_api_router.routes holds opaque _IncludedRouter
    wrappers, not APIRoute objects, and the fully-merged per-route
    dependency list only exists on the *effective* context. Falls back
    to a direct APIRoute.dependencies walk for any FastAPI version where
    this private mechanism doesn't exist.
    """
    try:
        from fastapi.routing import _EffectiveRouteContext, _IncludedRouter
    except ImportError:
        from fastapi.routing import APIRoute

        for route in protected_api_router.routes:
            if isinstance(route, APIRoute):
                yield route.methods, route.path, route.dependencies
        return

    target = None
    for item in app.routes:
        if (
            isinstance(item, _IncludedRouter)
            and item.original_router is protected_api_router
        ):
            target = item
            break
    assert (
        target is not None
    ), "protected_api_router is not included on app -- route introspection is broken"

    stack = [target]
    while stack:
        item = stack.pop()
        if isinstance(item, _IncludedRouter):
            stack.extend(item.effective_candidates())
        elif isinstance(item, _EffectiveRouteContext):
            yield item.methods, item.path, item.dependencies


def test_every_protected_route_has_exactly_one_category_rate_limit_dependency():
    """Guards against a future PR adding a route to any domain router
    without attaching exactly one authenticated category dependency
    (read/write/expensive/administrative) -- not zero, not more than one.
    Mirrors tests/test_api_key_protection.py's existing structural-test
    precedent for a different invariant."""
    category_dependencies = {
        rate_limit_api_read,
        rate_limit_api_write,
        rate_limit_api_expensive,
        rate_limit_api_admin,
    }
    offending = []
    checked = 0
    for methods, path, dependencies in _iter_effective_protected_routes():
        matched = [
            d.dependency for d in dependencies if d.dependency in category_dependencies
        ]
        checked += 1
        if len(matched) != 1:
            offending.append((sorted(methods), path, len(matched)))

    assert checked == 32, f"expected 32 protected_api_router routes, found {checked}"
    assert (
        not offending
    ), f"routes without exactly one PR14 category dependency: {offending}"
