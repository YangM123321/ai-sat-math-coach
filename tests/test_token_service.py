from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import Settings
from app.security.tokens import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)


def _settings(**overrides):
    return Settings(**overrides)


def test_access_token_contains_expected_claims():
    settings = _settings()
    token = create_access_token(user_id="user_abc123", role="student", settings=settings)
    claims = decode_access_token(token, settings=settings)
    assert claims["sub"] == "user_abc123"
    assert claims["role"] == "student"
    assert claims["type"] == "access"
    assert claims["iss"] == settings.jwt_issuer
    assert claims["aud"] == settings.jwt_audience
    assert "jti" in claims and claims["jti"]
    assert "exp" in claims and "iat" in claims


def test_jti_is_unique_per_token():
    settings = _settings()
    first = decode_access_token(create_access_token(user_id="u1", role="student", settings=settings), settings=settings)
    second = decode_access_token(create_access_token(user_id="u1", role="student", settings=settings), settings=settings)
    assert first["jti"] != second["jti"]


def test_decode_rejects_expired_token():
    settings = _settings(access_token_expire_minutes=1)
    token = create_access_token(user_id="u1", role="student", settings=settings)
    # Directly craft an already-expired token using the same signing path
    # (re-encode with an exp in the past) rather than waiting a minute.
    now = datetime.now(timezone.utc)
    from app.security.tokens import _signing_key

    expired_claims = jwt.decode(token, _signing_key(settings), algorithms=["HS256"], audience=settings.jwt_audience, issuer=settings.jwt_issuer)
    expired_claims["exp"] = now - timedelta(minutes=1)
    expired_token = jwt.encode(expired_claims, _signing_key(settings), algorithm="HS256")
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(expired_token, settings=settings)


def test_decode_rejects_wrong_issuer():
    settings = _settings()
    other_issuer_settings = _settings(jwt_issuer="someone-else")
    token = create_access_token(user_id="u1", role="student", settings=other_issuer_settings)
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(token, settings=settings)


def test_decode_rejects_wrong_audience():
    settings = _settings()
    other_audience_settings = _settings(jwt_audience="someone-elses-api")
    token = create_access_token(user_id="u1", role="student", settings=other_audience_settings)
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(token, settings=settings)


def test_decode_rejects_tampered_signature():
    settings = _settings()
    token = create_access_token(user_id="u1", role="student", settings=settings)
    tampered = token[:-4] + ("a" if token[-4] != "a" else "b") + token[-3:]
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(tampered, settings=settings)


def test_decode_rejects_wrong_token_type():
    settings = _settings()
    from app.security.tokens import _signing_key

    now = datetime.now(timezone.utc)
    claims = {
        "sub": "u1",
        "role": "student",
        "type": "refresh",  # forged type claim
        "jti": "whatever",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    token = jwt.encode(claims, _signing_key(settings), algorithm="HS256")
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(token, settings=settings)


def test_decode_rejects_alg_none():
    """Refuses to accept a token whose header claims alg=none, even
    though it would otherwise carry valid-looking claims -- the decode
    path pins algorithms=["HS256"] and never trusts the token's own
    stated algorithm."""
    settings = _settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "u1", "role": "student", "type": "access", "jti": "x",
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
        "iat": now, "exp": now + timedelta(minutes=15),
    }
    forged = jwt.encode(claims, None, algorithm="none")
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(forged, settings=settings)


def test_generate_refresh_token_is_high_entropy_and_unique():
    first = generate_refresh_token()
    second = generate_refresh_token()
    assert first != second
    assert len(first) >= 32


def test_hash_refresh_token_is_deterministic_sha256():
    import hashlib

    token = "some-raw-refresh-token-value"
    assert hash_refresh_token(token) == hashlib.sha256(token.encode("utf-8")).hexdigest()
