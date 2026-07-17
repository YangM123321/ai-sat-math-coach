"""Unit tests for the ProviderOutput / StoredDiagnosticPayload split (Task 4).

ProviderOutput is the strict provider contract: model_confidence stays a
required float. StoredDiagnosticPayload is a narrow subclass used only to
read already-persisted payload JSON, where model_confidence may be legally
absent for rows migrated from the pre-Task-4 schema (see
alembic/versions/0007_reconcile_diagnostic_schema.py).
"""
import asyncio

import pytest
from pydantic import ValidationError

from app.core.exceptions import InvalidModelOutput
from app.db.session import SessionLocal
from app.repositories.diagnostic_repository import Repository
from app.schemas.diagnostic import (
    DiagnosticRequest,
    DiagnosticResponse,
    ProviderOutput,
    QuestionInput,
    StoredDiagnosticPayload,
)
from app.services.confidence_service import ConfidenceService
from app.services.diagnostic_service import DiagnosticService
from app.services.grading_service import GradingService
from app.services.llm_service import RuleBasedProvider


def _minimal_kwargs(**overrides):
    kwargs = dict(
        correct=True,
        domain="algebra",
        skill="linear_equations",
        error_category="none",
        error_subcategory="none",
        affected_skill="linear_equations",
        root_cause="No error was detected.",
        explanation="Correct.",
        recommended_action="Continue.",
    )
    kwargs.update(overrides)
    return kwargs


# --- ProviderOutput: the strict provider contract ---------------------------

def test_provider_output_rejects_missing_model_confidence():
    with pytest.raises(ValidationError):
        ProviderOutput(**_minimal_kwargs())


def test_provider_output_rejects_explicit_null_model_confidence():
    with pytest.raises(ValidationError):
        ProviderOutput(**_minimal_kwargs(model_confidence=None))


def test_provider_output_accepts_a_real_value():
    p = ProviderOutput(**_minimal_kwargs(model_confidence=0.87))
    assert p.model_confidence == 0.87


def test_provider_output_still_enforces_bounds():
    with pytest.raises(ValidationError):
        ProviderOutput(**_minimal_kwargs(model_confidence=1.5))
    with pytest.raises(ValidationError):
        ProviderOutput(**_minimal_kwargs(model_confidence=-0.1))


def test_other_required_fields_are_unaffected():
    with pytest.raises(ValidationError):
        ProviderOutput(domain="algebra", skill="x", error_category="none", error_subcategory="none", affected_skill="x", root_cause="r", explanation="e", recommended_action="a", model_confidence=0.5)


def test_rule_based_provider_always_supplies_a_real_model_confidence():
    """New rows created via the live provider path must always get a real,
    validated model_confidence -- StoredDiagnosticPayload never enters the
    generation path."""
    provider = RuleBasedProvider()
    request = DiagnosticRequest(
        student_id="stu_1",
        question=QuestionInput(question_text="If 2x + 5 = 17, what is x?", correct_answer="6"),
        student_answer="6",
        work_text="Subtract 5, divide by 2, get 6",
    )
    output = asyncio.run(provider.diagnose(request, correct=True))
    assert isinstance(output, ProviderOutput)
    assert output.model_confidence is not None
    assert 0 <= output.model_confidence <= 1


# --- StoredDiagnosticPayload: relaxed, read-only, legacy-tolerant -----------

def test_stored_diagnostic_payload_accepts_model_confidence_none():
    p = StoredDiagnosticPayload(**_minimal_kwargs(model_confidence=None))
    assert p.model_confidence is None


def test_stored_diagnostic_payload_defaults_to_none_when_omitted():
    p = StoredDiagnosticPayload(**_minimal_kwargs())
    assert p.model_confidence is None


def test_stored_diagnostic_payload_still_enforces_bounds_when_present():
    with pytest.raises(ValidationError):
        StoredDiagnosticPayload(**_minimal_kwargs(model_confidence=1.5))


def test_stored_diagnostic_payload_still_requires_other_fields():
    with pytest.raises(ValidationError):
        StoredDiagnosticPayload(domain="algebra", skill="x", error_category="none", error_subcategory="none", affected_skill="x", root_cause="r", explanation="e", recommended_action="a")


def test_model_confidence_is_not_part_of_the_external_api_response_contract():
    """DiagnosticResponse is what the API actually returns; model_confidence
    is not part of it, so neither schema's shape changes what API callers see."""
    assert "model_confidence" not in DiagnosticResponse.model_fields


# --- Integration: DiagnosticService uses the right schema at each boundary --

class _BrokenProvider:
    """Simulates a buggy future provider that fails to supply a required
    field. Used to prove malformed output still raises InvalidModelOutput
    (via the strict ProviderOutput contract) rather than surfacing as an
    unhandled exception deeper in the service."""
    name = "broken"
    model_version = "broken-v1"

    async def diagnose(self, r, correct):
        return ProviderOutput(**_minimal_kwargs(correct=correct, model_confidence=None))


def _request():
    return DiagnosticRequest(
        student_id="stu_broken",
        question=QuestionInput(question_text="If 2x + 5 = 17, what is x?", correct_answer="6"),
        student_answer="6",
        work_text="Subtract 5, divide by 2, get 6",
    )


def test_invalid_provider_output_raises_invalid_model_output(reset_db):
    """A provider that cannot produce a valid ProviderOutput (e.g. omits
    model_confidence) must fail cleanly at the provider boundary via
    InvalidModelOutput, not crash later with an unhandled TypeError."""
    db = SessionLocal()
    try:
        service = DiagnosticService(Repository(db), GradingService(), _BrokenProvider(), ConfidenceService())
        with pytest.raises(InvalidModelOutput):
            asyncio.run(service.create(_request()))
    finally:
        db.close()


def test_newly_created_diagnostic_uses_strict_provider_contract(reset_db):
    """The live create() path never touches StoredDiagnosticPayload for
    generation -- only RuleBasedProvider's strict ProviderOutput."""
    db = SessionLocal()
    try:
        service = DiagnosticService(Repository(db), GradingService(), RuleBasedProvider(), ConfidenceService())
        response = asyncio.run(service.create(_request()))
        assert response.diagnostic_id
    finally:
        db.close()


def test_migrated_legacy_payload_is_readable_via_to_response(reset_db):
    """Simulates a legacy row (payload shaped by migration 0007, with
    model_confidence=None) and proves DiagnosticService.to_response() can
    still read it, via StoredDiagnosticPayload."""
    db = SessionLocal()
    try:
        repo = Repository(db)
        service = DiagnosticService(repo, GradingService(), RuleBasedProvider(), ConfidenceService())
        request = _request()
        attempt = repo.create_attempt(request, correct=True)
        legacy_payload = _minimal_kwargs(correct=True, model_confidence=None)
        result = repo.create_result(
            attempt_id=attempt.id,
            payload=legacy_payload,
            confidence=0.91,
            confidence_breakdown={"base_score": 0.5, "adjustments": {}, "final_score": 0.91},
            requires_human_review=False,
            review_reason=None,
            provider="rule_based",
            prompt_version="v1",
        )
        response = service.get(result.id)
        assert response.correct is True
        assert response.confidence == 0.91
    finally:
        db.close()
