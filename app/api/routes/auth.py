from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_audit_service, get_auth_service, get_bearer_refresh_token, get_current_user
from app.core.config import get_settings
from app.core.exceptions import EmailAlreadyRegistered, InvalidCredentials, InvalidRefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutAllResponse, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from app.security.api_key import require_api_key
from app.security.tokens import decode_access_token
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService, EmailAlreadyRegisteredError, InvalidCredentialsError, InvalidRefreshTokenError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _actor_from_access_token(access_token: str) -> str | None:
    """Best-effort extraction of the `sub` claim from a just-issued access
    token, so the route can record who an audit event's actor is without
    AuthService needing to know AuditService exists (see architecture-
    review decision, Phase 1.5 PR 5: keep authentication logic and audit
    logging loosely coupled)."""
    try:
        return decode_access_token(access_token, settings=get_settings()).get("sub")
    except Exception:
        return None


def translate(exc: Exception):
    if isinstance(exc, EmailAlreadyRegisteredError):
        raise EmailAlreadyRegistered(str(exc))
    if isinstance(exc, InvalidCredentialsError):
        raise InvalidCredentials()
    if isinstance(exc, InvalidRefreshTokenError):
        raise InvalidRefreshToken()
    raise exc


# Unlike every other router in this app, this one is mounted directly on
# `app` in app/main.py rather than under `protected_api_router` -- most
# of its routes must be reachable by callers who do not (yet) hold any
# credential at all. Each route below states its own auth requirement
# explicitly:
#   - register: requires the shared X-API-Key (no public sign-up surface
#     yet -- see architecture-review decision, Phase 1.5 PR 3).
#   - login, refresh: no prior credential; the request body itself
#     (password / refresh token) is the credential being verified.
#   - logout: the refresh token, presented as the Bearer credential, is
#     the sole authorization to revoke itself.
#   - logout-all: requires a valid JWT access token.
# tests/test_api_key_protection.py's API_KEY_EXEMPT_V1_PATHS documents
# this split for the structural protection test.


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def register(request: RegisterRequest, service: AuthService = Depends(get_auth_service), audit: AuditService = Depends(get_audit_service)):
    try:
        result = service.register(request.email, request.password)
    except Exception as exc:
        if isinstance(exc, EmailAlreadyRegisteredError):
            audit.record("auth.register.failure", category="authentication", outcome="failure", reason_code="EMAIL_ALREADY_REGISTERED")
        translate(exc)
    audit.record("auth.register.success", category="authentication", outcome="success", actor_user_id=result.id)
    return result


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, service: AuthService = Depends(get_auth_service), audit: AuditService = Depends(get_audit_service)):
    try:
        result = service.login(request.email, request.password)
    except Exception as exc:
        if isinstance(exc, InvalidCredentialsError):
            audit.record("auth.login.failure", category="authentication", outcome="failure", target_user_id=exc.user_id, reason_code=exc.reason)
        translate(exc)
    audit.record("auth.login.success", category="authentication", outcome="success", actor_user_id=_actor_from_access_token(result.access_token))
    return result


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: RefreshRequest, service: AuthService = Depends(get_auth_service), audit: AuditService = Depends(get_audit_service)):
    try:
        result = service.refresh(request.refresh_token)
    except Exception as exc:
        if isinstance(exc, InvalidRefreshTokenError):
            if exc.reason == "REFRESH_TOKEN_REUSE":
                audit.record("auth.refresh_token.reuse_detected", category="authentication", outcome="denied", target_user_id=exc.user_id, reason_code=exc.reason)
            else:
                audit.record("auth.refresh.failure", category="authentication", outcome="failure", target_user_id=exc.user_id, reason_code=exc.reason)
        translate(exc)
    audit.record("auth.refresh.success", category="authentication", outcome="success", actor_user_id=_actor_from_access_token(result.access_token))
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(refresh_token: str = Depends(get_bearer_refresh_token), service: AuthService = Depends(get_auth_service), audit: AuditService = Depends(get_audit_service)):
    service.logout(refresh_token)
    audit.record("auth.logout", category="authentication", outcome="success")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", response_model=LogoutAllResponse)
def logout_all(current_user: User = Depends(get_current_user), service: AuthService = Depends(get_auth_service), audit: AuditService = Depends(get_audit_service)):
    revoked_count = service.logout_all(current_user.id)
    audit.record("auth.logout_all", category="authentication", outcome="success", actor_user_id=current_user.id, metadata={"revoked_count": revoked_count})
    return LogoutAllResponse(revoked_count=revoked_count)
