from __future__ import annotations

import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from scene_spatial.domain.enums import ArtifactType, SemanticMode, TaskStatus
from scene_spatial.domain.task import CreateTaskResponse, TaskStatusResponse
from scene_spatial.infrastructure.artifact_store import ArtifactStore
from scene_spatial.infrastructure.db_models import ArtifactModel, TaskModel
from scene_spatial.infrastructure.repositories.task_repository import TaskRepository
from scene_spatial.infrastructure.settings import Settings
from scene_spatial.perception.image_preprocessor import ImagePreprocessor


class TaskService:
    def __init__(self, settings: Settings, session: Session) -> None:
        self.settings = settings
        self.session = session
        self.store = ArtifactStore(settings)
        self.preprocessor = ImagePreprocessor()
        self.tasks = TaskRepository(session)

    def create_task_from_upload(
        self,
        file_path: Path,
        domain: str,
        semantic_mode: SemanticMode = SemanticMode.MANUAL,
    ) -> CreateTaskResponse:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task_dir = self.store.create_task_layout(task_id)

        source_copy = task_dir / "input" / f"upload{file_path.suffix.lower() or '.image'}"
        shutil.copyfile(file_path, source_copy)

        metadata = self.preprocessor.prepare_task_images(source_copy, task_dir)
        now = datetime.now(UTC)
        task = TaskModel(
            id=task_id,
            status=TaskStatus.WAITING_SEMANTIC_PROPOSAL.value,
            current_stage=None,
            domain=domain,
            input_image_path="input/original.png",
            semantic_mode=semantic_mode.value,
            created_at=now,
            updated_at=now,
        )
        self.tasks.add(task)

        self.store.write_json(
            task_id,
            "task.json",
            {
                "taskId": task_id,
                "status": task.status,
                "domain": domain,
                "semanticMode": semantic_mode.value,
                "createdAt": now.isoformat(),
            },
        )
        self.store.write_json(task_id, "input/metadata.json", metadata)
        self.session.add(
            ArtifactModel(
                task_id=task_id,
                stage_name="preprocess",
                artifact_type=ArtifactType.IMAGE.value,
                relative_path="input/original.png",
                mime_type="image/png",
                size_bytes=(task_dir / "input" / "original.png").stat().st_size,
            )
        )
        self.session.flush()

        return CreateTaskResponse(task_id=task_id, status=TaskStatus(task.status), task_dir=task_dir)

    def get_task_status(self, task_id: str) -> TaskStatusResponse:
        task = self.tasks.require(task_id)
        return TaskStatusResponse(
            task_id=task.id,
            status=TaskStatus(task.status),
            current_stage=task.current_stage,
            domain=task.domain,
            input_image_path=task.input_image_path,
            created_at=task.created_at,
            updated_at=task.updated_at,
            error_code=task.error_code,
            error_message=task.error_message,
        )

    def enqueue(self, task_id: str) -> TaskStatusResponse:
        task = self.tasks.require(task_id)
        if task.status != TaskStatus.SEMANTIC_READY.value:
            raise ValueError(f"Task must be SEMANTIC_READY before run, got {task.status}")
        self.tasks.update_status(task_id, TaskStatus.QUEUED)
        return self.get_task_status(task_id)

    def rerun_from_stage(self, task_id: str, from_stage: str) -> TaskStatusResponse:
        task = self.tasks.require(task_id)
        if task.status in {TaskStatus.RUNNING.value, TaskStatus.QUEUED.value}:
            raise ValueError(f"Task cannot be rerun while {task.status}")

        now = datetime.now(UTC)
        task.status = TaskStatus.QUEUED.value
        task.current_stage = from_stage
        task.error_code = None
        task.error_message = None
        task.worker_id = None
        task.lease_expires_at = None
        task.updated_at = now
        self.store.write_json(
            task_id,
            f"stages/rerun_{now.strftime('%Y%m%d_%H%M%S')}.json",
            {"taskId": task_id, "fromStage": from_stage, "queuedAt": now.isoformat()},
        )
        self.session.flush()
        return self.get_task_status(task_id)
