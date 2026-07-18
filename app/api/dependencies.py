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
