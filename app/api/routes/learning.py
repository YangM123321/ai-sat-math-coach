from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies import get_authorization_service, get_current_user, get_learning_service
from app.models.user import User
from app.schemas.learning import LearningActivityResponse, LearningActivityUpdate, LearningPlanCreate, LearningPlanResponse
from app.services.authorization_service import AuthorizationService
from app.services.learning_service import LearningActivityNotFoundError, LearningPlanNotFoundError, LearningService, NoSkillCatalogError

router=APIRouter(prefix="/api/v1", tags=["personalized-learning"])

def translate(exc):
    if isinstance(exc, LearningPlanNotFoundError): raise HTTPException(404, detail={"code":"LEARNING_PLAN_NOT_FOUND","identifier":str(exc)})
    if isinstance(exc, LearningActivityNotFoundError): raise HTTPException(404, detail={"code":"LEARNING_ACTIVITY_NOT_FOUND","identifier":str(exc)})
    if isinstance(exc, NoSkillCatalogError): raise HTTPException(409, detail={"code":"SKILL_CATALOG_EMPTY","message":str(exc)})
    raise exc

@router.post("/learning-plans", response_model=LearningPlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(request: LearningPlanCreate, service: LearningService=Depends(get_learning_service), user: User=Depends(get_current_user), authz: AuthorizationService=Depends(get_authorization_service)):
    authz.ensure_student_write_access(user, request.student_id)
    try: return service.generate(request)
    except Exception as exc: translate(exc)

@router.get("/learning-plans/{plan_id}", response_model=LearningPlanResponse)
def get_plan(plan_id: str, service: LearningService=Depends(get_learning_service), user: User=Depends(get_current_user), authz: AuthorizationService=Depends(get_authorization_service)):
    try: result = service.get(plan_id)
    except Exception as exc: translate(exc)
    authz.ensure_student_read_access(user, result.student_id)
    return result

@router.get("/students/{student_id}/active-learning-plan", response_model=LearningPlanResponse)
def active_plan(student_id: str, service: LearningService=Depends(get_learning_service), user: User=Depends(get_current_user), authz: AuthorizationService=Depends(get_authorization_service)):
    authz.ensure_student_read_access(user, student_id)
    try: return service.get_active(student_id)
    except Exception as exc: translate(exc)

@router.patch("/learning-activities/{activity_id}", response_model=LearningActivityResponse)
def update_activity(activity_id: str, request: LearningActivityUpdate, service: LearningService=Depends(get_learning_service), user: User=Depends(get_current_user), authz: AuthorizationService=Depends(get_authorization_service)):
    try: owner_student_id = service.get_activity_owner_student_id(activity_id)
    except Exception as exc: translate(exc)
    authz.ensure_student_write_access(user, owner_student_id)
    try: return service.update_activity(activity_id, request)
    except Exception as exc: translate(exc)
