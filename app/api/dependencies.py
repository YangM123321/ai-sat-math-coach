from fastapi import Depends
from app.db.session import get_db
from app.core.config import get_settings
from app.repositories.diagnostic_repository import Repository
from app.services.grading_service import GradingService
from app.services.llm_service import RuleBasedProvider
from app.services.confidence_service import ConfidenceService
from app.services.diagnostic_service import DiagnosticService

def get_service(db=Depends(get_db)):
    s=get_settings()
    if s.diagnostic_provider!='rule_based': raise RuntimeError('Only rule_based is implemented in V1')
    return DiagnosticService(Repository(db),GradingService(),RuleBasedProvider(),ConfidenceService(s.human_review_threshold))

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.mastery_service import KnowledgeService

def get_knowledge_service(db=Depends(get_db)):
    return KnowledgeService(KnowledgeRepository(db))

from app.repositories.learning_repository import LearningRepository
from app.services.learning_service import LearningService

def get_learning_service(db=Depends(get_db)):
    return LearningService(LearningRepository(db))

from app.repositories.tutor_repository import TutorRepository
from app.services.tutor_service import TutorService

def get_tutor_service(db=Depends(get_db)):
    return TutorService(TutorRepository(db))

from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.user_repository import UserRepository
from app.services.dashboard_service import DashboardService

def get_dashboard_service(db=Depends(get_db)):
    return DashboardService(DashboardRepository(db), UserRepository(db))

from app.repositories.evaluation_repository import EvaluationRepository
from app.services.evaluation_service import EvaluationService

def get_evaluation_service(db=Depends(get_db)):
    return EvaluationService(EvaluationRepository(db))

from app.repositories.user_repository import UserRepository
from app.security.password_hashing import PasswordService
from app.services.auth_service import AuthService

def get_auth_service(db=Depends(get_db)):
    return AuthService(UserRepository(db), PasswordService(), get_settings())

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.exceptions import InvalidRefreshToken, InvalidToken
from app.models.user import User
from app.security.tokens import InvalidAccessTokenError, decode_access_token

# Mirrors app/security/api_key.py's self-contained dependency-function
# style, but lives here rather than under app/security/ since it also
# does a DB lookup and applies an authentication-outcome decision
# (is_active), not just a cryptographic check -- app/security/ stays
# limited to token/password primitives (app/security/tokens.py,
# app/security/password_hashing.py). get_current_user re-fetches the
# live User row on every call (rather than trusting the JWT's embedded
# role alone) so a disabled account is rejected on its very next
# request, not just once its access token naturally expires.
_access_token_scheme = HTTPBearer(description="JWT access token.", auto_error=False)
_refresh_token_scheme = HTTPBearer(description="Opaque refresh token.", auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_access_token_scheme),
    db=Depends(get_db),
) -> User:
    if credentials is None:
        raise InvalidToken()
    settings = get_settings()
    try:
        claims = decode_access_token(credentials.credentials, settings=settings)
    except InvalidAccessTokenError:
        raise InvalidToken()
    user = db.get(User, claims.get("sub"))
    if user is None or not user.is_active:
        raise InvalidToken()
    return user

def get_bearer_refresh_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_refresh_token_scheme),
) -> str:
    """Extracts the raw opaque refresh token from `Authorization: Bearer
    <refresh_token>`. No JWT decoding happens here -- refresh tokens are
    plain high-entropy random strings, never JWTs (see
    app/security/tokens.py)."""
    if credentials is None:
        raise InvalidRefreshToken()
    return credentials.credentials

from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService

def get_audit_service(db=Depends(get_db)):
    return AuditService(AuditRepository(db))

from app.services.authorization_service import AuthorizationService

def get_authorization_service(db=Depends(get_db), audit_service: AuditService = Depends(get_audit_service)):
    return AuthorizationService(DashboardRepository(db), audit_service)

def require_admin(
    user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> User:
    """Composed dependency for routes/routers that are admin-only in
    their entirety (e.g. the evaluation router) -- equivalent to calling
    get_current_user then authz.ensure_admin(user), but usable directly
    in a router's `dependencies=[...]` list."""
    authz.ensure_admin(user)
    return user

from app.core.exceptions import RateLimited
from app.middleware.request_context import get_request_context
from app.services.auth_service import normalize_email
from app.services.rate_limiter_service import RateLimitResult, get_api_rate_limiter, get_rate_limiter


def _client_rate_limit_key() -> str:
    return get_request_context()["ip_address"] or "unknown"


def _raise_if_denied(
    result: RateLimitResult,
    audit: AuditService,
    event_name: str,
    reason_code: str,
    *,
    category: str = "authentication",
    actor_user_id: str | None = None,
) -> None:
    if result.allowed:
        return
    audit.record(event_name, category=category, outcome="denied", actor_user_id=actor_user_id, reason_code=reason_code)
    raise RateLimited(
        retry_after_seconds=result.reset_seconds,
        limit=result.limit,
        remaining=result.remaining,
        reset_seconds=result.reset_seconds,
    )


def rate_limit_auth_ip(audit: AuditService = Depends(get_audit_service)) -> None:
    """Coarse per-IP backpressure shared by register/refresh/logout/
    logout-all (T11). Login uses its own, tighter tiers -- see
    rate_limit_login_ip and check_login_account_rate_limit below."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    result = get_rate_limiter().check(
        f"auth_ip:{_client_rate_limit_key()}",
        max_attempts=settings.rate_limit_auth_ip_max_attempts,
        window_seconds=settings.rate_limit_auth_ip_window_seconds,
    )
    _raise_if_denied(result, audit, "auth.rate_limited", "RATE_LIMIT_IP")


def rate_limit_login_ip(audit: AuditService = Depends(get_audit_service)) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    result = get_rate_limiter().check(
        f"login_ip:{_client_rate_limit_key()}",
        max_attempts=settings.rate_limit_login_ip_max_attempts,
        window_seconds=settings.rate_limit_login_ip_window_seconds,
    )
    _raise_if_denied(result, audit, "auth.login.rate_limited", "RATE_LIMIT_IP")


def check_login_account_rate_limit(email: str, audit: AuditService) -> None:
    """Called explicitly from the login route body (not a declarative
    Depends) because it needs the already-parsed request body's email --
    see architecture-review decision, Phase 1.5 PR 6. Keyed on the
    normalized email (app.services.auth_service.normalize_email), so an
    attacker can't dodge the per-account tier with case/whitespace
    variants of the same address."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    result = get_rate_limiter().check(
        f"login_account:{normalize_email(email)}",
        max_attempts=settings.rate_limit_login_account_max_attempts,
        window_seconds=settings.rate_limit_login_account_window_seconds,
    )
    _raise_if_denied(result, audit, "auth.login.rate_limited", "RATE_LIMIT_ACCOUNT")


# --- General /api/v1/* rate limiting (Phase 1.5 PR 14) ---------------------
# Uses a separate limiter instance (get_api_rate_limiter) and a separate
# enable flag (rate_limit_api_enabled) from PR6's auth-only tiers above --
# see docs/security/THREAT_MODEL.md T11 for why the two must never share
# instance state.
#
# The four rate_limit_api_* category functions below are deliberately
# left flat and near-identical rather than factored through a shared
# helper -- mirrors rate_limit_auth_ip/rate_limit_login_ip/
# check_login_account_rate_limit's own unfactored shape immediately
# above, this file's established precedent for one-dependency-per-tier.


def rate_limit_api_perimeter(audit: AuditService = Depends(get_audit_service)) -> None:
    """Coarse, identity-free perimeter tier for every protected_api_router
    request. Attached once, at the router level (app/main.py), and runs
    before require_api_key/get_current_user by construction, so its own
    cost stays a single dict lookup -- it exists specifically to protect
    the cost of everything downstream from being reached at all during a
    flood. IP-keyed via the same, unchanged _client_rate_limit_key() PR6
    already uses."""
    settings = get_settings()
    if not settings.rate_limit_api_enabled:
        return
    result = get_api_rate_limiter().check(
        f"api_perimeter:{_client_rate_limit_key()}",
        max_attempts=settings.rate_limit_api_perimeter_max_attempts,
        window_seconds=settings.rate_limit_api_perimeter_window_seconds,
    )
    _raise_if_denied(result, audit, "api.rate_limited", "RATE_LIMIT_PERIMETER", category="authorization")


def rate_limit_api_read(
    user: User = Depends(get_current_user),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """Authenticated read tier -- keyed on the caller's own user.id, never
    a path-supplied student_id (a teacher holding grants across many
    students is bounded once, holistically, by their own account)."""
    settings = get_settings()
    if not settings.rate_limit_api_enabled:
        return
    result = get_api_rate_limiter().check(
        f"api_read:{user.id}",
        max_attempts=settings.rate_limit_api_read_max_attempts,
        window_seconds=settings.rate_limit_api_read_window_seconds,
    )
    _raise_if_denied(result, audit, "api.rate_limited", "RATE_LIMIT_READ", category="authorization", actor_user_id=user.id)


def rate_limit_api_write(
    user: User = Depends(get_current_user),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """Authenticated write tier -- see rate_limit_api_read for the
    user.id-keying rationale."""
    settings = get_settings()
    if not settings.rate_limit_api_enabled:
        return
    result = get_api_rate_limiter().check(
        f"api_write:{user.id}",
        max_attempts=settings.rate_limit_api_write_max_attempts,
        window_seconds=settings.rate_limit_api_write_window_seconds,
    )
    _raise_if_denied(result, audit, "api.rate_limited", "RATE_LIMIT_WRITE", category="authorization", actor_user_id=user.id)


def rate_limit_api_expensive(
    user: User = Depends(get_current_user),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """Authenticated expensive/diagnostic-AI tier -- the heaviest-compute
    routes today, and the explicit future LLM-cost surface (ADR 0002)."""
    settings = get_settings()
    if not settings.rate_limit_api_enabled:
        return
    result = get_api_rate_limiter().check(
        f"api_expensive:{user.id}",
        max_attempts=settings.rate_limit_api_expensive_max_attempts,
        window_seconds=settings.rate_limit_api_expensive_window_seconds,
    )
    _raise_if_denied(result, audit, "api.rate_limited", "RATE_LIMIT_EXPENSIVE", category="authorization", actor_user_id=user.id)


def rate_limit_api_admin(
    user: User = Depends(get_current_user),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """Administrative tier -- a safety net against a compromised or
    malfunctioning admin credential/script, not the primary adversarial
    control (admin accounts are already the most trusted in this system)."""
    settings = get_settings()
    if not settings.rate_limit_api_enabled:
        return
    result = get_api_rate_limiter().check(
        f"api_admin:{user.id}",
        max_attempts=settings.rate_limit_api_admin_max_attempts,
        window_seconds=settings.rate_limit_api_admin_window_seconds,
    )
    _raise_if_denied(result, audit, "api.rate_limited", "RATE_LIMIT_ADMIN", category="authorization", actor_user_id=user.id)
