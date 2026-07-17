"""Integration tests for migration 0007 (schema drift reconciliation).

These require a real, reachable PostgreSQL database, since they exercise
actual Alembic upgrade/downgrade cycles and PostgreSQL-specific behavior
(the diagnostic_results.attempt_id uniqueness cleanup only runs on
PostgreSQL). They are skipped entirely unless MIGRATION_TEST_DATABASE_URL
is set -- deliberately a *different* env var than DATABASE_URL, because
tests/conftest.py unconditionally forces DATABASE_URL to SQLite for the
rest of the suite, and these tests must not disturb that.

Run locally against a throwaway PostgreSQL instance, e.g.:
    docker run --rm -d --name migration-test-pg -e POSTGRES_USER=sat \
        -e POSTGRES_PASSWORD=sat -e POSTGRES_DB=sat_coach -p 15555:5432 postgres:16-alpine
    MIGRATION_TEST_DATABASE_URL=postgresql+psycopg://sat:sat@localhost:15555/sat_coach \
        pytest tests/test_migration_reconciliation.py -v
"""
import os
import uuid

import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

PG_URL = os.environ.get("MIGRATION_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not PG_URL,
    reason="Set MIGRATION_TEST_DATABASE_URL to a reachable PostgreSQL URL to run migration reconciliation tests.",
)

HEAD_REVISION = "0007_reconcile_diagnostic_schema"
PRE_FIX_REVISION = "0006_level6_evaluation_loop"


def _alembic_config():
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", PG_URL)
    return cfg


@pytest.fixture
def pg_engine():
    prev_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = PG_URL
    get_settings.cache_clear()
    engine = sa.create_engine(PG_URL)
    with engine.begin() as conn:
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
    try:
        yield engine
    finally:
        engine.dispose()
        if prev_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev_url
        get_settings.cache_clear()


def _unique_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _insert_legacy_rows(engine, attempt_id, diagnostic_id, feedback_id):
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO student_attempts
                    (id, student_id, question_id, question_text, correct_answer, answer_choices,
                     official_explanation, declared_domain, declared_skill, declared_subskill,
                     difficulty, student_answer, work_text, student_confidence, time_spent_seconds,
                     deterministic_correct, created_at)
                VALUES
                    (:id, 'stu_legacy', 'q_100', 'If 2x + 5 = 17, what is x?', '6', '["4","6","8"]',
                     'Subtract 5, divide by 2.', 'algebra', 'linear_equations', 'inverse_operations',
                     'easy', '6', 'work shown', 4, 90, true, now())
                """
            ),
            {"id": attempt_id},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO diagnostic_results
                    (id, attempt_id, correct, domain, skill, subskill, error_category, error_subcategory,
                     affected_skill, error_step, observed_evidence, root_cause, explanation,
                     recommended_action, alternative_diagnoses, confidence, confidence_breakdown,
                     requires_human_review, review_reason, provider, model_version, prompt_version,
                     raw_model_output, created_at)
                VALUES
                    (:id, :attempt_id, true, 'algebra', 'linear_equations', 'inverse_operations', 'none',
                     'none', 'linear_equations', NULL, '[]', 'No error detected.', 'Correct answer.',
                     'Move on.', '[]', 0.91, :confidence_breakdown,
                     false, NULL, 'rule_based', 'rules-v1.0-legacy', 'v1',
                     :raw_model_output, now())
                """
            ).bindparams(
                sa.bindparam("confidence_breakdown", type_=sa.JSON),
                sa.bindparam("raw_model_output", type_=sa.JSON),
            ),
            {
                "id": diagnostic_id,
                "attempt_id": attempt_id,
                "confidence_breakdown": {"base_score": 0.5, "adjustments": {}, "final_score": 0.91},
                "raw_model_output": {"legacy_raw": "original provider blob"},
            },
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO diagnostic_feedback
                    (id, diagnostic_id, reviewer_id, reviewer_type, is_accurate,
                     corrected_error_category, corrected_error_subcategory, feedback_text, created_at)
                VALUES
                    (:id, :diagnostic_id, 'teacher_9', 'teacher', true, NULL, NULL, 'Looks right.', now())
                """
            ),
            {"id": feedback_id, "diagnostic_id": diagnostic_id},
        )


def test_clean_database_upgrades_from_base_through_head(pg_engine):
    cfg = _alembic_config()
    alembic_command.upgrade(cfg, "head")
    with pg_engine.connect() as conn:
        rev = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    assert rev == HEAD_REVISION


def test_resulting_schema_matches_orm_metadata(pg_engine):
    cfg = _alembic_config()
    alembic_command.upgrade(cfg, "head")
    insp = sa.inspect(pg_engine)

    assert {c["name"] for c in insp.get_columns("student_attempts")} == {
        "id", "student_id", "question_text", "correct_answer", "question_data",
        "student_answer", "work_text", "student_confidence", "time_spent_seconds",
        "deterministic_correct", "created_at",
    }
    assert {c["name"] for c in insp.get_columns("diagnostic_results")} == {
        "id", "attempt_id", "payload", "confidence", "confidence_breakdown",
        "requires_human_review", "review_reason", "provider", "prompt_version", "created_at",
    }
    assert {c["name"] for c in insp.get_columns("diagnostic_feedback")} == {
        "id", "diagnostic_id", "data", "created_at",
    }

    tutor_index_names = {ix["name"] for ix in insp.get_indexes("tutor_sessions")}
    assert {"ix_tutor_sessions_skill_id", "ix_tutor_sessions_learning_activity_id"} <= tutor_index_names

    diag_indexes = {ix["name"]: ix for ix in insp.get_indexes("diagnostic_results")}
    assert diag_indexes["ix_diagnostic_results_attempt_id"]["unique"] is True
    # The redundant pre-fix objects must be gone.
    assert "diagnostic_results_attempt_id_key" not in {
        uc["name"] for uc in insp.get_unique_constraints("diagnostic_results")
    }


def test_legacy_rows_migrate_with_correct_json_and_archive_data(pg_engine):
    cfg = _alembic_config()
    alembic_command.upgrade(cfg, PRE_FIX_REVISION)
    attempt_id, diagnostic_id, feedback_id = _unique_id("att"), _unique_id("diag"), _unique_id("fb")
    _insert_legacy_rows(pg_engine, attempt_id, diagnostic_id, feedback_id)

    alembic_command.upgrade(cfg, "head")

    with pg_engine.connect() as conn:
        question_data = conn.execute(
            sa.text("SELECT question_data FROM student_attempts WHERE id=:id"), {"id": attempt_id}
        ).scalar()
        payload = conn.execute(
            sa.text("SELECT payload FROM diagnostic_results WHERE id=:id"), {"id": diagnostic_id}
        ).scalar()
        archived = conn.execute(
            sa.text(
                "SELECT model_version, raw_model_output, original_confidence "
                "FROM diagnostic_results_legacy_archive WHERE diagnostic_result_id=:id"
            ),
            {"id": diagnostic_id},
        ).mappings().first()
        feedback_data = conn.execute(
            sa.text("SELECT data FROM diagnostic_feedback WHERE id=:id"), {"id": feedback_id}
        ).scalar()

    assert question_data == {
        "question_id": "q_100",
        "question_text": "If 2x + 5 = 17, what is x?",
        "correct_answer": "6",
        "answer_choices": ["4", "6", "8"],
        "official_explanation": "Subtract 5, divide by 2.",
        "domain": "algebra",
        "skill": "linear_equations",
        "subskill": "inverse_operations",
        "difficulty": "easy",
    }

    assert payload["correct"] is True
    assert payload["domain"] == "algebra"
    assert payload["error_category"] == "none"
    assert payload["observed_evidence"] == []
    # model_confidence is an explicit "unknown", never backfilled from confidence.
    assert payload["model_confidence"] is None

    assert archived["model_version"] == "rules-v1.0-legacy"
    assert archived["raw_model_output"] == {"legacy_raw": "original provider blob"}
    assert archived["original_confidence"] == pytest.approx(0.91)

    assert feedback_data == {
        "reviewer_id": "teacher_9",
        "reviewer_type": "teacher",
        "is_accurate": True,
        "corrected_error_category": None,
        "corrected_error_subcategory": None,
        "feedback_text": "Looks right.",
    }


def test_migrated_legacy_rows_validate_through_current_pydantic_schemas(pg_engine):
    from pydantic import ValidationError

    from app.schemas.diagnostic import FeedbackRequest, ProviderOutput, QuestionInput, StoredDiagnosticPayload

    cfg = _alembic_config()
    alembic_command.upgrade(cfg, PRE_FIX_REVISION)
    attempt_id, diagnostic_id, feedback_id = _unique_id("att"), _unique_id("diag"), _unique_id("fb")
    _insert_legacy_rows(pg_engine, attempt_id, diagnostic_id, feedback_id)
    alembic_command.upgrade(cfg, "head")

    with pg_engine.connect() as conn:
        question_data = conn.execute(
            sa.text("SELECT question_data FROM student_attempts WHERE id=:id"), {"id": attempt_id}
        ).scalar()
        payload = conn.execute(
            sa.text("SELECT payload FROM diagnostic_results WHERE id=:id"), {"id": diagnostic_id}
        ).scalar()
        feedback_data = conn.execute(
            sa.text("SELECT data FROM diagnostic_feedback WHERE id=:id"), {"id": feedback_id}
        ).scalar()

    QuestionInput.model_validate(question_data)

    # Legacy payload must fail the strict provider contract...
    with pytest.raises(ValidationError):
        ProviderOutput.model_validate(payload)

    # ...but must validate through the read-only, legacy-tolerant schema.
    stored = StoredDiagnosticPayload.model_validate(payload)
    assert stored.model_confidence is None

    FeedbackRequest.model_validate(feedback_data)


def test_application_service_reads_migrated_legacy_row_end_to_end(pg_engine):
    from app.repositories.diagnostic_repository import Repository
    from app.services.confidence_service import ConfidenceService
    from app.services.diagnostic_service import DiagnosticService
    from app.services.grading_service import GradingService
    from app.services.llm_service import RuleBasedProvider

    cfg = _alembic_config()
    alembic_command.upgrade(cfg, PRE_FIX_REVISION)
    attempt_id, diagnostic_id, feedback_id = _unique_id("att"), _unique_id("diag"), _unique_id("fb")
    _insert_legacy_rows(pg_engine, attempt_id, diagnostic_id, feedback_id)
    alembic_command.upgrade(cfg, "head")

    Session = sessionmaker(bind=pg_engine)
    db = Session()
    try:
        service = DiagnosticService(
            Repository(db), GradingService(), RuleBasedProvider(), ConfidenceService()
        )
        response = service.get(diagnostic_id)
        assert response.diagnostic_id == diagnostic_id
        assert response.correct is True
        assert response.confidence == pytest.approx(0.91)
    finally:
        db.close()


def test_application_can_insert_and_read_new_rows_via_current_orm_models(pg_engine):
    from app.models.diagnostic import DiagnosticFeedback, DiagnosticResult, StudentAttempt

    cfg = _alembic_config()
    alembic_command.upgrade(cfg, "head")

    Session = sessionmaker(bind=pg_engine)
    db = Session()
    try:
        attempt = StudentAttempt(
            student_id="stu_new",
            question_text="If 2x + 5 = 17, what is x?",
            correct_answer="6",
            student_answer="6",
            question_data={
                "question_id": None, "question_text": "If 2x + 5 = 17, what is x?",
                "correct_answer": "6", "answer_choices": None, "official_explanation": None,
                "domain": "algebra", "skill": "linear_equations", "subskill": None, "difficulty": None,
            },
            deterministic_correct=True,
        )
        db.add(attempt)
        db.flush()

        result = DiagnosticResult(
            attempt_id=attempt.id,
            payload={
                "correct": True, "domain": "algebra", "skill": "linear_equations", "subskill": None,
                "error_category": "none", "error_subcategory": "none", "affected_skill": "linear_equations",
                "error_step": None, "observed_evidence": [], "root_cause": "None.", "explanation": "Correct.",
                "recommended_action": "Continue.", "alternative_diagnoses": [], "model_confidence": 0.95,
            },
            confidence=0.9,
            confidence_breakdown={"base_score": 0.5, "adjustments": {}, "final_score": 0.9},
            requires_human_review=False,
            provider="rule_based",
            prompt_version="v1",
        )
        db.add(result)
        db.commit()

        fetched = db.get(DiagnosticResult, result.id)
        assert fetched.payload["model_confidence"] == 0.95

        feedback = DiagnosticFeedback(
            diagnostic_id=result.id,
            data={
                "reviewer_id": "t1", "reviewer_type": "teacher", "is_accurate": True,
                "corrected_error_category": None, "corrected_error_subcategory": None, "feedback_text": None,
            },
        )
        db.add(feedback)
        db.commit()
        assert db.get(DiagnosticFeedback, feedback.id).data["reviewer_id"] == "t1"
    finally:
        db.close()


def test_downgrade_restores_legacy_rows_exactly_and_nulls_rows_created_after_migration(pg_engine):
    cfg = _alembic_config()

    # 1. Legacy row, inserted under the pre-fix (0006) schema.
    alembic_command.upgrade(cfg, PRE_FIX_REVISION)
    legacy_attempt_id, legacy_diag_id, legacy_fb_id = _unique_id("att"), _unique_id("diag"), _unique_id("fb")
    _insert_legacy_rows(pg_engine, legacy_attempt_id, legacy_diag_id, legacy_fb_id)

    # 2. Upgrade to head, then insert a genuinely new row that only ever
    #    existed under the new (payload-only) shape.
    alembic_command.upgrade(cfg, "head")
    new_diag_id = _unique_id("diag")
    with pg_engine.begin() as conn:
        new_attempt_id = _unique_id("att")
        conn.execute(
            sa.text(
                "INSERT INTO student_attempts (id, student_id, question_text, correct_answer, "
                "student_answer, question_data, deterministic_correct, created_at) VALUES "
                "(:id, 'stu_new', 'q', '6', '6', '{}', true, now())"
            ),
            {"id": new_attempt_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO diagnostic_results (id, attempt_id, payload, confidence, "
                "confidence_breakdown, requires_human_review, provider, prompt_version, created_at) "
                "VALUES (:id, :attempt_id, :payload, 0.8, :confidence_breakdown, false, 'rule_based', 'v1', now())"
            ).bindparams(
                sa.bindparam("payload", type_=sa.JSON),
                sa.bindparam("confidence_breakdown", type_=sa.JSON),
            ),
            {
                "id": new_diag_id,
                "attempt_id": new_attempt_id,
                "payload": {"correct": True},
                "confidence_breakdown": {},
            },
        )

    # 3. Downgrade back to pre-fix.
    alembic_command.downgrade(cfg, PRE_FIX_REVISION)

    with pg_engine.connect() as conn:
        legacy_attempt = conn.execute(
            sa.text(
                "SELECT question_id, answer_choices, official_explanation, declared_domain, "
                "declared_skill, declared_subskill, difficulty FROM student_attempts WHERE id=:id"
            ),
            {"id": legacy_attempt_id},
        ).mappings().first()
        legacy_result = conn.execute(
            sa.text(
                "SELECT correct, domain, skill, model_version, raw_model_output "
                "FROM diagnostic_results WHERE id=:id"
            ),
            {"id": legacy_diag_id},
        ).mappings().first()
        legacy_feedback = conn.execute(
            sa.text(
                "SELECT reviewer_id, reviewer_type, is_accurate, feedback_text "
                "FROM diagnostic_feedback WHERE id=:id"
            ),
            {"id": legacy_fb_id},
        ).mappings().first()
        new_result = conn.execute(
            sa.text("SELECT correct, model_version, raw_model_output FROM diagnostic_results WHERE id=:id"),
            {"id": new_diag_id},
        ).mappings().first()
        archive_exists = conn.execute(
            sa.text(
                "SELECT to_regclass('public.diagnostic_results_legacy_archive') IS NOT NULL"
            )
        ).scalar()

    # Exactly reversible fields: byte-for-byte restored for the legacy row.
    assert legacy_attempt["question_id"] == "q_100"
    assert legacy_attempt["answer_choices"] == ["4", "6", "8"]
    assert legacy_attempt["official_explanation"] == "Subtract 5, divide by 2."
    assert legacy_attempt["declared_domain"] == "algebra"
    assert legacy_attempt["declared_skill"] == "linear_equations"
    assert legacy_attempt["declared_subskill"] == "inverse_operations"
    assert legacy_attempt["difficulty"] == "easy"

    assert legacy_result["correct"] is True
    assert legacy_result["domain"] == "algebra"
    assert legacy_result["skill"] == "linear_equations"
    # Exact original values, restored from the archive table -- not reconstructed placeholders.
    assert legacy_result["model_version"] == "rules-v1.0-legacy"
    assert legacy_result["raw_model_output"] == {"legacy_raw": "original provider blob"}

    assert legacy_feedback["reviewer_id"] == "teacher_9"
    assert legacy_feedback["reviewer_type"] == "teacher"
    assert legacy_feedback["is_accurate"] is True
    assert legacy_feedback["feedback_text"] == "Looks right."

    # Intentionally irreversible: a row that only ever existed under the new
    # schema has no historical model_version/raw_model_output to restore.
    assert new_result["correct"] is True  # reconstructible from payload -- still correct
    assert new_result["model_version"] is None
    assert new_result["raw_model_output"] is None

    # The archive table is scratch space for this one revision -- it must not
    # leak into the downgraded schema.
    assert archive_exists is False
