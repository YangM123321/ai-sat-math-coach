"""Identity schema (Phase 1.5 PR 2B) -- schema only.

No registration, login, JWT issuance, password-hashing service, refresh-
token rotation, or route authorization exists yet. These models only
define where that future behavior will store its data. See
docs/security/THREAT_MODEL.md for the threat model this schema is
designed against.
"""
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.diagnostic import nid


class UserRole(str, Enum):
    """Application roles. The database enforces this exact set via a
    CHECK constraint (ck_users_role on the `users` table) -- the value
    can never be anything else regardless of what application code
    sends. `student` is the least-privileged value and the column
    default, per the fail-closed / secure-defaults principle in
    docs/security/THREAT_MODEL.md. Preventing a *caller* from
    self-assigning `teacher`/`admin` at registration is authentication
    behavior for a later PR; this schema only guarantees the stored
    value itself can never fall outside this set."""
    student = "student"
    teacher = "teacher"
    admin = "admin"


class User(Base):
    """`email` is stored exactly as given -- this model performs no
    normalization (no lowercasing/trimming). `uq_users_email` is therefore
    a case-sensitive uniqueness guarantee at this layer. Normalizing an
    email before it reaches this model (and any case-insensitive
    uniqueness behavior built on top of that) is authentication/service-
    layer behavior for a later PR, not schema."""
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("role IN ('student', 'teacher', 'admin')", name="ck_users_role"),
        Index("ix_users_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("user"))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=UserRole.student.value)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    """Hashed refresh-token record. The raw token value is never stored --
    only a hash of it (token_hash). `replaced_by_id` tracks a rotation
    chain (mirrors LearningPlan.superseded_by_id) so a future auth PR can
    detect reuse of a superseded token as a theft signal."""
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        # Genuinely impossible states, anchored on created_at. A
        # constraint comparing revoked_at directly against expires_at was
        # considered and deliberately omitted: revoking a token either
        # before or after its natural expiry is a legitimate, meaningful
        # state (e.g. an incident-response revocation of an
        # already-expired token), so no ordering between those two
        # columns alone is actually impossible.
        CheckConstraint("expires_at > created_at", name="ck_refresh_tokens_expires_after_created"),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_refresh_tokens_revoked_after_created",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: nid("rtok"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[str | None] = mapped_column(ForeignKey("refresh_tokens.id"), nullable=True)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
