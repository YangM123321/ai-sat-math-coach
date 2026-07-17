from abc import ABC,abstractmethod
import re
from app.schemas.diagnostic import *
class DiagnosticProvider(ABC):
    name='abstract'; model_version='abstract'
    @abstractmethod
    async def diagnose(self,r,correct): ...
class RuleBasedProvider(DiagnosticProvider):
    name='rule_based'; model_version='rules-v1.0'
    async def diagnose(self,r,correct):
        domain=r.question.domain or Domain.algebra; skill=r.question.skill or 'unclassified_sat_math_skill'; work=(r.work_text or '').lower()
        if correct:
            return ProviderOutput(correct=True,domain=domain,skill=skill,subskill=r.question.subskill,error_category=ErrorCategory.none,error_subcategory=ErrorSubcategory.none,affected_skill=skill,observed_evidence=[Evidence(statement='The submitted answer is equivalent to the expected answer.',source='student_answer')],root_cause='No error was detected.',explanation='Your final answer matches the expected answer.',recommended_action='Continue with a slightly more challenging problem in the same skill.',model_confidence=.99)
        if not r.work_text or len(r.work_text.strip())<5:
            return ProviderOutput(correct=False,domain=domain,skill=skill,subskill=r.question.subskill,error_category=ErrorCategory.insufficient_evidence,error_subcategory=ErrorSubcategory.unknown,affected_skill=skill,observed_evidence=[Evidence(statement='The final answer does not match the expected answer.',source='student_answer')],root_cause='No reasoning was provided.',explanation='More work is needed to locate the error.',recommended_action='Submit your main calculation steps.',alternative_diagnoses=[ErrorCategory.procedural_error,ErrorCategory.arithmetic_error],model_confidence=.35)
        if re.search(r'17\s*\+\s*5|=\s*22',work) and '2x' in work:
            return ProviderOutput(correct=False,domain=domain,skill=skill,subskill=r.question.subskill,error_category=ErrorCategory.procedural_error,error_subcategory=ErrorSubcategory.inverse_operation_error,affected_skill=skill,error_step=1,observed_evidence=[Evidence(statement='The work changes 2x + 5 = 17 into 2x = 17 + 5.',source='student_work')],root_cause='The constant was moved using the wrong inverse operation.',explanation='You added 5 instead of subtracting 5.',recommended_action='Practice isolating a variable with inverse operations.',model_confidence=.96)
        return ProviderOutput(correct=False,domain=domain,skill=skill,subskill=r.question.subskill,error_category=ErrorCategory.insufficient_evidence,error_subcategory=ErrorSubcategory.unknown,affected_skill=skill,error_step=1,observed_evidence=[Evidence(statement='The written work does not expose one clear error pattern.',source='student_work')],root_cause='The work does not support one unique diagnosis.',explanation='The answer is incorrect, but the cause is uncertain.',recommended_action='Add intermediate steps and name the formula or equation used.',alternative_diagnoses=[ErrorCategory.procedural_error,ErrorCategory.arithmetic_error],model_confidence=.48)
