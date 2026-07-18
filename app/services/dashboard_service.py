from datetime import date, datetime, timezone
from app.core.exceptions import UserNotFound
from app.models.dashboard import DashboardAccessGrant, ProgressSnapshot
from app.schemas.dashboard import *

DATA_VERSION='dashboard-v1.0'
class DashboardStudentDataNotFoundError(Exception): pass

class DashboardService:
    """Authorization (who may call which method with which student_id) is
    decided entirely at the route layer (app/api/routes/dashboard.py) via
    the centralized AuthorizationService, before any of these methods
    run -- this service no longer makes its own access decisions (see
    Phase 1.5 PR 4; the removed DashboardAccessDeniedError/_authorize
    used to take a caller-supplied viewer_id/role)."""
    def __init__(self,repository,user_repository): self.repository=repository; self.user_repository=user_repository
    def grant(self,request:AccessGrantCreate,created_by:str):
        if self.user_repository.get_by_id(request.viewer_id) is None: raise UserNotFound(request.viewer_id)
        if self.user_repository.get_by_id(request.student_id) is None: raise UserNotFound(request.student_id)
        item=DashboardAccessGrant(viewer_id=request.viewer_id,student_id=request.student_id,role=request.role.value,active=True,created_by=created_by)
        saved=self.repository.save_grant(item)
        return AccessGrantResponse(id=saved.id,viewer_id=saved.viewer_id,student_id=saved.student_id,role=saved.role,active=saved.active,created_at=saved.created_at)
    def dashboard(self,student_id):
        return self._build(student_id)
    def overview(self,viewer_id,role=None):
        grants=self.repository.grants(viewer_id,role.value if role else None)
        items=[]
        for grant in grants:
            d=self._build(grant.student_id,allow_empty=True)
            items.append(ViewerOverviewItem(student_id=grant.student_id,role=grant.role,risk_level=d.risk_level,overall_mastery=d.metrics.overall_mastery,mastery_confidence=d.metrics.mastery_confidence,active_alert_count=len(d.alerts),next_activity_id=d.next_activity_id))
        return ViewerOverviewResponse(viewer_id=viewer_id,items=items,total=len(items),generated_at=datetime.now(timezone.utc))
    def snapshot(self,student_id):
        dashboard=self.dashboard(student_id)
        item=ProgressSnapshot(student_id=student_id,snapshot_date=date.today().isoformat(),overall_mastery=dashboard.metrics.overall_mastery,mastery_confidence=dashboard.metrics.mastery_confidence,diagnostic_accuracy=dashboard.metrics.diagnostic_accuracy,plan_completion_rate=dashboard.metrics.active_plan_completion_rate,tutor_sessions_completed=dashboard.metrics.completed_tutor_sessions,weak_skills=[x.model_dump() for x in dashboard.weak_skills],strengths=[x.model_dump() for x in dashboard.strengths],generated_by=DATA_VERSION)
        return self._snapshot_response(self.repository.save_snapshot(item))
    def trends(self,student_id,limit):
        return TrendResponse(student_id=student_id,snapshots=[self._snapshot_response(x) for x in self.repository.snapshots(student_id,limit)])
    def _build(self,student_id,allow_empty=False):
        masteries=self.repository.masteries(student_id); total,correct=self.repository.diagnostic_counts(student_id); plan=self.repository.active_plan(student_id); tutor_completed=self.repository.completed_tutor_sessions(student_id)
        if not masteries and total==0 and not plan and not allow_empty: raise DashboardStudentDataNotFoundError(student_id)
        insights=[SkillInsight(skill_code=m.skill.code,skill_name=m.skill.name,domain=m.skill.domain,mastery_score=round(m.mastery_score,3),confidence=round(m.confidence,3),attempt_count=m.attempt_count) for m in masteries]
        strengths=sorted([x for x in insights if x.mastery_score>=.75],key=lambda x:-x.mastery_score)[:5]
        weak=sorted([x for x in insights if x.mastery_score<.6],key=lambda x:(x.mastery_score,-x.confidence))[:5]
        overall=round(sum(x.mastery_score for x in insights)/len(insights),3) if insights else .5
        conf=round(sum(x.confidence for x in insights)/len(insights),3) if insights else 0.0
        accuracy=round(correct/total,3) if total else None
        activities=list(plan.activities) if plan else []
        completed=sum(1 for a in activities if a.status=='completed')
        completion=round(completed/len(activities),3) if activities else None
        pending=sorted([a for a in activities if a.status in {'pending','in_progress'}],key=lambda a:(a.scheduled_date,a.sequence))
        alerts=[]
        if conf<.35: alerts.append(DashboardAlert(code='LOW_EVIDENCE_CONFIDENCE',severity='medium',title='Limited learning evidence',explanation='The mastery estimate is based on limited or uncertain evidence.',recommended_action='Assign a short diagnostic checkpoint before making high-stakes decisions.'))
        if weak: alerts.append(DashboardAlert(code='WEAK_SKILLS',severity='high' if weak[0].mastery_score<.35 else 'medium',title='Skills need intervention',explanation=f'{len(weak)} tracked skill(s) are below the mastery threshold.',recommended_action=f'Review {weak[0].skill_name} and confirm prerequisite understanding.'))
        if plan and completion is not None and completion<.25: alerts.append(DashboardAlert(code='LOW_PLAN_COMPLETION',severity='medium',title='Learning plan progress is low',explanation='Few activities in the active plan are complete.',recommended_action='Check schedule barriers and reduce the next study block if necessary.'))
        risk=RiskLevel.high if any(a.severity==RiskLevel.high for a in alerts) else RiskLevel.medium if alerts else RiskLevel.low
        return StudentDashboardResponse(student_id=student_id,risk_level=risk,metrics=DashboardMetrics(overall_mastery=overall,mastery_confidence=conf,diagnostic_accuracy=accuracy,active_plan_completion_rate=completion,completed_tutor_sessions=tutor_completed,total_diagnostics=total),strengths=strengths,weak_skills=weak,active_plan_id=plan.id if plan else None,next_activity_id=pending[0].id if pending else None,alerts=alerts,generated_at=datetime.now(timezone.utc),data_version=DATA_VERSION)
    @staticmethod
    def _snapshot_response(x):
        return SnapshotResponse(id=x.id,student_id=x.student_id,snapshot_date=x.snapshot_date,overall_mastery=x.overall_mastery,mastery_confidence=x.mastery_confidence,diagnostic_accuracy=x.diagnostic_accuracy,plan_completion_rate=x.plan_completion_rate,tutor_sessions_completed=x.tutor_sessions_completed,weak_skills=x.weak_skills,strengths=x.strengths,created_at=x.created_at)
