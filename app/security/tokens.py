"""JWT access tokens and opaque refresh-token helpers (Phase 1.5 PR 3).

Access tokens are short-lived JWTs (HS256, signed with SECRET_KEY),
carrying `sub` (user id), `role`, `type: "access"`, a unique `jti`,
`iss`, `aud`, `iat`, `exp`. Decoding pins `algorithms=["HS256"]`
explicitly -- the algorithm is never taken from the token itself, which
closes the classic "alg:none"/algorithm-confusion class of JWT bugs.

Refresh tokens are opaque, high-entropy random credentials
(`secrets.token_urlsafe`), NOT JWTs. The raw value is returned to the
client exactly once, at issuance/rotation time; the server persists
only its SHA-256 hash (see app.models.user.RefreshToken.token_hash).
SHA-256 -- not Argon2id -- is deliberately used here: Argon2id exists to
slow down brute-forcing of low-entropy human passwords, which is
unnecessary and wasteful for verifying an already-high-entropy random
secret on every refresh/logout call.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings

ACCESS_TOKEN_TYPE = "access"

# Falls back to a fixed, clearly-labeled development-only signing key
# when SECRET_KEY is unset. Safe because app/core/config.py's production
# startup validation refuses to boot in ENVIRONMENT=production without a
# real, strong SECRET_KEY -- this fallback is only ever reached in
# development/test, which docs/security/THREAT_MODEL.md's security
# assumptions already treat as never exposed to the public internet.
_DEV_INSECURE_SECRET_KEY = "dev-only-insecure-secret-key-do-not-use-in-production"


class InvalidAccessTokenError(Exception):
    pass


def _signing_key(settings: Settings) -> str:
    return settings.secret_key or _DEV_INSECURE_SECRET_KEY


def create_access_token(*, user_id: str, role: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user_id,
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "jti": secrets.token_hex(16),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(claims, _signing_key(settings), algorithm="HS256")


def decode_access_token(token: str, *, settings: Settings) -> dict:
    """Decode and fully validate an access token: signature, issuer,
    audience, expiration, and the custom `type` claim. Raises
    InvalidAccessTokenError uniformly on any failure so callers cannot
    distinguish which specific check failed."""
    try:
        claims = jwt.decode(
            token,
            _signing_key(settings),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except jwt.PyJWTError as exc:
        raise InvalidAccessTokenError(str(exc)) from exc
    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidAccessTokenError("unexpected token type")
    return claims


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
