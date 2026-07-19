"""Tests for CORS/TrustedHost runtime enforcement (Phase 1.5 PR 7).

Exercises configure_security_middleware directly against throwaway
FastAPI() instances + hand-built Settings, not the shared app/client
fixtures -- Starlette bakes middleware constructor args in at
app.add_middleware() call time (module-import time for the real app), so
there is no way to dynamically retoggle CORS/TrustedHost behavior per
test the way the enable_api_key/enable_rate_limiting fixtures do for
dependency-based checks. See app/middleware/security.py's module
docstring for the underlying empty-list semantics this file verifies.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.middleware.security import ALLOW_HEADERS, ALLOW_METHODS, configure_security_middleware


def _build_app(**settings_overrides):
    settings = Settings(_env_file=None, **settings_overrides)
    app = FastAPI()
    configure_security_middleware(app, settings)

    @app.get("/probe")
    def probe_get():
        return {"ok": True}

    @app.post("/probe")
    def probe_post():
        return {"ok": True}

    return app


# --- TrustedHost -------------------------------------------------------

def test_trusted_host_allows_configured_host():
    app = _build_app(trusted_hosts=["allowed.example.com"])
    client = TestClient(app, base_url="http://allowed.example.com")
    assert client.get("/probe").status_code == 200


def test_trusted_host_rejects_unconfigured_host():
    app = _build_app(trusted_hosts=["allowed.example.com"])
    client = TestClient(app, base_url="http://evil.example.com")
    r = client.get("/probe")
    assert r.status_code == 400
    assert r.text == "Invalid host header"


def test_empty_trusted_hosts_allows_any_host():
    """Documented semantics: empty trusted_hosts means allow ALL hosts."""
    app = _build_app(trusted_hosts=[])
    client = TestClient(app, base_url="http://anything.example.com")
    assert client.get("/probe").status_code == 200


def test_trusted_host_does_not_redirect_www():
    app = _build_app(trusted_hosts=["www.allowed.example.com"])
    client = TestClient(app, base_url="http://allowed.example.com", follow_redirects=False)
    # Starlette's default (www_redirect=True) would 301 here; this app
    # disables it explicitly (see app/middleware/security.py).
    assert client.get("/probe").status_code == 400


# --- CORS ----------------------------------------------------------------

def test_cors_preflight_allowed_origin():
    app = _build_app(cors_allowed_origins=["https://allowed.example.com"])
    client = TestClient(app)
    r = client.options(
        "/probe",
        headers={"Origin": "https://allowed.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://allowed.example.com"


def test_cors_preflight_disallowed_origin():
    app = _build_app(cors_allowed_origins=["https://allowed.example.com"])
    client = TestClient(app)
    r = client.options(
        "/probe",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers


def test_cors_simple_request_from_allowed_origin_gets_header():
    app = _build_app(cors_allowed_origins=["https://allowed.example.com"])
    client = TestClient(app)
    r = client.get("/probe", headers={"Origin": "https://allowed.example.com"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://allowed.example.com"


def test_cors_simple_request_from_disallowed_origin_still_succeeds_without_header():
    """CORS is enforced by the browser, not this server -- a disallowed
    origin still gets a normal response, just without the header."""
    app = _build_app(cors_allowed_origins=["https://allowed.example.com"])
    client = TestClient(app)
    r = client.get("/probe", headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_empty_cors_allowed_origins_grants_no_origin_the_header():
    """Documented semantics: empty cors_allowed_origins means allow NO
    browser origins."""
    app = _build_app(cors_allowed_origins=[])
    client = TestClient(app)
    r = client.get("/probe", headers={"Origin": "https://anything.example.com"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_request_without_origin_header_is_unaffected():
    """The entire existing (~240-test) suite relies on this -- none of it
    sets an Origin header."""
    app = _build_app(cors_allowed_origins=["https://allowed.example.com"])
    client = TestClient(app)
    r = client.get("/probe")
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_allow_methods_and_headers_are_explicit_not_wildcard():
    assert "*" not in ALLOW_METHODS
    assert "*" not in ALLOW_HEADERS
    assert set(ALLOW_METHODS) == {"GET", "POST", "PATCH"}
    assert {"Authorization", "X-API-Key"}.issubset(set(ALLOW_HEADERS))


# --- Wired into the real app ---------------------------------------------

def test_real_app_is_unaffected_with_default_test_settings(client):
    r = client.get("/health")
    assert r.status_code == 200
