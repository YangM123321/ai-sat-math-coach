from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class TutorSessionStatus(str, Enum):
    active='active'; completed='completed'; abandoned='abandoned'
class TutorRole(str, Enum):
    student='student'; tutor='tutor'; system='system'
class TutorStrategy(str, Enum):
    socratic='socratic'; hint='hint'; explanation='explanation'; reflection='reflection'

class TutorSessionCreate(BaseModel):
    student_id: str = Field(min_length=1,max_length=128)
    skill_code: str = Field(min_length=1,max_length=64)
    learning_activity_id: str|None=None
    problem_text: str = Field(min_length=1,max_length=8000)
    correct_answer: str|None=Field(default=None,max_length=1000)
    student_answer: str|None=Field(default=None,max_length=1000)
    student_work: str|None=Field(default=None,max_length=8000)

class TutorMessageCreate(BaseModel):
    content: str = Field(min_length=1,max_length=4000)

class TutorMessageResponse(BaseModel):
    id:str; role:TutorRole; content:str; strategy:TutorStrategy|None
    sequence:int; created_at:datetime

class TutorSessionResponse(BaseModel):
    id:str; student_id:str; skill_code:str; status:TutorSessionStatus
    problem_text:str; current_step:int; max_hints:int; hints_used:int
    provider:str; policy_version:str; messages:list[TutorMessageResponse]
    created_at:datetime; updated_at:datetime

class TutorSessionComplete(BaseModel):
    reflection: str|None=Field(default=None,max_length=2000)

class TutorFeedbackCreate(BaseModel):
    helpful: bool
    rating: int|None=Field(default=None,ge=1,le=5)
    comment: str|None=Field(default=None,max_length=2000)
