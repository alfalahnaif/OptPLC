from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all PLCForge persistence models."""


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    standard: Mapped[str] = mapped_column(String(50), nullable=False, default="IEC 61131-3")
    target_language: Mapped[str] = mapped_column(String(50), nullable=False, default="Structured Text")
    complexity_tier: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    sessions: Mapped[list[SessionModel]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_input: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    safety_constraints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    plan_object: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    code_artifact: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    code_artifact_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    st_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    st_code_pre_opt: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation_report_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    debugging_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    debugging_report_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    repair_loop_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    optimization_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    optimization_report_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    metrics_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    metrics_report_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    metrics_before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    metrics_after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    messages_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    workflow_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    total_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[ProjectModel] = relationship(back_populates="sessions")
