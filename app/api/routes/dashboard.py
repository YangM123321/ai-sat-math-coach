from fastapi import APIRouter, Depends, Query, status
from app.api.dependencies import get_audit_service, get_authorization_service, get_current_user, get_dashboard_service, require_admin
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.dashboard import *
from app.services.audit_service import AuditService
from app.services.authorization_service import AuthorizationService
from app.services.dashboard_service import DashboardStudentDataNotFoundError
router=APIRouter(prefix='/api/v1/dashboard',tags=['teacher-parent-dashboard'])

def translate(exc):
    if isinstance(exc,DashboardStudentDataNotFoundError): return AppError(404,'DASHBOARD_STUDENT_DATA_NOT_FOUND','No dashboard data is available for this student.')
    return exc

@router.post('/access-grants',response_model=AccessGrantResponse,status_code=status.HTTP_201_CREATED)
def grant_access(request:AccessGrantCreate,service=Depends(get_dashboard_service),user:User=Depends(require_admin),audit:AuditService=Depends(get_audit_service)):
    response=service.grant(request,created_by=user.id)
    audit.record('authorization.access_granted',category='authorization',outcome='success',actor_user_id=user.id,target_user_id=request.student_id,resource_type='dashboard_access_grant',resource_id=response.id,metadata={'viewer_id':request.viewer_id,'role':request.role.value})
    return response

@router.get('/students/{student_id}',response_model=StudentDashboardResponse)
def student_dashboard(student_id:str,service=Depends(get_dashboard_service),user:User=Depends(get_current_user),authz:AuthorizationService=Depends(get_authorization_service)):
    authz.ensure_student_read_access(user,student_id)
    try:return service.dashboard(student_id)
    except Exception as exc: raise translate(exc)

@router.get('/viewers/{viewer_id}/overview',response_model=ViewerOverviewResponse)
def viewer_overview(viewer_id:str,role:ViewerRole|None=Query(default=None),service=Depends(get_dashboard_service),user:User=Depends(get_current_user),authz:AuthorizationService=Depends(get_authorization_service)):
    authz.ensure_self(user,viewer_id)
    return service.overview(viewer_id,role)

@router.post('/students/{student_id}/snapshots',response_model=SnapshotResponse,status_code=status.HTTP_201_CREATED)
def create_snapshot(student_id:str,service=Depends(get_dashboard_service),user:User=Depends(get_current_user),authz:AuthorizationService=Depends(get_authorization_service)):
    authz.ensure_student_write_access(user,student_id)
    try:return service.snapshot(student_id)
    except Exception as exc: raise translate(exc)

@router.get('/students/{student_id}/trends',response_model=TrendResponse)
def trends(student_id:str,limit:int=Query(default=30,ge=1,le=365),service=Depends(get_dashboard_service),user:User=Depends(get_current_user),authz:AuthorizationService=Depends(get_authorization_service)):
    authz.ensure_student_read_access(user,student_id)
    try:return service.trends(student_id,limit)
    except Exception as exc: raise translate(exc)
