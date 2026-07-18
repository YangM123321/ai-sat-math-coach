"""Integration tests for migration 0008 (identity schema).

These require a real, reachable PostgreSQL database, since they verify
PostgreSQL-enforced behavior -- most importantly FK ON DELETE CASCADE,
which app/db/session.py does not enable for SQLite (no
PRAGMA foreign_keys=ON), so it is untestable there. They are skipped
entirely unless MIGRATION_TEST_DATABASE_URL is set, mirroring
tests/test_migration_reconciliation.py exactly.

Run locally against a throwaway PostgreSQL instance, e.g.:
    docker run --rm -d --name identity-test-pg -e POSTGRES_USER=sat \
        -e POSTGRES_PASSWORD=sat -e POSTGRES_DB=sat_coach -p 15556:5432 postgres:16-alpine
    MIGRATION_TEST_DATABASE_URL=postgresql+psycopg://sat:sat@localhost:15556/sat_coach \
        pytest tests/test_identity_migration.py -v
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from alembic import command as alembic_command
from alembic.config import Config

from app.core.config import get_settings

PG_URL = os.environ.get("MIGRATION_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not PG_URL,
    reason="Set MIGRATION_TEST_DATABASE_URL to a reachable PostgreSQL URL to run identity migration tests.",
)

HEAD_REVISION = "0008_identity_schema"


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


def _unique_email(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def test_clean_database_upgrades_to_identity_schema_head(pg_engine):
    cfg = _alembic_config()
    alembic_command.upgrade(cfg, "head")
    with pg_engine.connect() as conn:
        rev = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    assert rev == HEAD_REVISION


def test_resulting_schema_matches_orm_metadata(pg_engine):
    cfg = _alembic_config()
    alembic_command.upgrade(cfg, "head")
    insp = sa.inspect(pg_engine)

    assert {c["name"] for c in insp.get_columns("users")} == {
        "id", "email", "password_hash", "role", "is_active", "disabled_at",
        "is_email_verified", "email_verified_at", "created_at", "updated_at",
    }
    assert {c["name"] for c in insp.get_columns("refresh_tokens")} == {
        "id", "user_id", "token_hash", "created_at", "expires_at", "revoked_at", "replaced_by_id",
    }

    user_unique = {uc["name"] for uc in insp.get_unique_constraints("users")}
    assert "uq_users_email" in user_unique

    token_unique = {uc["name"] for uc in insp.get_unique_constraints("refresh_tokens")}
    assert "uq_refresh_tokens_token_hash" in token_unique

    users_indexes = {ix["name"] for ix in insp.get_indexes("users")}
    assert "ix_users_created_at" in users_indexes

    token_indexes = {ix["name"] for ix in insp.get_indexes("refresh_tokens")}
    assert "ix_refresh_tokens_user_id" in token_indexes

    fks = {fk["name"]: fk for fk in insp.get_foreign_keys("refresh_tokens")}
    user_fk = next(fk for fk in fks.values() if fk["referred_table"] == "users")
    # ondelete reporting is dialect-normalized to upper-case by SQLAlchemy's inspector.
    assert user_fk["options"].get("ondelete") == "CASCADE"


def test_email_uniqueness_enforced_by_database(pg_engine):
    cfg = _alembic_config()
    alembic_command.upgrade(cfg, "head")
    with pg_engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO users (id, email, password_hash, created_at, updated_at) "
                    "VALUES (:id, :email, 'hash', now(), now())"),
            {"id": "user_dup1", "email": "dup@example.com"},
        )
    with pg_engine.connect() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            with conn.begin():
                conn.execute(
                    sa.text("INSERT INTO users (id, email, password_hash, created_at, updated_at) "
                            "VALUES (:id, :email, 'hash', now(), now())"),
                    {"id": "user_dup2", "email": "dup@example.com"},
                )


def test_role_check_constraint_enforced_by_database(pg_engine):
    cfg = _alembic_config()
    alembic_command.upgrade(cfg, "head")
    with pg_engine.connect() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            with conn.begin():
                conn.execute(
                    sa.text("INSERT INTO users (id, email, password_hash, role, created_at, updated_at) "
                            "VALUES (:id, :email, 'hash', 'superadmin', now(), now())"),
                    {"id": "user_bad_role", "email": _unique_email("bad-role")},
                )


def test_deleting_user_cascades_to_refresh_tokens_in_postgres(pg_engine):
    cfg = _alembic_config()
    alembic_command.upgrade(cfg, "head")
    now = datetime.now(timezone.utc)
    with pg_engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO users (id, email, password_hash, created_at, updated_at) "
                    "VALUES (:id, :email, 'hash', now(), now())"),
            {"id": "user_cascade", "email": _unique_email("cascade")},
        )
        conn.execute(
            sa.text(
                "INSERT INTO refresh_tokens (id, user_id, token_hash, created_at, expires_at) "
                "VALUES (:id, :user_id, :token_hash, :created_at, :expires_at)"
            ),
            {
                "id": "rtok_cascade",
                "user_id": "user_cascade",
                "token_hash": "sha256:" + "9" * 64,
                "created_at": now,
                "expires_at": now + timedelta(days=30),
            },
        )
    with pg_engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM users WHERE id = :id"), {"id": "user_cascade"})
    with pg_engine.connect() as conn:
        remaining = conn.execute(
            sa.text("SELECT count(*) FROM refresh_tokens WHERE id = 'rtok_cascade'")
        ).scalar()
    assert remaining == 0


def test_downgrade_drops_identity_tables_cleanly(pg_engine):
    cfg = _alembic_config()
    alembic_command.upgrade(cfg, "head")
    alembic_command.downgrade(cfg, "0007_reconcile_diagnostic_schema")
    insp = sa.inspect(pg_engine)
    assert "users" not in insp.get_table_names()
    assert "refresh_tokens" not in insp.get_table_names()
