from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from scene_spatial.infrastructure.artifact_store import ArtifactStore
from scene_spatial.infrastructure.repositories.task_repository import TaskRepository
from scene_spatial.infrastructure.settings import Settings


class ResultService:
    def __init__(self, settings: Settings, session: Session) -> None:
        self.settings = settings
        self.session = session
        self.store = ArtifactStore(settings)
        self.tasks = TaskRepository(session)

    def get_result(self, task_id: str) -> dict[str, Any] | None:
        self.tasks.require(task_id)
        result_path = self.store.task_dir(task_id) / "spatial" / "spatial_scene_observation.json"
        if not result_path.exists():
            return None
        return json.loads(result_path.read_text(encoding="utf-8"))
