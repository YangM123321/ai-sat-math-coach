from app.core.exceptions import NotFound,InvalidModelOutput
from app.prompts.diagnostic_prompt import PROMPT_VERSION
from app.schemas.diagnostic import *
class DiagnosticService:
    def __init__(self,repo,grader,provider,confidence): self.repo=repo; self.grader=grader; self.provider=provider; self.confidence=confidence
    async def create(self,r):
        correct=self.grader.equivalent(r.student_answer,r.question.correct_answer); a=self.repo.create_attempt(r,correct)
        try: o=await self.provider.diagnose(r,correct)
        except Exception as e: self.repo.db.rollback(); raise InvalidModelOutput(str(e))
        if o.correct!=correct: o=o.model_copy(update={'correct':correct})
        score,breakdown,review,reason=self.confidence.calculate(r,o)
        x=self.repo.create_result(attempt_id=a.id,payload=o.model_dump(mode='json'),confidence=score,confidence_breakdown=breakdown,requires_human_review=review,review_reason=reason,provider=self.provider.name,prompt_version=PROMPT_VERSION)
        return self.to_response(x)
    def to_response(self,x):
        p=StoredDiagnosticPayload.model_validate(x.payload)
        return DiagnosticResponse(diagnostic_id=x.id,attempt_id=x.attempt_id,student_id=x.attempt.student_id,correct=p.correct,domain=p.domain,skill=p.skill,subskill=p.subskill,error_category=p.error_category,error_subcategory=p.error_subcategory,affected_skill=p.affected_skill,error_step=p.error_step,observed_evidence=p.observed_evidence,root_cause=p.root_cause,explanation=p.explanation,recommended_action=p.recommended_action,confidence=x.confidence,confidence_breakdown=ConfidenceBreakdown.model_validate(x.confidence_breakdown),requires_human_review=x.requires_human_review,review_reason=x.review_reason,provider=x.provider,prompt_version=x.prompt_version,created_at=x.created_at)
    def get(self,i):
        x=self.repo.get(i)
        if not x: raise NotFound(i)
        return self.to_response(x)
    def list_student(self,sid,limit,offset):
        xs,total=self.repo.list_student(sid,limit,offset); return DiagnosticListResponse(items=[self.to_response(x) for x in xs],total=total)
    def feedback(self,did,r,reviewer_id,reviewer_type):
        if not self.repo.get(did): raise NotFound(did)
        x=self.repo.feedback(did,r,reviewer_id,reviewer_type); return FeedbackResponse(feedback_id=x.id,diagnostic_id=did,accepted=True)
