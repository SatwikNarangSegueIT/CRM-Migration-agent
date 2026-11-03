"""Reports, dashboards, folders and schedules (plan v3, section 12); e-mail delivery tracking (section 8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReportFolder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_folders"
    __table_args__ = (
        CheckConstraint("visibility IN ('private', 'public', 'shared')", name="visibility_valid"),
    )

    name: Mapped[str] = mapped_column(String(80))
    key: Mapped[str | None] = mapped_column(String(60), unique=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    visibility: Mapped[str] = mapped_column(String(10), default="private")
    shared_profile_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    shared_role_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_folder", "folder_id"),)

    name: Mapped[str] = mapped_column(String(120))
    key: Mapped[str | None] = mapped_column(String(60), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    folder_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("report_folders.id", ondelete="SET NULL"))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    object_api_name: Mapped[str] = mapped_column(String(80))
    # {"format": "tabular"|"summary"|"matrix", "columns": [...], "filters": AST, "scope": "mine"|"all",
    #  "group_by": [...], "group_columns": [...], "aggregates": [{"op", "field"}], "sort": [...],
    #  "chart": {"type": "bar"|"column"|"line"|"donut"|"funnel"|"kpi"}, "limit": n,
    #  "related": {"object": api, "field": lookup api}}
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    pack_key: Mapped[str | None] = mapped_column(String(60))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Dashboard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dashboards"

    name: Mapped[str] = mapped_column(String(120))
    key: Mapped[str | None] = mapped_column(String(60), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    folder_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("report_folders.id", ondelete="SET NULL"))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # "Run as" user for the whole dashboard (NULL = the viewer).
    running_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # [{"report_id": uuid, "title": str, "chart": type, "width": 1-3}]
    components: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    pack_key: Mapped[str | None] = mapped_column(String(60))


class ReportSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_schedules"
    __table_args__ = (CheckConstraint("frequency IN ('daily', 'weekly', 'monthly')", name="frequency_valid"),)

    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    frequency: Mapped[str] = mapped_column(String(10))
    recipients: Mapped[list[str]] = mapped_column(JSONB, default=list)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailDelivery(UUIDPrimaryKeyMixin, Base):
    """One recipient of an e-mail send, with delivery and engagement status."""

    __tablename__ = "email_deliveries"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'sent', 'failed', 'bounced', 'skipped')", name="status_valid"),
        Index("ix_email_deliveries_send", "send_record_id", "status"),
    )

    send_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"))
    recipient_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("records.id", ondelete="SET NULL")
    )
    email: Mapped[str] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(10), default="queued")
    skip_reason: Mapped[str | None] = mapped_column(String(80))
    # Random token used in the open pixel, click redirects and the unsubscribe link.
    tracking_token: Mapped[str] = mapped_column(String(64), unique=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    open_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    click_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
