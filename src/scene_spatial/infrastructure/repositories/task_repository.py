from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from scene_spatial.domain.enums import TaskStatus
from scene_spatial.infrastructure.db_models import TaskModel


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, task: TaskModel) -> TaskModel:
        self.session.add(task)
        self.session.flush()
        return task

    def get(self, task_id: str) -> TaskModel | None:
        return self.session.get(TaskModel, task_id)

    def require(self, task_id: str) -> TaskModel:
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        return task

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        current_stage: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> TaskModel:
        task = self.require(task_id)
        task.status = status.value
        task.current_stage = current_stage
        task.error_code = error_code
        task.error_message = error_message
        task.updated_at = datetime.now(UTC)
        self.session.flush()
        return task

    def claim_next(self, worker_id: str, lease_seconds: int) -> TaskModel | None:
        task = self.session.execute(
            select(TaskModel)
            .where(TaskModel.status == TaskStatus.QUEUED.value)
            .order_by(TaskModel.priority.desc(), TaskModel.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()
        if task is None:
            return None

        now = datetime.now(UTC)
        task.status = TaskStatus.RUNNING.value
        task.started_at = task.started_at or now
        task.updated_at = now
        task.worker_id = worker_id
        task.lease_expires_at = now + timedelta(seconds=lease_seconds)
        self.session.flush()
        return task
