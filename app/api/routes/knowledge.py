from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import get_authorization_service, get_current_user, get_knowledge_service, rate_limit_api_admin, rate_limit_api_read, rate_limit_api_write, require_admin
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeGraphResponse,
    KnowledgeProfileResponse,
    MasteryEventResponse,
    MasteryEvidenceInput,
    RelationshipCreate,
    RelationshipResponse,
    SkillCreate,
    SkillResponse,
)
from app.services.authorization_service import AuthorizationService
from app.services.mastery_service import KnowledgeService, SkillNotFoundError

router = APIRouter(prefix="/api/v1", tags=["knowledge-model"])


def translate_error(exc: Exception):
    if isinstance(exc, SkillNotFoundError):
        raise HTTPException(status_code=404, detail={"code": "SKILL_NOT_FOUND", "skill_code": str(exc)})
    if isinstance(exc, (ValueError, IntegrityError)):
        raise HTTPException(status_code=409, detail={"code": "KNOWLEDGE_MODEL_CONFLICT", "message": str(exc)})
    raise exc


@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin), Depends(rate_limit_api_admin)])
def create_skill(
    request: SkillCreate,
    service: KnowledgeService = Depends(get_knowledge_service),
):
    try:
        return service.create_skill(request)
    except Exception as exc:
        translate_error(exc)


@router.get("/skills", response_model=list[SkillResponse], dependencies=[Depends(rate_limit_api_read)])
def list_skills(service: KnowledgeService = Depends(get_knowledge_service), user: User = Depends(get_current_user)):
    return service.list_skills()


@router.post("/skill-relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin), Depends(rate_limit_api_admin)])
def create_relationship(
    request: RelationshipCreate,
    service: KnowledgeService = Depends(get_knowledge_service),
):
    try:
        return service.create_relationship(request)
    except Exception as exc:
        translate_error(exc)


@router.post("/mastery/evidence", response_model=MasteryEventResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit_api_write)])
def apply_mastery_evidence(
    request: MasteryEvidenceInput,
    service: KnowledgeService = Depends(get_knowledge_service),
    user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
):
    authz.ensure_student_write_access(user, request.student_id)
    try:
        return service.apply_evidence(request)
    except Exception as exc:
        translate_error(exc)


@router.get("/students/{student_id}/knowledge-profile", response_model=KnowledgeProfileResponse, dependencies=[Depends(rate_limit_api_read)])
def get_profile(
    student_id: str,
    service: KnowledgeService = Depends(get_knowledge_service),
    user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
):
    authz.ensure_student_read_access(user, student_id)
    return service.get_profile(student_id)


@router.get("/students/{student_id}/knowledge-graph", response_model=KnowledgeGraphResponse, dependencies=[Depends(rate_limit_api_read)])
def get_graph(
    student_id: str,
    service: KnowledgeService = Depends(get_knowledge_service),
    user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
):
    authz.ensure_student_read_access(user, student_id)
    return service.get_graph(student_id)
