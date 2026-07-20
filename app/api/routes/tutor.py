from fastapi import APIRouter, Depends, status
from app.api.dependencies import get_authorization_service, get_current_user, get_tutor_service, rate_limit_api_expensive, rate_limit_api_read, rate_limit_api_write
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.tutor import *
from app.services.authorization_service import AuthorizationService
from app.services.tutor_service import *
router=APIRouter(prefix='/api/v1',tags=['ai-tutor'])

def translate(exc):
    if isinstance(exc,TutorSessionNotFoundError): return AppError(404,'TUTOR_SESSION_NOT_FOUND','The tutor session does not exist.')
    if isinstance(exc,TutorSkillNotFoundError): return AppError(404,'TUTOR_SKILL_NOT_FOUND','The requested skill does not exist.')
    if isinstance(exc,TutorSessionClosedError): return AppError(409,'TUTOR_SESSION_CLOSED','The tutor session is no longer active.')
    return exc

@router.post('/tutor/sessions',response_model=TutorSessionResponse,status_code=status.HTTP_201_CREATED,dependencies=[Depends(rate_limit_api_expensive)])
def create_session(request:TutorSessionCreate,service=Depends(get_tutor_service),user:User=Depends(get_current_user),authz:AuthorizationService=Depends(get_authorization_service)):
    authz.ensure_student_write_access(user,request.student_id)
    try:return service.create(request)
    except Exception as exc: raise translate(exc)

@router.get('/tutor/sessions/{session_id}',response_model=TutorSessionResponse,dependencies=[Depends(rate_limit_api_read)])
def get_session(session_id:str,service=Depends(get_tutor_service),user:User=Depends(get_current_user),authz:AuthorizationService=Depends(get_authorization_service)):
    try:result=service.get(session_id)
    except Exception as exc: raise translate(exc)
    authz.ensure_student_read_access(user,result.student_id)
    return result

@router.post('/tutor/sessions/{session_id}/messages',response_model=TutorSessionResponse,dependencies=[Depends(rate_limit_api_expensive)])
def send_message(session_id:str,request:TutorMessageCreate,service=Depends(get_tutor_service),user:User=Depends(get_current_user),authz:AuthorizationService=Depends(get_authorization_service)):
    try:existing=service.get(session_id)
    except Exception as exc: raise translate(exc)
    authz.ensure_student_write_access(user,existing.student_id)
    try:return service.send(session_id,request)
    except Exception as exc: raise translate(exc)

@router.post('/tutor/sessions/{session_id}/complete',response_model=TutorSessionResponse,dependencies=[Depends(rate_limit_api_write)])
def complete_session(session_id:str,request:TutorSessionComplete,service=Depends(get_tutor_service),user:User=Depends(get_current_user),authz:AuthorizationService=Depends(get_authorization_service)):
    try:existing=service.get(session_id)
    except Exception as exc: raise translate(exc)
    authz.ensure_student_write_access(user,existing.student_id)
    try:return service.complete(session_id,request)
    except Exception as exc: raise translate(exc)

@router.post('/tutor/sessions/{session_id}/feedback',status_code=201,dependencies=[Depends(rate_limit_api_write)])
def add_feedback(session_id:str,request:TutorFeedbackCreate,service=Depends(get_tutor_service),user:User=Depends(get_current_user),authz:AuthorizationService=Depends(get_authorization_service)):
    try:existing=service.get(session_id)
    except Exception as exc: raise translate(exc)
    authz.ensure_student_write_access(user,existing.student_id)
    try:return service.feedback(session_id,request)
    except Exception as exc: raise translate(exc)
