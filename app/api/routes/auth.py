from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_auth_service, get_bearer_refresh_token, get_current_user
from app.core.exceptions import EmailAlreadyRegistered, InvalidCredentials, InvalidRefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutAllResponse, RefreshRequest, RegisterRequest, TokenResponse, UserResponse
from app.security.api_key import require_api_key
from app.services.auth_service import AuthService, EmailAlreadyRegisteredError, InvalidCredentialsError, InvalidRefreshTokenError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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
def register(request: RegisterRequest, service: AuthService = Depends(get_auth_service)):
    try:
        return service.register(request.email, request.password)
    except Exception as exc:
        translate(exc)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, service: AuthService = Depends(get_auth_service)):
    try:
        return service.login(request.email, request.password)
    except Exception as exc:
        translate(exc)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    try:
        return service.refresh(request.refresh_token)
    except Exception as exc:
        translate(exc)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(refresh_token: str = Depends(get_bearer_refresh_token), service: AuthService = Depends(get_auth_service)):
    service.logout(refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", response_model=LogoutAllResponse)
def logout_all(current_user: User = Depends(get_current_user), service: AuthService = Depends(get_auth_service)):
    return LogoutAllResponse(revoked_count=service.logout_all(current_user.id))
