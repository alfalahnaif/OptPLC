from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProjectModel(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_name", "name"),
        Index("ix_projects_domain", "domain"),
        Index("ix_projects_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    standard: Mapped[str] = mapped_column(String(50), nullable=False, server_default="IEC 61131-3")
    target_language: Mapped[str] = mapped_column(String(50), nullable=False, server_default="Structured Text")
    complexity_tier: Mapped[str] = mapped_column(String(50), nullable=False, server_default="medium")
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SessionModel(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        Index("ix_sessions_project_id", "project_id"),
        Index("ix_sessions_state", "state"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_input: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    safety_constraints: Mapped[list[Any]] = mapped_column(JSON, nullable=False, server_default="[]")
    plan_object: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    code_artifact: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    code_artifact_history: Mapped[list[Any]] = mapped_column(JSON, nullable=False, server_default="[]")
    st_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    st_code_pre_opt: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation_report_history: Mapped[list[Any]] = mapped_column(JSON, nullable=False, server_default="[]")
    debugging_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    debugging_report_history: Mapped[list[Any]] = mapped_column(JSON, nullable=False, server_default="[]")
    repair_loop_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    optimization_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    optimization_report_history: Mapped[list[Any]] = mapped_column(JSON, nullable=False, server_default="[]")
    metrics_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    metrics_report_history: Mapped[list[Any]] = mapped_column(JSON, nullable=False, server_default="[]")
    metrics_before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    metrics_after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    messages_log: Mapped[list[Any]] = mapped_column(JSON, nullable=False, server_default="[]")
    workflow_events: Mapped[list[Any]] = mapped_column(JSON, nullable=False, server_default="[]")
    total_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
