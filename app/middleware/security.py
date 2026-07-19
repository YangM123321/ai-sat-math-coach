"""Runtime CORS and Trusted Host enforcement (Phase 1.5 PR 7).

Pure consumers of Settings.cors_allowed_origins / Settings.trusted_hosts
(app/core/config.py, Phase 1.5 PR1) -- no new configuration, no new
validation logic. Production already refuses to start unless both are
non-empty and wildcard-free (Settings._refuse_insecure_production_startup);
this module only wires the already-validated values into Starlette's
built-in middleware at runtime.

Empty-list semantics differ between the two middlewares, and matter for
what "no configuration" means in development/test:
  - empty `trusted_hosts` -> allow ALL hosts. Starlette's
    TrustedHostMiddleware treats an *empty list* as "nothing matches,
    reject everything" (confirmed against its source -- allow_any is only
    true when "*" is literally in the list), which is the opposite of
    what an unset TRUSTED_HOSTS should mean locally. Passing `None`
    instead makes Starlette default internally to `["*"]`. This is a
    values-adaptation, not new validation: the non-empty/no-wildcard
    *rule* still lives solely in Settings.
  - empty `cors_allowed_origins` -> allow NO browser origins.
    CORSMiddleware never blocks a request server-side either way (see
    below); an empty list just means no Origin ever receives
    Access-Control-Allow-Origin, so browsers block cross-origin JS reads
    while curl/TestClient/mobile/server-to-server callers (which don't
    send an Origin header) are completely unaffected.

CORS enforcement is client-side (the browser), not server-side: a
disallowed-origin *simple* request still reaches the route and gets a
normal response, just without the CORS header, so the browser -- not
this API -- refuses to let JS read it. Only a *preflight* (OPTIONS with
Access-Control-Request-Method) gets a genuine 400 from CORSMiddleware
for a disallowed origin/method/header. TrustedHostMiddleware, by
contrast, rejects every non-matching request outright with its own
built-in 400 PlainTextResponse -- deliberately left as Starlette's
default response shape rather than reshaped into this app's AppError
JSON envelope; a wrong Host header is the most primitive possible
rejection, analogous to a failed TLS handshake not producing an
app-level JSON body either.

allow_methods/allow_headers are explicit lists, not "*": this API's
surface is small and fully known (see the grep-derived lists below), so
there's no compatibility reason to fall back to a wildcard the way a
large/evolving public API might need. Content-Type is included for
self-documentation even though Starlette always merges in its own
SAFELISTED_HEADERS (Content-Language, Content-Type, Accept,
Accept-Language) regardless of what's passed here. "OPTIONS" is
deliberately absent from ALLOW_METHODS: CORSMiddleware checks the
*intended* request method from the Access-Control-Request-Method header,
never the preflight's own OPTIONS verb, so OPTIONS never needs to appear
in this list.
"""
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import Settings

# Every HTTP method any route in this app actually declares (verified via
# `grep -rhoE "@router\.(get|post|put|patch|delete)" app/api/routes/*.py`).
ALLOW_METHODS = ["GET", "POST", "PATCH"]

# Every non-safelisted header a legitimate cross-origin browser client
# needs to send: the bearer credential, the shared API key, and the
# optional client-supplied request-correlation id
# (app/middleware/request_context.py).
ALLOW_HEADERS = ["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"]


def configure_security_middleware(app: FastAPI, settings: Settings) -> None:
    """Registers CORSMiddleware then TrustedHostMiddleware, in that call
    order. Starlette's add_middleware makes the *last*-added middleware
    outermost (runs first on the request path) -- calling these two
    before app/main.py's later RequestContextMiddleware registration
    keeps RequestContextMiddleware outermost of all three, so every
    request is logged even if TrustedHost/CORS subsequently reject it."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,  # Bearer-token auth, no cookies -- nothing needs this
        allow_methods=ALLOW_METHODS,
        allow_headers=ALLOW_HEADERS,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts or None,
        www_redirect=False,  # this is an API, not a browser-navigated site -- a redirect on a
                              # non-GET request is actively broken for most HTTP clients
    )
