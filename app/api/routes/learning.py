from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies import get_learning_service
from app.schemas.learning import LearningActivityResponse, LearningActivityUpdate, LearningPlanCreate, LearningPlanResponse
from app.services.learning_service import LearningActivityNotFoundError, LearningPlanNotFoundError, LearningService, NoSkillCatalogError

router=APIRouter(prefix="/api/v1", tags=["personalized-learning"])

def translate(exc):
    if isinstance(exc, LearningPlanNotFoundError): raise HTTPException(404, detail={"code":"LEARNING_PLAN_NOT_FOUND","identifier":str(exc)})
    if isinstance(exc, LearningActivityNotFoundError): raise HTTPException(404, detail={"code":"LEARNING_ACTIVITY_NOT_FOUND","identifier":str(exc)})
    if isinstance(exc, NoSkillCatalogError): raise HTTPException(409, detail={"code":"SKILL_CATALOG_EMPTY","message":str(exc)})
    raise exc

@router.post("/learning-plans", response_model=LearningPlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(request: LearningPlanCreate, service: LearningService=Depends(get_learning_service)):
    try: return service.generate(request)
    except Exception as exc: translate(exc)

@router.get("/learning-plans/{plan_id}", response_model=LearningPlanResponse)
def get_plan(plan_id: str, service: LearningService=Depends(get_learning_service)):
    try: return service.get(plan_id)
    except Exception as exc: translate(exc)

@router.get("/students/{student_id}/active-learning-plan", response_model=LearningPlanResponse)
def active_plan(student_id: str, service: LearningService=Depends(get_learning_service)):
    try: return service.get_active(student_id)
    except Exception as exc: translate(exc)

@router.patch("/learning-activities/{activity_id}", response_model=LearningActivityResponse)
def update_activity(activity_id: str, request: LearningActivityUpdate, service: LearningService=Depends(get_learning_service)):
    try: return service.update_activity(activity_id, request)
    except Exception as exc: translate(exc)
