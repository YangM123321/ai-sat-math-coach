from dataclasses import dataclass
from fastapi import Request
from fastapi.responses import JSONResponse

@dataclass
class AppError(Exception):
    status_code:int
    code:str
    message:str
    details:dict|None=None

class NotFound(AppError):
    def __init__(self, diagnostic_id:str):
        super().__init__(404,'DIAGNOSTIC_NOT_FOUND','The requested diagnostic result does not exist.',{'diagnostic_id':diagnostic_id})
class UnsupportedFile(AppError):
    def __init__(self, content_type:str|None):
        super().__init__(415,'UNSUPPORTED_FILE_TYPE','The uploaded file type is not supported.',{'content_type':content_type})
class FileTooLarge(AppError):
    def __init__(self, maximum_bytes:int):
        super().__init__(413,'FILE_TOO_LARGE','The uploaded file exceeds the maximum allowed size.',{'maximum_bytes':maximum_bytes})
class OCRFailed(AppError):
    def __init__(self):
        super().__init__(422,'OCR_EXTRACTION_FAILED','No production OCR provider is configured for image diagnosis.')
class InvalidModelOutput(AppError):
    def __init__(self, reason:str):
        super().__init__(502,'INVALID_MODEL_OUTPUT','The provider returned invalid structured output.',{'reason':reason})

async def app_error_handler(_:Request, exc:AppError):
    return JSONResponse(status_code=exc.status_code, content={'error':{'code':exc.code,'message':exc.message,'details':exc.details}})

class EvaluationNotFound(AppError):
    def __init__(self, run_id:str):
        super().__init__(404,'EVALUATION_RUN_NOT_FOUND','The requested evaluation run does not exist.',{'run_id':run_id})
class ExperimentNotFound(AppError):
    def __init__(self, experiment_id:str):
        super().__init__(404,'EXPERIMENT_NOT_FOUND','The requested experiment does not exist.',{'experiment_id':experiment_id})

class EmailAlreadyRegistered(AppError):
    def __init__(self, email:str):
        super().__init__(409,'EMAIL_ALREADY_REGISTERED','An account with this email already exists.',{'email':email})
class InvalidCredentials(AppError):
    # Deliberately identical for wrong password, nonexistent email, and a
    # disabled account -- no detail that would let a caller distinguish
    # why a login attempt failed.
    def __init__(self):
        super().__init__(401,'INVALID_CREDENTIALS','Invalid email or password.')
class InvalidToken(AppError):
    # Deliberately identical for a missing/malformed/expired/wrong-issuer/
    # wrong-audience/wrong-type access token, and for a valid token whose
    # user no longer exists or is disabled.
    def __init__(self):
        super().__init__(401,'INVALID_TOKEN','The access token is missing, invalid, or expired.')
class InvalidRefreshToken(AppError):
    def __init__(self):
        super().__init__(401,'INVALID_REFRESH_TOKEN','The refresh token is missing, invalid, expired, or has been revoked.')

class Forbidden(AppError):
    # Phase 1.5 PR 4: the single, consistent 403 used across every domain
    # for "authenticated but not permitted" -- deliberately generic, no
    # detail about which ownership/relationship check failed, so a
    # response never reveals whether a resource exists, who owns it, or
    # why access was denied.
    def __init__(self):
        super().__init__(403,'ACCESS_DENIED','You do not have permission to access this resource.')
class UserNotFound(AppError):
    def __init__(self, user_id:str):
        super().__init__(404,'USER_NOT_FOUND','The referenced user does not exist.',{'user_id':user_id})
