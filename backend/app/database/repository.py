from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ProjectModel, SessionModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Repository:
    """Async persistence operations for PLCForge projects and pipeline sessions.

    The repository intentionally flushes and refreshes changed ORM instances, but
    leaves transaction commit/rollback ownership to the service layer.
    """

    _SESSION_MUTABLE_FIELDS = {
        "state",
        "requirement",
        "requirement_input",
        "safety_constraints",
        "plan_object",
        "code_artifact",
        "code_artifact_history",
        "st_code",
        "st_code_pre_opt",
        "validation_result",
        "validation_report",
        "validation_report_history",
        "debugging_report",
        "debugging_report_history",
        "repair_loop_report",
        "optimization_report",
        "optimization_report_history",
        "metrics_report",
        "metrics_report_history",
        "metrics_before",
        "metrics_after",
        "messages_log",
        "workflow_events",
        "total_tokens_used",
        "error",
        "completed_at",
    }

    _PROJECT_MUTABLE_FIELDS = {
        "name",
        "domain",
        "description",
        "standard",
        "target_language",
        "complexity_tier",
        "status",
        "updated_at",
    }

    async def create_project(self, db: AsyncSession, project_data: dict[str, Any]) -> ProjectModel:
        payload = self._normalize_payload(project_data)
        payload.setdefault("status", "draft")
        payload.setdefault("created_at", utc_now())
        payload.setdefault("updated_at", utc_now())

        project = ProjectModel(**payload)
        db.add(project)
        await db.flush()
        await db.refresh(project)
        return project

    async def get_project(self, db: AsyncSession, project_id: str) -> ProjectModel | None:
        result = await db.execute(select(ProjectModel).where(ProjectModel.id == project_id))
        return result.scalar_one_or_none()

    async def list_projects(self, db: AsyncSession) -> list[ProjectModel]:
        result = await db.execute(select(ProjectModel).order_by(desc(ProjectModel.updated_at), ProjectModel.id))
        return list(result.scalars().all())

    async def update_project(self, db: AsyncSession, project_id: str, **kwargs: Any) -> ProjectModel:
        project = await self.require_project(db, project_id)
        updates = self._normalize_payload(kwargs)
        invalid_fields = set(updates) - self._PROJECT_MUTABLE_FIELDS
        if invalid_fields:
            invalid = ", ".join(sorted(invalid_fields))
            raise ValueError(f"Unsupported ProjectModel update field(s): {invalid}")

        updates.setdefault("updated_at", utc_now())
        for field_name, value in updates.items():
            setattr(project, field_name, value)

        await db.flush()
        await db.refresh(project)
        return project

    async def require_project(self, db: AsyncSession, project_id: str) -> ProjectModel:
        project = await self.get_project(db, project_id)
        if project is None:
            raise LookupError(f"Project {project_id} was not found.")
        return project

    async def create_session(self, db: AsyncSession, session_data: dict[str, Any]) -> SessionModel:
        payload = self._normalize_payload(session_data)
        payload.setdefault("state", "created")
        payload.setdefault("safety_constraints", [])
        payload.setdefault("code_artifact_history", [])
        payload.setdefault("validation_report_history", [])
        payload.setdefault("debugging_report_history", [])
        payload.setdefault("optimization_report_history", [])
        payload.setdefault("metrics_report_history", [])
        payload.setdefault("messages_log", [])
        payload.setdefault("workflow_events", [])
        payload.setdefault("total_tokens_used", 0)
        payload.setdefault("created_at", utc_now())

        session = SessionModel(**payload)
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session

    async def get_session(self, db: AsyncSession, session_id: str) -> SessionModel | None:
        result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
        return result.scalar_one_or_none()

    async def get_latest_session_for_project(self, db: AsyncSession, project_id: str) -> SessionModel | None:
        result = await db.execute(
            select(SessionModel)
            .where(SessionModel.project_id == project_id)
            .order_by(desc(SessionModel.created_at), desc(SessionModel.id))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_or_create_project_session(self, db: AsyncSession, project_id: str) -> SessionModel:
        session = await self.get_latest_session_for_project(db, project_id)
        if session is not None:
            return session
        return await self.create_session(
            db,
            {
                "id": f"{project_id}-session-1",
                "project_id": project_id,
                "state": "created",
            },
        )

    async def update_session_state(
        self,
        db: AsyncSession,
        session_id: str,
        new_state: str,
        **kwargs: Any,
    ) -> SessionModel:
        session = await self._require_session(db, session_id)
        session.state = self._coerce_value(new_state)

        updates = self._normalize_payload(kwargs)
        invalid_fields = set(updates) - self._SESSION_MUTABLE_FIELDS
        if invalid_fields:
            invalid = ", ".join(sorted(invalid_fields))
            raise ValueError(f"Unsupported SessionModel update field(s): {invalid}")

        for field_name, value in updates.items():
            setattr(session, field_name, value)

        if session.state in {"completed", "failed", "cancelled"} and session.completed_at is None:
            session.completed_at = utc_now()

        await db.flush()
        await db.refresh(session)
        return session

    async def append_session_message(
        self,
        db: AsyncSession,
        session_id: str,
        message: dict[str, Any],
    ) -> SessionModel:
        if not isinstance(message, dict):
            raise TypeError("Session message must be a dictionary.")

        session = await self._require_session(db, session_id)
        current_log = session.messages_log if isinstance(session.messages_log, list) else []
        session.messages_log = [*current_log, self._normalize_payload(message)]

        await db.flush()
        await db.refresh(session)
        return session

    async def append_workflow_event(
        self,
        db: AsyncSession,
        session_id: str,
        event: dict[str, Any],
    ) -> SessionModel:
        if not isinstance(event, dict):
            raise TypeError("Workflow event must be a dictionary.")

        session = await self._require_session(db, session_id)
        current_events = session.workflow_events if isinstance(session.workflow_events, list) else []
        session.workflow_events = [*current_events, self._normalize_payload(event)]

        await db.flush()
        await db.refresh(session)
        return session

    async def _require_session(self, db: AsyncSession, session_id: str) -> SessionModel:
        result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise LookupError(f"Session {session_id} was not found.")
        return session

    @classmethod
    def _normalize_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        return {key: cls._coerce_value(value) for key, value in payload.items()}

    @classmethod
    def _coerce_value(cls, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return cls._normalize_payload(value)
        if isinstance(value, list):
            return [cls._coerce_value(item) for item in value]
        return value
