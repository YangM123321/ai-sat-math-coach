"""Tests for security response headers (Phase 1.5 PR 13).

Exercises SecurityHeadersMiddleware directly against throwaway FastAPI()
instances + hand-built Settings, not the shared app/client fixtures --
Starlette bakes middleware constructor args in at app.add_middleware()
call time (module-import time for the real app), so there is no way to
dynamically retoggle environment-specific behavior (HSTS) per test the
way the enable_api_key/enable_rate_limiting fixtures do for
dependency-based checks. Mirrors tests/test_security_middleware.py's
_build_app pattern (Phase 1.5 PR 7).
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.responses import PlainTextResponse

from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    Forbidden,
    InvalidToken,
    RateLimited,
    app_error_handler,
)
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security import configure_security_middleware
from app.middleware.security_headers import (
    CONTENT_SECURITY_POLICY,
    HSTS_VALUE,
    PERMISSIONS_POLICY,
    REFERRER_POLICY,
    SecurityHeadersMiddleware,
)

MANAGED_HEADERS = {
    "content-security-policy": CONTENT_SECURITY_POLICY,
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": REFERRER_POLICY,
    "permissions-policy": PERMISSIONS_POLICY,
}


class Body(BaseModel):
    required_field: str


def _build_app(**settings_overrides):
    settings = Settings(_env_file=None, **settings_overrides)
    app = FastAPI()
    configure_security_middleware(app, settings)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_exception_handler(AppError, app_error_handler)

    @app.get("/probe")
    def probe_get():
        return {"ok": True}

    @app.post("/probe")
    def probe_post(body: Body):
        return {"ok": True}

    @app.get("/http-exception")
    def http_exception_probe():
        raise HTTPException(status_code=404, detail="not found")

    @app.get("/forbidden")
    def forbidden_probe():
        raise Forbidden()

    @app.get("/unauthorized")
    def unauthorized_probe():
        raise InvalidToken()

    @app.get("/rate-limited")
    def rate_limited_probe():
        raise RateLimited(
            retry_after_seconds=30, limit=5, remaining=0, reset_seconds=30
        )

    @app.get("/set-cache-control")
    def set_cache_control_probe():
        return PlainTextResponse("ok", headers={"Cache-Control": "private, max-age=60"})

    @app.get("/set-referrer-policy")
    def set_referrer_policy_probe():
        return PlainTextResponse("ok", headers={"Referrer-Policy": "no-referrer"})

    @app.get("/set-permissions-policy")
    def set_permissions_policy_probe():
        return PlainTextResponse(
            "ok", headers={"Permissions-Policy": "geolocation=(self)"}
        )

    @app.get("/set-conflicting-invariants")
    def set_conflicting_invariants_probe():
        return PlainTextResponse(
            "ok",
            headers={
                "X-Frame-Options": "SAMEORIGIN",
                "Content-Security-Policy": "default-src *",
            },
        )

    @app.get("/api/v1/probe")
    def api_v1_probe():
        return {"ok": True}

    @app.get("/api/v1/set-cache-control")
    def api_v1_set_cache_control_probe():
        return PlainTextResponse("ok", headers={"Cache-Control": "private, max-age=60"})

    @app.get("/unhandled")
    def unhandled_probe():
        raise RuntimeError("a genuine bug, not an AppError")

    @app.get("/health")
    def health_probe():
        return {"status": "ok"}

    @app.get("/ready")
    def ready_probe():
        return {"status": "ready"}

    return app


# --- Exact header values on a successful response -------------------------


def test_all_unconditional_headers_present_with_exact_values_on_success():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/probe")
    assert r.status_code == 200
    for name, value in MANAGED_HEADERS.items():
        assert r.headers[name] == value


def test_cache_control_not_forced_outside_api_v1():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/probe")
    assert "cache-control" not in r.headers


def test_cache_control_no_store_on_api_v1_path():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/api/v1/probe")
    assert r.headers["cache-control"] == "no-store"


# --- Coverage on handled error/response classes ----------------------------


def test_headers_present_on_fastapi_validation_error_response():
    app = _build_app()
    client = TestClient(app)
    r = client.post("/probe", json={})
    assert r.status_code == 422
    for name, value in MANAGED_HEADERS.items():
        assert r.headers[name] == value


def test_headers_present_on_http_exception_response():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/http-exception")
    assert r.status_code == 404
    for name, value in MANAGED_HEADERS.items():
        assert r.headers[name] == value


def test_headers_present_on_forbidden_apperror_response():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/forbidden")
    assert r.status_code == 403
    for name, value in MANAGED_HEADERS.items():
        assert r.headers[name] == value


def test_headers_present_on_unauthorized_apperror_response():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/unauthorized")
    assert r.status_code == 401
    for name, value in MANAGED_HEADERS.items():
        assert r.headers[name] == value


def test_headers_present_on_rate_limited_response():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/rate-limited")
    assert r.status_code == 429
    for name, value in MANAGED_HEADERS.items():
        assert r.headers[name] == value
    # RateLimited's own headers must survive alongside the new ones --
    # additional non-regression evidence, not the sole precedence proof.
    assert r.headers["retry-after"] == "30"


def test_headers_present_on_trusted_host_rejection_response():
    app = _build_app(trusted_hosts=["allowed.example.com"])
    client = TestClient(app, base_url="http://evil.example.com")
    r = client.get("/probe")
    assert r.status_code == 400
    for name, value in MANAGED_HEADERS.items():
        assert r.headers[name] == value


def test_headers_present_on_cors_preflight_rejection_response():
    app = _build_app(cors_allowed_origins=["https://allowed.example.com"])
    client = TestClient(app)
    r = client.options(
        "/probe",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 400
    for name, value in MANAGED_HEADERS.items():
        assert r.headers[name] == value


# --- HSTS: environment-conditional ----------------------------------------


@pytest.mark.parametrize("environment", ["development", "test", "staging"])
def test_hsts_absent_outside_production(environment):
    app = _build_app(environment=environment)
    client = TestClient(app)
    r = client.get("/probe")
    assert "strict-transport-security" not in r.headers


def test_hsts_present_with_exact_value_in_production():
    app = _build_app(
        environment="production",
        secret_key="a" * 40,
        database_url="postgresql+psycopg://user:pass@host:5432/db?sslmode=require",
        cors_allowed_origins=["https://allowed.example.com"],
        trusted_hosts=["allowed.example.com"],
        rate_limit_enabled=True,
        rate_limit_api_enabled=True,
    )
    client = TestClient(app, base_url="http://allowed.example.com")
    r = client.get("/probe")
    assert r.headers["strict-transport-security"] == HSTS_VALUE


# --- CSP: documentation-route exemption, derived dynamically --------------


def test_csp_absent_on_dynamically_obtained_docs_url():
    app = _build_app()
    client = TestClient(app)
    assert app.docs_url is not None
    r = client.get(app.docs_url)
    assert "content-security-policy" not in r.headers


def test_csp_absent_on_dynamically_obtained_redoc_url():
    app = _build_app()
    client = TestClient(app)
    assert app.redoc_url is not None
    r = client.get(app.redoc_url)
    assert "content-security-policy" not in r.headers


def test_csp_present_on_openapi_url():
    app = _build_app()
    client = TestClient(app)
    assert app.openapi_url is not None
    r = client.get(app.openapi_url)
    assert r.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


def test_swagger_ui_still_reachable():
    app = _build_app()
    client = TestClient(app)
    r = client.get(app.docs_url)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_redoc_still_reachable():
    app = _build_app()
    client = TestClient(app)
    r = client.get(app.redoc_url)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_openapi_json_still_reachable_and_valid():
    app = _build_app()
    client = TestClient(app)
    r = client.get(app.openapi_url)
    assert r.status_code == 200
    body = r.json()
    assert "openapi" in body
    assert "paths" in body


# --- Cache-Control: route scope --------------------------------------------


@pytest.mark.parametrize("path", ["/health", "/ready"])
def test_cache_control_absent_from_health_and_ready(path):
    app = _build_app()
    client = TestClient(app)
    r = client.get(path)
    assert "cache-control" not in r.headers


def test_cache_control_absent_from_docs_redoc_and_openapi():
    app = _build_app()
    client = TestClient(app)
    for path in (app.docs_url, app.redoc_url, app.openapi_url):
        r = client.get(path)
        assert "cache-control" not in r.headers


# --- Precedence: safe defaults preserve an explicit route value -----------


def test_route_defined_cache_control_is_preserved():
    app = _build_app()
    client = TestClient(app)
    # This probe route lives outside /api/v1/, so its own explicit
    # Cache-Control value is what setdefault preserves -- the /api/v1/
    # prefix rule plays no part in this assertion.
    r = client.get("/set-cache-control")
    assert r.headers["cache-control"] == "private, max-age=60"


def test_route_defined_cache_control_survives_the_api_v1_no_store_default():
    """The stronger version of the precedence proof: this route lives
    under /api/v1/, where the middleware would otherwise setdefault
    Cache-Control to no-store -- its own explicit value must still win."""
    app = _build_app()
    client = TestClient(app)
    r = client.get("/api/v1/set-cache-control")
    assert r.headers["cache-control"] == "private, max-age=60"


def test_route_defined_referrer_policy_is_preserved():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/set-referrer-policy")
    assert r.headers["referrer-policy"] == "no-referrer"


def test_route_defined_permissions_policy_is_preserved():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/set-permissions-policy")
    assert r.headers["permissions-policy"] == "geolocation=(self)"


# --- Precedence: mandatory invariants overwrite a conflicting value -------


def test_mandatory_invariant_headers_overwrite_conflicting_route_values():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/set-conflicting-invariants")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


# --- X-Request-ID is unaffected --------------------------------------------


def test_x_request_id_remains_present_alongside_security_headers():
    app = _build_app()
    client = TestClient(app)
    r = client.get("/probe")
    assert "x-request-id" in r.headers
    for name, value in MANAGED_HEADERS.items():
        assert r.headers[name] == value


# --- Documented, tested limitation: truly unhandled exceptions ------------


def test_unhandled_exception_response_does_not_carry_security_headers():
    """Documents the known response-coverage boundary rather than
    eliminating it: a bare, unregistered exception is caught by
    Starlette's ServerErrorMiddleware, outside every user-added
    middleware, so this middleware never runs its post-call_next code on
    that path. This is a deliberate, accepted limitation, not a defect --
    see docs/security/THREAT_MODEL.md."""
    app = _build_app()
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/unhandled")
    assert r.status_code == 500
    for name in MANAGED_HEADERS:
        assert name not in r.headers


# --- Wired into the real app ------------------------------------------------


def test_real_app_is_unaffected_with_default_test_settings(client):
    r = client.get("/health")
    assert r.status_code == 200
    for name, value in MANAGED_HEADERS.items():
        assert r.headers[name] == value
    assert "strict-transport-security" not in r.headers
    assert "cache-control" not in r.headers
