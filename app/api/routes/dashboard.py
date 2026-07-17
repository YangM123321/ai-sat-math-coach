from fastapi import APIRouter, Depends, Query, status
from app.api.dependencies import get_dashboard_service
from app.core.exceptions import AppError
from app.schemas.dashboard import *
from app.services.dashboard_service import DashboardAccessDeniedError, DashboardStudentDataNotFoundError
router=APIRouter(prefix='/api/v1/dashboard',tags=['teacher-parent-dashboard'])

def translate(exc):
    if isinstance(exc,DashboardAccessDeniedError): return AppError(403,'DASHBOARD_ACCESS_DENIED','The viewer is not authorized to access this student dashboard.')
    if isinstance(exc,DashboardStudentDataNotFoundError): return AppError(404,'DASHBOARD_STUDENT_DATA_NOT_FOUND','No dashboard data is available for this student.')
    return exc
@router.post('/access-grants',response_model=AccessGrantResponse,status_code=status.HTTP_201_CREATED)
def grant_access(request:AccessGrantCreate,service=Depends(get_dashboard_service)):
    return service.grant(request)
@router.get('/students/{student_id}',response_model=StudentDashboardResponse)
def student_dashboard(student_id:str,viewer_id:str=Query(...),role:ViewerRole=Query(...),service=Depends(get_dashboard_service)):
    try:return service.dashboard(student_id,viewer_id,role)
    except Exception as exc: raise translate(exc)
@router.get('/viewers/{viewer_id}/overview',response_model=ViewerOverviewResponse)
def viewer_overview(viewer_id:str,role:ViewerRole|None=Query(default=None),service=Depends(get_dashboard_service)):
    return service.overview(viewer_id,role)
@router.post('/students/{student_id}/snapshots',response_model=SnapshotResponse,status_code=status.HTTP_201_CREATED)
def create_snapshot(student_id:str,viewer_id:str=Query(...),role:ViewerRole=Query(...),service=Depends(get_dashboard_service)):
    try:return service.snapshot(student_id,viewer_id,role)
    except Exception as exc: raise translate(exc)
@router.get('/students/{student_id}/trends',response_model=TrendResponse)
def trends(student_id:str,viewer_id:str=Query(...),role:ViewerRole=Query(...),limit:int=Query(default=30,ge=1,le=365),service=Depends(get_dashboard_service)):
    try:return service.trends(student_id,viewer_id,role,limit)
    except Exception as exc: raise translate(exc)
