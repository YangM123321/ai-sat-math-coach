from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator

class Domain(str,Enum):
    algebra='algebra'; advanced_math='advanced_math'; problem_solving_and_data_analysis='problem_solving_and_data_analysis'; geometry_and_trigonometry='geometry_and_trigonometry'; unknown='unknown'
class ErrorCategory(str,Enum):
    none='none'; conceptual_misunderstanding='conceptual_misunderstanding'; equation_setup_error='equation_setup_error'; strategy_selection_error='strategy_selection_error'; procedural_error='procedural_error'; arithmetic_error='arithmetic_error'; interpretation_error='interpretation_error'; formula_recall_error='formula_recall_error'; visual_interpretation_error='visual_interpretation_error'; incomplete_reasoning='incomplete_reasoning'; insufficient_evidence='insufficient_evidence'
class ErrorSubcategory(str,Enum):
    none='none'; inverse_operation_error='inverse_operation_error'; sign_error='sign_error'; distribution_error='distribution_error'; combining_unlike_terms='combining_unlike_terms'; fraction_operation_error='fraction_operation_error'; verbal_translation_error='verbal_translation_error'; wrong_formula='wrong_formula'; solved_wrong_quantity='solved_wrong_quantity'; omitted_solution='omitted_solution'; missing_unit='missing_unit'; unknown='unknown'
class QuestionInput(BaseModel):
    question_id:str|None=None
    question_text:str=Field(min_length=1)
    correct_answer:str=Field(min_length=1)
    answer_choices:list[str]|None=None
    official_explanation:str|None=None
    domain:Domain|None=None
    skill:str|None=None
    subskill:str|None=None
    difficulty:str|None=Field(None,pattern='^(easy|medium|hard)$')
    @field_validator('answer_choices')
    @classmethod
    def unique(cls,v):
        if v and len(v)!=len(set(v)): raise ValueError('answer_choices must be unique')
        return v
class DiagnosticRequest(BaseModel):
    student_id:str=Field(min_length=1)
    question:QuestionInput
    student_answer:str=Field(min_length=1)
    work_text:str|None=Field(None,max_length=10000)
    student_confidence:int|None=Field(None,ge=1,le=5)
    time_spent_seconds:int|None=Field(None,ge=0,le=86400)
class Evidence(BaseModel):
    statement:str
    source:str=Field(pattern='^(question|student_answer|student_work|official_solution)$')
class ProviderOutput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    correct:bool
    domain:Domain
    skill:str
    subskill:str|None=None
    error_category:ErrorCategory
    error_subcategory:ErrorSubcategory
    affected_skill:str
    error_step:int|None=Field(None,ge=1)
    observed_evidence:list[Evidence]=[]
    root_cause:str
    explanation:str
    recommended_action:str
    alternative_diagnoses:list[ErrorCategory]=[]
    model_confidence:float=Field(ge=0,le=1)
class StoredDiagnosticPayload(ProviderOutput):
    """Same shape as ProviderOutput, for reading already-persisted
    diagnostic_results.payload data. model_confidence is the only relaxed
    field: legacy rows migrated by 0007_reconcile_diagnostic_schema have no
    historical value for it (see that migration's docstring) and store JSON
    null. Never used to validate fresh provider output -- new diagnoses are
    always validated against the strict ProviderOutput at the provider
    boundary in DiagnosticService.create()."""
    model_confidence:float|None=Field(None,ge=0,le=1)
class ConfidenceBreakdown(BaseModel):
    base_score:float
    adjustments:dict[str,float]
    final_score:float
class DiagnosticResponse(BaseModel):
    diagnostic_id:str; attempt_id:str; student_id:str; correct:bool; domain:Domain; skill:str; subskill:str|None
    error_category:ErrorCategory; error_subcategory:ErrorSubcategory; affected_skill:str; error_step:int|None
    observed_evidence:list[Evidence]; root_cause:str; explanation:str; recommended_action:str
    confidence:float; confidence_breakdown:ConfidenceBreakdown; requires_human_review:bool; review_reason:str|None
    provider:str; prompt_version:str; created_at:datetime
class DiagnosticListResponse(BaseModel):
    items:list[DiagnosticResponse]; total:int
class FeedbackRequest(BaseModel):
    # reviewer_id/reviewer_type are NOT accepted from the caller (Phase
    # 1.5 PR 4) -- the service derives them from the authenticated
    # principal (app/api/dependencies.py::get_current_user), never from
    # the request body.
    model_config=ConfigDict(extra='forbid')
    is_accurate:bool
    corrected_error_category:ErrorCategory|None=None; corrected_error_subcategory:ErrorSubcategory|None=None; feedback_text:str|None=Field(None,max_length=2000)
class FeedbackResponse(BaseModel):
    feedback_id:str; diagnostic_id:str; accepted:bool
