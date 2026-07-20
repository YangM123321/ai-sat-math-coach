"""Security response headers (Phase 1.5 PR 13).

Adds a fixed set of browser-security response headers to every response
that returns normally through the middleware chain (see
docs/security/THREAT_MODEL.md for the exact response-coverage boundary --
a truly unhandled exception, caught by Starlette's ServerErrorMiddleware
outside every user-added middleware, never reaches this class).

Four headers are mandatory invariants and always overwrite a conflicting
value: Strict-Transport-Security (production only), Content-Security-Policy
(outside the documentation routes), X-Content-Type-Options, and
X-Frame-Options -- no route in this codebase has a legitimate reason to
serve a weaker value for any of these. Three headers are safe defaults,
applied with MutableHeaders.setdefault so an explicitly-configured
route-level value is never silently overridden: Referrer-Policy,
Permissions-Policy, and Cache-Control.

HSTS is gated solely on `settings.environment == Environment.production`,
never on `request.url.scheme` or a forwarded-proto header -- this
application has no trusted-proxy configuration (uvicorn's
`forwarded_allow_ips` defaults to 127.0.0.1 and nothing in this repo's
Dockerfile/docker-compose.yml narrows or widens that), so a scheme-derived
signal would be attacker-influenceable rather than safer. See the Threat
Model for the resulting operational prerequisite: ENVIRONMENT=production
must only be set once genuine, end-to-end HTTPS is actually enforced by
the deployment edge.

Content-Security-Policy exempts exactly the two FastAPI-served HTML
documentation pages, derived dynamically from the live app instance
(request.app.docs_url / request.app.redoc_url) rather than hardcoded
"/docs"/"/redoc" literals, so a future FastAPI(docs_url=...) customization
-- or a disabled documentation route, where the attribute is None -- is
picked up automatically with no change here. request.app.openapi_url is
deliberately not exempted: CSP is enforced by the browser against the
*document* that initiates a fetch, not against the policy header attached
to the fetched resource itself, so the OpenAPI JSON schema route keeps the
strict policy at no compatibility cost.
"""

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import Environment, Settings

CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
REFERRER_POLICY = "strict-origin-when-cross-origin"
HSTS_VALUE = "max-age=31536000"
X_CONTENT_TYPE_OPTIONS = "nosniff"
X_FRAME_OPTIONS = "DENY"
CACHE_CONTROL_VALUE = "no-store"

# Only /api/v1/* responses default to no-store: this is the entire
# authenticated application surface (diagnostics/knowledge/learning/
# tutor/dashboard/evaluation, plus the token-issuing auth endpoints),
# where caching a per-user response in a shared/intermediate cache would
# leak it to a different caller. /health, /ready, and the documentation
# routes are intentionally outside this prefix and never get a forced
# Cache-Control value.
CACHE_CONTROL_PATH_PREFIX = "/api/v1/"


def _is_documentation_route(request: Request) -> bool:
    """True only for the live app's own Swagger UI / ReDoc HTML pages --
    never request.app.openapi_url, and never a hardcoded path literal."""
    path = request.url.path
    docs_url = request.app.docs_url
    redoc_url = request.app.redoc_url
    return (docs_url is not None and path == docs_url) or (
        redoc_url is not None and path == redoc_url
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Stamp the seven security headers described in
    docs/security/THREAT_MODEL.md onto every response that returns
    normally through call_next."""

    def __init__(self, app: FastAPI, *, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path

        if self._settings.environment is Environment.production:
            response.headers["Strict-Transport-Security"] = HSTS_VALUE

        if not _is_documentation_route(request):
            response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY

        response.headers["X-Content-Type-Options"] = X_CONTENT_TYPE_OPTIONS
        response.headers["X-Frame-Options"] = X_FRAME_OPTIONS

        response.headers.setdefault("Referrer-Policy", REFERRER_POLICY)
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)

        if path.startswith(CACHE_CONTROL_PATH_PREFIX):
            response.headers.setdefault("Cache-Control", CACHE_CONTROL_VALUE)

        return response
