from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from scene_spatial.infrastructure.db_models import TaskModel
from scene_spatial.infrastructure.settings import Settings


def refresh_task_lease(session: Session, settings: Settings, task: TaskModel) -> None:
    now = datetime.now(UTC)
    task.updated_at = now
    task.lease_expires_at = now + timedelta(seconds=settings.task_lease_seconds)
    session.flush()
