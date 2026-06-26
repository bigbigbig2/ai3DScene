from __future__ import annotations

from sqlalchemy.orm import Session

from scene_spatial.infrastructure.db_models import TaskModel
from scene_spatial.infrastructure.repositories.task_repository import TaskRepository
from scene_spatial.infrastructure.settings import Settings


class JobClaimer:
    def __init__(self, settings: Settings, session: Session, worker_id: str) -> None:
        self.settings = settings
        self.session = session
        self.worker_id = worker_id

    def claim_next(self) -> TaskModel | None:
        repo = TaskRepository(self.session)
        task = repo.claim_next(self.worker_id, self.settings.task_lease_seconds)
        self.session.commit()
        return task
