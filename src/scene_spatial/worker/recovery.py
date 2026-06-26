from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from scene_spatial.domain.enums import TaskStatus
from scene_spatial.infrastructure.db_models import TaskModel


def recover_stale_jobs(session: Session) -> int:
    now = datetime.now(UTC)
    stale_tasks = session.execute(
        select(TaskModel).where(
            TaskModel.status == TaskStatus.RUNNING.value,
            TaskModel.lease_expires_at.is_not(None),
            TaskModel.lease_expires_at < now,
        )
    ).scalars()

    recovered = 0
    for task in stale_tasks:
        task.status = TaskStatus.QUEUED.value
        task.worker_id = None
        task.lease_expires_at = None
        task.updated_at = now
        recovered += 1

    if recovered:
        session.commit()
    return recovered
