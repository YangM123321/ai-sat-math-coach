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
