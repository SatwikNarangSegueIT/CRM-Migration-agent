"""Users, sessions, one-time tokens (invitation / password reset) and MFA recovery codes."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.security import Profile, Role


class TokenPurpose(StrEnum):
    INVITATION = "INVITATION"
    PASSWORD_RESET = "PASSWORD_RESET"  # noqa: S105 - enum label, not a password


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)

    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    # NULL until an invited user accepts the invitation and sets a password.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # What the user can do.
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="RESTRICT"), index=True)
    # Where the user sits in the role hierarchy (whose records they see). Optional.
    role_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    title: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    mara_number: Mapped[str | None] = mapped_column(String(20))
    # Portal users: the contact record they represent (their account is that contact's account).
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("records.id", ondelete="SET NULL", use_alter=True), index=True
    )
    locale: Mapped[str] = mapped_column(String(10), default="en-AU", server_default="en-AU")
    time_zone: Mapped[str] = mapped_column(String(40), default="Australia/Sydney", server_default="Australia/Sydney")

    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Fernet-encrypted TOTP secret. Set (with mfa_enabled = false) while enrolment is pending.
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(String(255))
    # Last accepted TOTP time-step, to reject replay of the same code.
    mfa_last_used_step: Mapped[int | None] = mapped_column(Integer)

    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sessions: Mapped[list[UserSession]] = relationship(back_populates="user", cascade="all, delete-orphan")
    profile: Mapped[Profile] = relationship(lazy="joined")
    role: Mapped[Role | None] = relationship(lazy="joined")

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None


class UserSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    mfa_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="sessions")


class UserToken(UUIDPrimaryKeyMixin, Base):
    """Single-use token for invitations and password resets. Only the SHA-256 hash is stored."""

    __tablename__ = "user_tokens"
    __table_args__ = (
        CheckConstraint("purpose IN ('INVITATION', 'PASSWORD_RESET')", name="purpose_valid"),
        Index("ix_user_tokens_user_purpose", "user_id", "purpose"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship()


class RecoveryCode(UUIDPrimaryKeyMixin, Base):
    """MFA recovery code (hashed). Each code works once."""

    __tablename__ = "mfa_recovery_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
