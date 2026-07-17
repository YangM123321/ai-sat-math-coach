from app.schemas.diagnostic import DiagnosticRequest,ProviderOutput,ErrorCategory
class ConfidenceService:
    def __init__(self,threshold=.60): self.threshold=threshold
    def calculate(self,r:DiagnosticRequest,o:ProviderOutput):
        score=.50; adj={}
        def ap(k,v):
            nonlocal score; score+=v; adj[k]=v
        ap('high_model_confidence',.15) if o.model_confidence>=.85 else ap('low_model_confidence',-.10) if o.model_confidence<.60 else None
        ap('usable_student_work',.10) if r.work_text and len(r.work_text.strip())>=15 else ap('missing_or_minimal_student_work',-.20)
        if r.question.official_explanation: ap('official_explanation_available',.10)
        if r.question.domain and r.question.skill: ap('domain_and_skill_pre_labeled',.05)
        if o.observed_evidence: ap('evidence_cited',.05)
        if len(o.alternative_diagnoses)>=2: ap('multiple_plausible_diagnoses',-.15)
        if o.error_category==ErrorCategory.insufficient_evidence: ap('insufficient_evidence',-.15)
        score=round(max(0,min(1,score)),2)
        reason=None
        if score<self.threshold: reason='Confidence is below the human-review threshold.'
        elif o.error_category==ErrorCategory.insufficient_evidence: reason='The evidence is insufficient for a reliable diagnosis.'
        elif len(o.alternative_diagnoses)>=2: reason='Multiple diagnoses are similarly plausible.'
        return score,{'base_score':.50,'adjustments':adj,'final_score':score},reason is not None,reason
