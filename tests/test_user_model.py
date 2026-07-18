"""Model-level tests for the Phase 1.5 identity schema (PR 2B).

Schema only -- there is no registration/login/JWT service yet, so these
tests exercise app.models.user.User/RefreshToken directly against the
SQLite test database (see tests/conftest.py's autouse reset_db fixture).

CHECK and UNIQUE constraints are enforced by SQLite unconditionally, so
they are safely tested here. FK ON DELETE CASCADE is only enforced by
SQLite when PRAGMA foreign_keys=ON is set, which app/db/session.py does
not do -- that enforcement is instead verified against real PostgreSQL
in tests/test_identity_migration.py. The ORM-level cascade tested below
(via session.delete, not raw SQL) is SQLAlchemy's own unit-of-work
behavior and does not depend on that PRAGMA.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.user import RefreshToken, User, UserRole


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_user(db, **overrides):
    defaults = dict(email="Student@Example.com", password_hash="argon2id$fake-hash-value")
    defaults.update(overrides)
    user = User(**defaults)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_user_applies_secure_defaults(db):
    user = _make_user(db)
    assert user.role == UserRole.student.value
    assert user.is_active is True
    assert user.disabled_at is None
    assert user.is_email_verified is False
    assert user.email_verified_at is None
    assert user.created_at is not None
    assert user.updated_at is not None


def test_email_is_stored_exactly_as_given(db):
    """The model performs no normalization -- lowercasing/trimming is
    deferred to the future authentication/service layer, not schema."""
    user = _make_user(db, email="  Student@Example.COM  ")
    assert user.email == "  Student@Example.COM  "


def test_duplicate_email_raises_integrity_error(db):
    _make_user(db, email="dup@example.com")
    db.add(User(email="dup@example.com", password_hash="argon2id$fake-hash-value"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_email_uniqueness_is_case_sensitive_at_this_layer(db):
    """Documents the current schema-only behavior: uq_users_email is a
    case-sensitive constraint, so case-insensitive deduplication must be
    enforced by a future service layer, not assumed from this schema."""
    _make_user(db, email="dup@example.com")
    user = _make_user(db, email="DUP@example.com")
    assert user.email == "DUP@example.com"


def test_invalid_role_raises_integrity_error(db):
    db.add(User(email="bad-role@example.com", password_hash="argon2id$fake-hash-value", role="superadmin"))
    with pytest.raises(IntegrityError):
        db.commit()


@pytest.mark.parametrize("role", [r.value for r in UserRole])
def test_every_declared_role_is_accepted(db, role):
    user = _make_user(db, email=f"{role}@example.com", role=role)
    assert user.role == role


def test_refresh_token_stores_hash_not_raw_token(db):
    user = _make_user(db)
    now = datetime.now(timezone.utc)
    token = RefreshToken(
        user_id=user.id,
        token_hash="sha256:" + "a" * 64,
        expires_at=now + timedelta(days=30),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    assert token.revoked_at is None
    assert not hasattr(token, "token")  # no raw-token attribute exists on the model at all


def test_duplicate_token_hash_raises_integrity_error(db):
    user = _make_user(db)
    now = datetime.now(timezone.utc)
    shared_hash = "sha256:" + "b" * 64
    db.add(RefreshToken(user_id=user.id, token_hash=shared_hash, expires_at=now + timedelta(days=30)))
    db.commit()
    db.add(RefreshToken(user_id=user.id, token_hash=shared_hash, expires_at=now + timedelta(days=30)))
    with pytest.raises(IntegrityError):
        db.commit()


def test_expires_at_at_or_before_created_at_raises_integrity_error(db):
    user = _make_user(db)
    now = datetime.now(timezone.utc)
    db.add(RefreshToken(user_id=user.id, token_hash="sha256:" + "c" * 64, created_at=now, expires_at=now))
    with pytest.raises(IntegrityError):
        db.commit()


def test_revoked_before_created_raises_integrity_error(db):
    user = _make_user(db)
    now = datetime.now(timezone.utc)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash="sha256:" + "d" * 64,
            created_at=now,
            expires_at=now + timedelta(days=30),
            revoked_at=now - timedelta(seconds=1),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_revoked_at_or_after_created_at_is_accepted(db):
    user = _make_user(db)
    now = datetime.now(timezone.utc)
    token = RefreshToken(
        user_id=user.id,
        token_hash="sha256:" + "e" * 64,
        created_at=now,
        expires_at=now + timedelta(days=30),
        revoked_at=now,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    # SQLite round-trips datetimes as naive, so compare values, not tzinfo.
    assert token.revoked_at.replace(tzinfo=None) == now.replace(tzinfo=None)


def test_revoked_after_expires_at_is_accepted(db):
    """Revoking an already-expired token is legitimate (e.g. an
    incident-response sweep) -- see the migration's design notes for why
    no constraint compares revoked_at against expires_at directly."""
    user = _make_user(db)
    now = datetime.now(timezone.utc)
    token = RefreshToken(
        user_id=user.id,
        token_hash="sha256:" + "f" * 64,
        created_at=now,
        expires_at=now + timedelta(seconds=1),
        revoked_at=now + timedelta(days=1),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    assert token.revoked_at > token.expires_at


def test_deleting_user_cascades_to_refresh_tokens_at_orm_level(db):
    user = _make_user(db)
    now = datetime.now(timezone.utc)
    db.add(RefreshToken(user_id=user.id, token_hash="sha256:" + "0" * 64, expires_at=now + timedelta(days=30)))
    db.commit()

    db.delete(user)
    db.commit()

    assert db.query(RefreshToken).count() == 0


def test_replaced_by_id_supports_a_rotation_chain(db):
    user = _make_user(db)
    now = datetime.now(timezone.utc)
    old_token = RefreshToken(
        user_id=user.id, token_hash="sha256:" + "1" * 64, created_at=now, expires_at=now + timedelta(days=30)
    )
    db.add(old_token)
    db.commit()
    db.refresh(old_token)

    new_token = RefreshToken(
        user_id=user.id, token_hash="sha256:" + "2" * 64, created_at=now, expires_at=now + timedelta(days=30)
    )
    db.add(new_token)
    db.commit()
    db.refresh(new_token)

    # Rotation happens strictly after both tokens' created_at.
    rotated_at = now + timedelta(seconds=1)
    old_token.replaced_by_id = new_token.id
    old_token.revoked_at = rotated_at
    db.commit()
    db.refresh(old_token)

    assert old_token.replaced_by_id == new_token.id
