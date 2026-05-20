"""Initial PLCForge SQLAlchemy schema.

Revision ID: 20260520_0001
Revises:
Create Date: 2026-05-20 22:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260520_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("standard", sa.String(length=50), nullable=False, server_default="IEC 61131-3"),
        sa.Column("target_language", sa.String(length=50), nullable=False, server_default="Structured Text"),
        sa.Column("complexity_tier", sa.String(length=50), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_name", "projects", ["name"], unique=False)
    op.create_index("ix_projects_domain", "projects", ["domain"], unique=False)
    op.create_index("ix_projects_status", "projects", ["status"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("requirement", sa.Text(), nullable=True),
        sa.Column("requirement_input", sa.JSON(), nullable=True),
        sa.Column("safety_constraints", sa.JSON(), nullable=False),
        sa.Column("plan_object", sa.JSON(), nullable=True),
        sa.Column("code_artifact", sa.JSON(), nullable=True),
        sa.Column("code_artifact_history", sa.JSON(), nullable=False),
        sa.Column("st_code", sa.Text(), nullable=True),
        sa.Column("st_code_pre_opt", sa.Text(), nullable=True),
        sa.Column("validation_result", sa.JSON(), nullable=True),
        sa.Column("validation_report", sa.JSON(), nullable=True),
        sa.Column("validation_report_history", sa.JSON(), nullable=False),
        sa.Column("debugging_report", sa.JSON(), nullable=True),
        sa.Column("debugging_report_history", sa.JSON(), nullable=False),
        sa.Column("repair_loop_report", sa.JSON(), nullable=True),
        sa.Column("optimization_report", sa.JSON(), nullable=True),
        sa.Column("optimization_report_history", sa.JSON(), nullable=False),
        sa.Column("metrics_report", sa.JSON(), nullable=True),
        sa.Column("metrics_report_history", sa.JSON(), nullable=False),
        sa.Column("metrics_before", sa.JSON(), nullable=True),
        sa.Column("metrics_after", sa.JSON(), nullable=True),
        sa.Column("messages_log", sa.JSON(), nullable=False),
        sa.Column("workflow_events", sa.JSON(), nullable=False),
        sa.Column("total_tokens_used", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_project_id", "sessions", ["project_id"], unique=False)
    op.create_index("ix_sessions_state", "sessions", ["state"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sessions_state", table_name="sessions")
    op.drop_index("ix_sessions_project_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_domain", table_name="projects")
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_table("projects")
