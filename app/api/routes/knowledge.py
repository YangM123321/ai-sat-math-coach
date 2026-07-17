from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import get_knowledge_service
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
from app.services.mastery_service import KnowledgeService, SkillNotFoundError

router = APIRouter(prefix="/api/v1", tags=["knowledge-model"])


def translate_error(exc: Exception):
    if isinstance(exc, SkillNotFoundError):
        raise HTTPException(status_code=404, detail={"code": "SKILL_NOT_FOUND", "skill_code": str(exc)})
    if isinstance(exc, (ValueError, IntegrityError)):
        raise HTTPException(status_code=409, detail={"code": "KNOWLEDGE_MODEL_CONFLICT", "message": str(exc)})
    raise exc


@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def create_skill(request: SkillCreate, service: KnowledgeService = Depends(get_knowledge_service)):
    try:
        return service.create_skill(request)
    except Exception as exc:
        translate_error(exc)


@router.get("/skills", response_model=list[SkillResponse])
def list_skills(service: KnowledgeService = Depends(get_knowledge_service)):
    return service.list_skills()


@router.post("/skill-relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_relationship(request: RelationshipCreate, service: KnowledgeService = Depends(get_knowledge_service)):
    try:
        return service.create_relationship(request)
    except Exception as exc:
        translate_error(exc)


@router.post("/mastery/evidence", response_model=MasteryEventResponse, status_code=status.HTTP_201_CREATED)
def apply_mastery_evidence(request: MasteryEvidenceInput, service: KnowledgeService = Depends(get_knowledge_service)):
    try:
        return service.apply_evidence(request)
    except Exception as exc:
        translate_error(exc)


@router.get("/students/{student_id}/knowledge-profile", response_model=KnowledgeProfileResponse)
def get_profile(student_id: str, service: KnowledgeService = Depends(get_knowledge_service)):
    return service.get_profile(student_id)


@router.get("/students/{student_id}/knowledge-graph", response_model=KnowledgeGraphResponse)
def get_graph(student_id: str, service: KnowledgeService = Depends(get_knowledge_service)):
    return service.get_graph(student_id)
