"""Authentication service (Phase 1.5 PR 3): register/login/refresh/logout.

Consumes the identity schema added in PR 2B (app.models.user). Email
normalization (lowercase + trim) happens here, before every persistence
and lookup -- never in the model (see app/models/user.py's docstring).
Role is never accepted from a caller; registration always creates the
least-privileged UserRole.student (app/schemas/auth.py's RegisterRequest
has no role field at all).
"""
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.models.user import RefreshToken, User
from app.schemas.auth import TokenResponse, UserResponse
from app.security.password_hashing import PasswordService
from app.security.tokens import create_access_token, generate_refresh_token, hash_refresh_token


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _as_aware_utc(value: datetime) -> datetime:
    """SQLite round-trips datetimes as naive (PostgreSQL preserves
    timezone-awareness); treat a naive value as UTC, since every
    datetime this service writes is created via datetime.now(timezone.utc)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


class AuthService:
    def __init__(self, repository, password_service: PasswordService, settings: Settings):
        self.repository = repository
        self.password_service = password_service
        self.settings = settings

    def register(self, email: str, password: str) -> UserResponse:
        normalized = normalize_email(email)
        if self.repository.get_by_email(normalized) is not None:
            raise EmailAlreadyRegisteredError(normalized)
        password_hash = self.password_service.hash(password)
        user = self.repository.create(email=normalized, password_hash=password_hash)
        return self._user_response(user)

    def login(self, email: str, password: str) -> TokenResponse:
        normalized = normalize_email(email)
        user = self.repository.get_by_email(normalized)
        if user is None:
            # Closes the timing side-channel that would otherwise let an
            # attacker distinguish "no such account" from "wrong
            # password" by response latency.
            self.password_service.verify_dummy()
            raise InvalidCredentialsError()
        if not self.password_service.verify(password, user.password_hash):
            raise InvalidCredentialsError()
        if not user.is_active:
            # Identical error to the two cases above -- see
            # InvalidCredentials in app/core/exceptions.py.
            raise InvalidCredentialsError()
        token_response, _ = self._issue_tokens(user)
        return token_response

    def refresh(self, raw_refresh_token: str) -> TokenResponse:
        token_hash = hash_refresh_token(raw_refresh_token)
        token = self.repository.get_refresh_token_by_hash(token_hash)
        if token is None:
            raise InvalidRefreshTokenError()
        if token.revoked_at is not None:
            if token.replaced_by_id is not None:
                # This token was revoked because it was rotated out (not
                # merely logged out) -- replaying it is reuse of an
                # already-rotated token, a theft signal. Revoke every
                # active session for this user, not just this token's
                # own rotation chain. A token revoked via plain /logout
                # (replaced_by_id is None) falls through to the generic
                # rejection below with no side effects -- presenting an
                # already-logged-out token isn't itself a theft signal.
                self.repository.revoke_all_refresh_tokens_for_user(token.user_id)
            raise InvalidRefreshTokenError()
        if _as_aware_utc(token.expires_at) <= datetime.now(timezone.utc):
            raise InvalidRefreshTokenError()
        user = self.repository.get_by_id(token.user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError()
        token_response, new_row = self._issue_tokens(user)
        self.repository.revoke_refresh_token(token, replaced_by_id=new_row.id)
        return token_response

    def logout(self, raw_refresh_token: str) -> None:
        """Idempotent: an unknown or already-revoked token is a silent
        no-op, not an error -- logout must never reveal whether a given
        token was ever valid."""
        token = self.repository.get_refresh_token_by_hash(hash_refresh_token(raw_refresh_token))
        if token is not None and token.revoked_at is None:
            self.repository.revoke_refresh_token(token)

    def logout_all(self, user_id: str) -> int:
        return self.repository.revoke_all_refresh_tokens_for_user(user_id)

    def _issue_tokens(self, user: User) -> tuple[TokenResponse, RefreshToken]:
        access_token = create_access_token(user_id=user.id, role=user.role, settings=self.settings)
        raw_refresh = generate_refresh_token()
        refresh_row = RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=self.settings.refresh_token_expire_days),
        )
        saved = self.repository.save_refresh_token(refresh_row)
        response = TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )
        return response, saved

    @staticmethod
    def _user_response(user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_email_verified=user.is_email_verified,
            created_at=user.created_at,
        )
