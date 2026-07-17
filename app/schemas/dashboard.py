from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class ViewerRole(str,Enum):
    teacher='teacher'; parent='parent'; tutor='tutor'; admin='admin'
class RiskLevel(str,Enum):
    low='low'; medium='medium'; high='high'; unknown='unknown'

class AccessGrantCreate(BaseModel):
    viewer_id:str=Field(min_length=1,max_length=128)
    student_id:str=Field(min_length=1,max_length=128)
    role:ViewerRole
    created_by:str=Field(min_length=1,max_length=128)
class AccessGrantResponse(BaseModel):
    id:str; viewer_id:str; student_id:str; role:ViewerRole; active:bool; created_at:datetime

class SkillInsight(BaseModel):
    skill_code:str; skill_name:str; domain:str; mastery_score:float; confidence:float; attempt_count:int
class DashboardMetrics(BaseModel):
    overall_mastery:float; mastery_confidence:float; diagnostic_accuracy:float|None
    active_plan_completion_rate:float|None; completed_tutor_sessions:int; total_diagnostics:int
class DashboardAlert(BaseModel):
    code:str; severity:RiskLevel; title:str; explanation:str; recommended_action:str
class StudentDashboardResponse(BaseModel):
    student_id:str; risk_level:RiskLevel; metrics:DashboardMetrics
    strengths:list[SkillInsight]; weak_skills:list[SkillInsight]
    active_plan_id:str|None; next_activity_id:str|None; alerts:list[DashboardAlert]
    generated_at:datetime; data_version:str
class ViewerOverviewItem(BaseModel):
    student_id:str; role:ViewerRole; risk_level:RiskLevel; overall_mastery:float
    mastery_confidence:float; active_alert_count:int; next_activity_id:str|None
class ViewerOverviewResponse(BaseModel):
    viewer_id:str; items:list[ViewerOverviewItem]; total:int; generated_at:datetime
class SnapshotResponse(BaseModel):
    id:str; student_id:str; snapshot_date:str; overall_mastery:float; mastery_confidence:float
    diagnostic_accuracy:float|None; plan_completion_rate:float|None; tutor_sessions_completed:int
    weak_skills:list[dict]; strengths:list[dict]; created_at:datetime
class TrendResponse(BaseModel):
    student_id:str; snapshots:list[SnapshotResponse]
