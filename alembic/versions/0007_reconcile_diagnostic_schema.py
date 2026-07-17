"""Reconcile student_attempts, diagnostic_results, diagnostic_feedback, and
tutor_sessions with the current SQLAlchemy models.

Revision ID: 0007_reconcile_diagnostic_schema
Revises: 0006_level6_evaluation_loop

Background
----------
Migration 0001 created student_attempts / diagnostic_results /
diagnostic_feedback with many discrete columns. The current ORM models
(app/models/diagnostic.py) instead use single JSON columns
(question_data / payload / data). Migration 0004 is also missing two
indexes tutor_sessions declares (skill_id, learning_activity_id). This
migration reconciles both without touching 0001-0006.

Field mapping (see ai-sat-math-coach Task 4 discussion for full rationale)
---------------------------------------------------------------------------
student_attempts.question_data (matches app.schemas.diagnostic.QuestionInput):
    question_id, question_text, correct_answer, answer_choices,
    official_explanation, domain<-declared_domain, skill<-declared_skill,
    subskill<-declared_subskill, difficulty
    -> fully lossless in both directions.

diagnostic_results.payload (matches app.schemas.diagnostic.ProviderOutput):
    correct, domain, skill, subskill, error_category, error_subcategory,
    affected_skill, error_step, observed_evidence, root_cause, explanation,
    recommended_action, alternative_diagnoses
    -> fully lossless in both directions.
    model_confidence: NOT sourced from the old `confidence` column.
    `confidence` is a separately-computed composite score
    (app/services/confidence_service.py blends model_confidence with five
    other signals starting from a 0.50 base) -- it is not the same value
    as the provider's self-reported model_confidence, which the old schema
    never persisted anywhere. Per approved design, legacy rows get
    payload["model_confidence"] = None. ProviderOutput.model_confidence
    itself stays a required float (the strict provider contract is
    unchanged); reading this null back out goes through the separate,
    read-only app.schemas.diagnostic.StoredDiagnosticPayload schema, which
    relaxes only this one field. This is an explicit "unknown for this
    legacy row" marker, not an invented number and not a copy of
    `confidence`. `confidence` / `confidence_breakdown` are left untouched.
    model_version and raw_model_output have no home in the new model at
    all; their *exact original values* are preserved in the
    diagnostic_results_legacy_archive table created by this migration
    (see below) rather than approximated or dropped.

diagnostic_feedback.data (matches app.schemas.diagnostic.FeedbackRequest):
    reviewer_id, reviewer_type, is_accurate, corrected_error_category,
    corrected_error_subcategory, feedback_text
    -> fully lossless in both directions.

diagnostic_results_legacy_archive:
    A migration-owned table (diagnostic_result_id, model_version,
    raw_model_output, original_confidence) populated during upgrade with
    the exact pre-migration values, before the source columns are dropped.
    It exists purely to make downgrade() exact for pre-migration rows; it
    is dropped again at the end of downgrade(). Rows created *after* this
    migration have no archive entry (they never had model_version /
    raw_model_output at all), so downgrade restores NULL for them -- an
    accurate statement about their history, not a placeholder.

Downgrade limitations (explicit, not hidden)
---------------------------------------------
- student_attempts and diagnostic_feedback downgrade exactly -- every
  discrete column is 100% reconstructible from the JSON blob.
- diagnostic_results downgrades exactly for every column except
  model_version/raw_model_output on rows created after this migration
  (no history exists for them -> NULL, not fabricated).
- All re-added legacy columns are restored as NULLABLE on downgrade
  rather than re-asserting their original NOT NULL constraints, so
  downgrade can never fail on a row shaped only by the new schema.
- The diagnostic_results.attempt_id uniqueness cleanup (see below) is
  fully symmetric on PostgreSQL. It is a no-op on other dialects in both
  directions.

Row processing is batched (keyset pagination on the primary key) rather
than loading full tables into memory, since these tables are not assumed
to be small in every environment.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_reconcile_diagnostic_schema"
down_revision = "0006_level6_evaluation_loop"
branch_labels = None
depends_on = None

BATCH_SIZE = 500


def _iter_batches(bind, table, batch_size=BATCH_SIZE):
    """Yield rows ordered by primary key in fixed-size batches (keyset pagination)."""
    last_id = ""
    while True:
        stmt = sa.select(table).where(table.c.id > last_id).order_by(table.c.id).limit(batch_size)
        rows = bind.execute(stmt).mappings().all()
        if not rows:
            return
        yield rows
        if len(rows) < batch_size:
            return
        last_id = rows[-1]["id"]


# ---------------------------------------------------------------------------
# student_attempts
# ---------------------------------------------------------------------------

_student_attempts_cols = sa.table(
    "student_attempts",
    sa.column("id", sa.String(32)),
    sa.column("question_id", sa.String(128)),
    sa.column("question_text", sa.Text()),
    sa.column("correct_answer", sa.Text()),
    sa.column("answer_choices", sa.JSON()),
    sa.column("official_explanation", sa.Text()),
    sa.column("declared_domain", sa.String(64)),
    sa.column("declared_skill", sa.String(128)),
    sa.column("declared_subskill", sa.String(128)),
    sa.column("difficulty", sa.String(16)),
    sa.column("question_data", sa.JSON()),
)


def _populate_student_attempts_question_data(bind):
    for batch in _iter_batches(bind, _student_attempts_cols):
        for row in batch:
            question_data = {
                "question_id": row["question_id"],
                "question_text": row["question_text"],
                "correct_answer": row["correct_answer"],
                "answer_choices": row["answer_choices"],
                "official_explanation": row["official_explanation"],
                "domain": row["declared_domain"],
                "skill": row["declared_skill"],
                "subskill": row["declared_subskill"],
                "difficulty": row["difficulty"],
            }
            bind.execute(
                _student_attempts_cols.update()
                .where(_student_attempts_cols.c.id == row["id"])
                .values(question_data=question_data)
            )


def _restore_student_attempts_columns(bind):
    for batch in _iter_batches(bind, _student_attempts_cols):
        for row in batch:
            qd = row["question_data"] or {}
            bind.execute(
                _student_attempts_cols.update()
                .where(_student_attempts_cols.c.id == row["id"])
                .values(
                    question_id=qd.get("question_id"),
                    answer_choices=qd.get("answer_choices"),
                    official_explanation=qd.get("official_explanation"),
                    declared_domain=qd.get("domain"),
                    declared_skill=qd.get("skill"),
                    declared_subskill=qd.get("subskill"),
                    difficulty=qd.get("difficulty"),
                )
            )


# ---------------------------------------------------------------------------
# diagnostic_results
# ---------------------------------------------------------------------------

_diagnostic_results_cols = sa.table(
    "diagnostic_results",
    sa.column("id", sa.String(32)),
    sa.column("correct", sa.Boolean()),
    sa.column("domain", sa.String(64)),
    sa.column("skill", sa.String(128)),
    sa.column("subskill", sa.String(128)),
    sa.column("error_category", sa.String(64)),
    sa.column("error_subcategory", sa.String(64)),
    sa.column("affected_skill", sa.String(128)),
    sa.column("error_step", sa.Integer()),
    sa.column("observed_evidence", sa.JSON()),
    sa.column("root_cause", sa.Text()),
    sa.column("explanation", sa.Text()),
    sa.column("recommended_action", sa.Text()),
    sa.column("alternative_diagnoses", sa.JSON()),
    sa.column("model_version", sa.String(64)),
    sa.column("raw_model_output", sa.JSON()),
    sa.column("confidence", sa.Float()),
    sa.column("payload", sa.JSON()),
)

_archive_cols = sa.table(
    "diagnostic_results_legacy_archive",
    sa.column("diagnostic_result_id", sa.String(32)),
    sa.column("model_version", sa.String(64)),
    sa.column("raw_model_output", sa.JSON()),
    sa.column("original_confidence", sa.Float()),
)


def _populate_diagnostic_results_payload_and_archive(bind):
    for batch in _iter_batches(bind, _diagnostic_results_cols):
        for row in batch:
            payload = {
                "correct": row["correct"],
                "domain": row["domain"],
                "skill": row["skill"],
                "subskill": row["subskill"],
                "error_category": row["error_category"],
                "error_subcategory": row["error_subcategory"],
                "affected_skill": row["affected_skill"],
                "error_step": row["error_step"],
                "observed_evidence": row["observed_evidence"],
                "root_cause": row["root_cause"],
                "explanation": row["explanation"],
                "recommended_action": row["recommended_action"],
                "alternative_diagnoses": row["alternative_diagnoses"],
                # Explicit "unknown for this legacy row" marker. NOT the same
                # concept as `confidence` (see module docstring) -- never
                # backfilled from it.
                "model_confidence": None,
            }
            bind.execute(
                _diagnostic_results_cols.update()
                .where(_diagnostic_results_cols.c.id == row["id"])
                .values(payload=payload)
            )
            bind.execute(
                _archive_cols.insert().values(
                    diagnostic_result_id=row["id"],
                    model_version=row["model_version"],
                    raw_model_output=row["raw_model_output"],
                    original_confidence=row["confidence"],
                )
            )


def _restore_diagnostic_results_columns(bind):
    # _archive_cols' primary key is diagnostic_result_id, not id, so it's
    # paginated directly here rather than via _iter_batches (which assumes
    # an `id` column).
    archive_by_id = {}
    last_id = ""
    while True:
        stmt = (
            sa.select(_archive_cols)
            .where(_archive_cols.c.diagnostic_result_id > last_id)
            .order_by(_archive_cols.c.diagnostic_result_id)
            .limit(BATCH_SIZE)
        )
        rows = bind.execute(stmt).mappings().all()
        if not rows:
            break
        for row in rows:
            archive_by_id[row["diagnostic_result_id"]] = row
        if len(rows) < BATCH_SIZE:
            break
        last_id = rows[-1]["diagnostic_result_id"]

    for batch in _iter_batches(bind, _diagnostic_results_cols):
        for row in batch:
            p = row["payload"] or {}
            archived = archive_by_id.get(row["id"])
            bind.execute(
                _diagnostic_results_cols.update()
                .where(_diagnostic_results_cols.c.id == row["id"])
                .values(
                    correct=p.get("correct"),
                    domain=p.get("domain"),
                    skill=p.get("skill"),
                    subskill=p.get("subskill"),
                    error_category=p.get("error_category"),
                    error_subcategory=p.get("error_subcategory"),
                    affected_skill=p.get("affected_skill"),
                    error_step=p.get("error_step"),
                    observed_evidence=p.get("observed_evidence"),
                    root_cause=p.get("root_cause"),
                    explanation=p.get("explanation"),
                    recommended_action=p.get("recommended_action"),
                    alternative_diagnoses=p.get("alternative_diagnoses"),
                    # Exact original values for pre-migration rows; explicit
                    # NULL (not a placeholder) for rows that never had them.
                    model_version=archived["model_version"] if archived else None,
                    raw_model_output=archived["raw_model_output"] if archived else None,
                )
            )


# ---------------------------------------------------------------------------
# diagnostic_feedback
# ---------------------------------------------------------------------------

_diagnostic_feedback_cols = sa.table(
    "diagnostic_feedback",
    sa.column("id", sa.String(32)),
    sa.column("reviewer_id", sa.String(128)),
    sa.column("reviewer_type", sa.String(32)),
    sa.column("is_accurate", sa.Boolean()),
    sa.column("corrected_error_category", sa.String(64)),
    sa.column("corrected_error_subcategory", sa.String(64)),
    sa.column("feedback_text", sa.Text()),
    sa.column("data", sa.JSON()),
)


def _populate_diagnostic_feedback_data(bind):
    for batch in _iter_batches(bind, _diagnostic_feedback_cols):
        for row in batch:
            data = {
                "reviewer_id": row["reviewer_id"],
                "reviewer_type": row["reviewer_type"],
                "is_accurate": row["is_accurate"],
                "corrected_error_category": row["corrected_error_category"],
                "corrected_error_subcategory": row["corrected_error_subcategory"],
                "feedback_text": row["feedback_text"],
            }
            bind.execute(
                _diagnostic_feedback_cols.update()
                .where(_diagnostic_feedback_cols.c.id == row["id"])
                .values(data=data)
            )


def _restore_diagnostic_feedback_columns(bind):
    for batch in _iter_batches(bind, _diagnostic_feedback_cols):
        for row in batch:
            d = row["data"] or {}
            bind.execute(
                _diagnostic_feedback_cols.update()
                .where(_diagnostic_feedback_cols.c.id == row["id"])
                .values(
                    reviewer_id=d.get("reviewer_id"),
                    reviewer_type=d.get("reviewer_type"),
                    is_accurate=d.get("is_accurate"),
                    corrected_error_category=d.get("corrected_error_category"),
                    corrected_error_subcategory=d.get("corrected_error_subcategory"),
                    feedback_text=d.get("feedback_text"),
                )
            )


# ---------------------------------------------------------------------------
# diagnostic_results.attempt_id uniqueness cleanup (PostgreSQL only; see
# module docstring -- this artifact was confirmed empirically to exist only
# on PostgreSQL, produced by op.create_table's column-level unique=True kwarg
# plus a separately created named index in migration 0001)
# ---------------------------------------------------------------------------

def _fix_diagnostic_results_attempt_id_uniqueness(bind):
    if bind.dialect.name != "postgresql":
        return
    inspector = sa.inspect(bind)
    indexes = {ix["name"]: ix for ix in inspector.get_indexes("diagnostic_results")}
    unique_constraints = {uc["name"]: uc for uc in inspector.get_unique_constraints("diagnostic_results")}

    plain_index = indexes.get("ix_diagnostic_results_attempt_id")
    unique_constraint = unique_constraints.get("diagnostic_results_attempt_id_key")

    if plain_index is None or plain_index["unique"] is not False or plain_index["column_names"] != ["attempt_id"]:
        raise RuntimeError(
            "Expected a non-unique index 'ix_diagnostic_results_attempt_id' on "
            f"diagnostic_results(attempt_id); found {plain_index!r}. Refusing to "
            "proceed with an unexpected schema state -- inspect manually before retrying."
        )
    if unique_constraint is None or unique_constraint["column_names"] != ["attempt_id"]:
        raise RuntimeError(
            "Expected a unique constraint 'diagnostic_results_attempt_id_key' on "
            f"diagnostic_results(attempt_id); found {unique_constraint!r}. Refusing "
            "to proceed with an unexpected schema state -- inspect manually before retrying."
        )

    op.drop_index("ix_diagnostic_results_attempt_id", table_name="diagnostic_results")
    op.drop_constraint("diagnostic_results_attempt_id_key", "diagnostic_results", type_="unique")
    op.create_index("ix_diagnostic_results_attempt_id", "diagnostic_results", ["attempt_id"], unique=True)


def _restore_diagnostic_results_attempt_id_uniqueness(bind):
    if bind.dialect.name != "postgresql":
        return
    op.drop_index("ix_diagnostic_results_attempt_id", table_name="diagnostic_results")
    op.create_index("ix_diagnostic_results_attempt_id", "diagnostic_results", ["attempt_id"], unique=False)
    op.create_unique_constraint("diagnostic_results_attempt_id_key", "diagnostic_results", ["attempt_id"])


# ---------------------------------------------------------------------------
# upgrade / downgrade
# ---------------------------------------------------------------------------

def upgrade():
    bind = op.get_bind()

    # --- student_attempts ---------------------------------------------
    op.add_column("student_attempts", sa.Column("question_data", sa.JSON(), nullable=True))
    _populate_student_attempts_question_data(bind)
    with op.batch_alter_table("student_attempts") as batch_op:
        batch_op.alter_column("question_data", nullable=False)
        batch_op.drop_column("question_id")
        batch_op.drop_column("answer_choices")
        batch_op.drop_column("official_explanation")
        batch_op.drop_column("declared_domain")
        batch_op.drop_column("declared_skill")
        batch_op.drop_column("declared_subskill")
        batch_op.drop_column("difficulty")

    # --- diagnostic_results ---------------------------------------------
    op.create_table(
        "diagnostic_results_legacy_archive",
        sa.Column("diagnostic_result_id", sa.String(32), primary_key=True),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("raw_model_output", sa.JSON(), nullable=False),
        sa.Column("original_confidence", sa.Float(), nullable=False),
    )
    op.add_column("diagnostic_results", sa.Column("payload", sa.JSON(), nullable=True))
    _populate_diagnostic_results_payload_and_archive(bind)
    _fix_diagnostic_results_attempt_id_uniqueness(bind)
    with op.batch_alter_table("diagnostic_results") as batch_op:
        batch_op.alter_column("payload", nullable=False)
        batch_op.drop_column("correct")
        batch_op.drop_column("domain")
        batch_op.drop_column("skill")
        batch_op.drop_column("subskill")
        batch_op.drop_column("error_category")
        batch_op.drop_column("error_subcategory")
        batch_op.drop_column("affected_skill")
        batch_op.drop_column("error_step")
        batch_op.drop_column("observed_evidence")
        batch_op.drop_column("root_cause")
        batch_op.drop_column("explanation")
        batch_op.drop_column("recommended_action")
        batch_op.drop_column("alternative_diagnoses")
        batch_op.drop_column("model_version")
        batch_op.drop_column("raw_model_output")

    # --- diagnostic_feedback ---------------------------------------------
    op.add_column("diagnostic_feedback", sa.Column("data", sa.JSON(), nullable=True))
    _populate_diagnostic_feedback_data(bind)
    with op.batch_alter_table("diagnostic_feedback") as batch_op:
        batch_op.alter_column("data", nullable=False)
        batch_op.drop_column("reviewer_id")
        batch_op.drop_column("reviewer_type")
        batch_op.drop_column("is_accurate")
        batch_op.drop_column("corrected_error_category")
        batch_op.drop_column("corrected_error_subcategory")
        batch_op.drop_column("feedback_text")

    # --- tutor_sessions (index-only, no data involved) --------------------
    op.create_index("ix_tutor_sessions_skill_id", "tutor_sessions", ["skill_id"])
    op.create_index("ix_tutor_sessions_learning_activity_id", "tutor_sessions", ["learning_activity_id"])


def downgrade():
    bind = op.get_bind()

    # --- tutor_sessions ---------------------------------------------------
    op.drop_index("ix_tutor_sessions_learning_activity_id", table_name="tutor_sessions")
    op.drop_index("ix_tutor_sessions_skill_id", table_name="tutor_sessions")

    # --- diagnostic_feedback ---------------------------------------------
    with op.batch_alter_table("diagnostic_feedback") as batch_op:
        batch_op.add_column(sa.Column("reviewer_id", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("reviewer_type", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("is_accurate", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("corrected_error_category", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("corrected_error_subcategory", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("feedback_text", sa.Text(), nullable=True))
    _restore_diagnostic_feedback_columns(bind)
    with op.batch_alter_table("diagnostic_feedback") as batch_op:
        batch_op.drop_column("data")

    # --- diagnostic_results ---------------------------------------------
    with op.batch_alter_table("diagnostic_results") as batch_op:
        batch_op.add_column(sa.Column("correct", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("domain", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("skill", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("subskill", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("error_category", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("error_subcategory", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("affected_skill", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("error_step", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("observed_evidence", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("root_cause", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("explanation", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("recommended_action", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("alternative_diagnoses", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("model_version", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("raw_model_output", sa.JSON(), nullable=True))
    _restore_diagnostic_results_columns(bind)
    _restore_diagnostic_results_attempt_id_uniqueness(bind)
    with op.batch_alter_table("diagnostic_results") as batch_op:
        batch_op.drop_column("payload")
    op.drop_table("diagnostic_results_legacy_archive")

    # --- student_attempts ---------------------------------------------
    with op.batch_alter_table("student_attempts") as batch_op:
        batch_op.add_column(sa.Column("question_id", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("answer_choices", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("official_explanation", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("declared_domain", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("declared_skill", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("declared_subskill", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("difficulty", sa.String(16), nullable=True))
    _restore_student_attempts_columns(bind)
    with op.batch_alter_table("student_attempts") as batch_op:
        batch_op.drop_column("question_data")
