from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from scene_spatial.domain.enums import ArtifactType
from scene_spatial.infrastructure.artifact_store import ArtifactStore
from scene_spatial.infrastructure.db_models import ArtifactModel, CorrectionModel
from scene_spatial.infrastructure.repositories.task_repository import TaskRepository
from scene_spatial.infrastructure.settings import Settings


class CorrectionService:
    def __init__(self, settings: Settings, session: Session) -> None:
        self.settings = settings
        self.session = session
        self.store = ArtifactStore(settings)
        self.tasks = TaskRepository(session)

    def submit(self, task_id: str, correction_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.tasks.require(task_id)
        now = datetime.now(UTC)
        correction = CorrectionModel(
            task_id=task_id,
            correction_type=correction_type,
            payload_json=self._payload_to_json(payload),
            created_at=now,
        )
        self.session.add(correction)
        self.session.flush()

        relative_path = f"spatial/corrections/{correction.id}_{correction_type}.json"
        path = self.store.write_json(
            task_id,
            relative_path,
            {
                "id": correction.id,
                "taskId": task_id,
                "correctionType": correction_type,
                "payload": payload,
                "createdAt": now.isoformat(),
            },
        )
        self.session.add(
            ArtifactModel(
                task_id=task_id,
                stage_name="correction",
                artifact_type=ArtifactType.JSON.value,
                relative_path=relative_path,
                mime_type="application/json",
                size_bytes=path.stat().st_size,
            )
        )
        return {
            "id": correction.id,
            "taskId": task_id,
            "correctionType": correction_type,
            "createdAt": now.isoformat(),
        }

    @staticmethod
    def _payload_to_json(payload: dict[str, Any]) -> str:
        import json

        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
