from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from scene_spatial.application.pipeline_definition import PIPELINE
from scene_spatial.application.stage_registry import build_stage_registry
from scene_spatial.domain.enums import ArtifactType, StageStatus, TaskStatus
from scene_spatial.domain.stage import StageContext, StageResult
from scene_spatial.infrastructure.artifact_store import ArtifactStore
from scene_spatial.infrastructure.db_models import ArtifactModel, StageRunModel, TaskModel
from scene_spatial.infrastructure.repositories.task_repository import TaskRepository
from scene_spatial.infrastructure.settings import Settings


STAGE_TASK_STATUS = {
    "build_sam_tasks": TaskStatus.BUILDING_SAM_TASKS,
    "sam_segment": TaskStatus.SEGMENTING,
    "mask_postprocess": TaskStatus.MASK_POSTPROCESSING,
    "moge_estimate": TaskStatus.GEOMETRY_ESTIMATING,
    "pixel_align": TaskStatus.PIXEL_ALIGNING,
    "ground_solve": TaskStatus.GROUND_SOLVING,
    "object_solve": TaskStatus.OBJECT_SOLVING,
    "group_solve": TaskStatus.GROUP_SOLVING,
    "export": TaskStatus.EXPORTING,
    "evaluate": TaskStatus.EVALUATING,
}


class PipelineOrchestrator:
    def __init__(self, settings: Settings, session: Session) -> None:
        self.settings = settings
        self.session = session
        self.store = ArtifactStore(settings)
        self.tasks = TaskRepository(session)
        self.stage_registry = build_stage_registry()

    def run(self, task: TaskModel) -> None:
        ctx = StageContext(
            task_id=task.id,
            task_dir=self.store.task_dir(task.id),
            input_image=self.store.task_dir(task.id) / task.input_image_path,
            domain=task.domain,
            gpu_physical_id=self.settings.gpu_physical_id,
            config_snapshot_path=self.store.task_dir(task.id) / "config_snapshot",
            attempt=1,
            fake_models=self.settings.fake_models,
            sam_python=self.settings.sam_python,
            sam_worker=self.settings.sam_worker,
            moge_python=self.settings.moge_python,
            moge_worker=self.settings.moge_worker,
        )

        try:
            pipeline = PIPELINE
            if task.current_stage in PIPELINE:
                pipeline = PIPELINE[PIPELINE.index(task.current_stage) :]

            for stage_name in pipeline:
                self.tasks.update_status(task.id, STAGE_TASK_STATUS[stage_name], current_stage=stage_name)
                self.session.commit()

                stage = self.stage_registry[stage_name]
                result = stage.execute(ctx)
                self._record_stage_result(task.id, result)
                self.session.commit()

                if result.status != StageStatus.COMPLETED:
                    message = result.error.message if result.error else f"Stage failed: {stage_name}"
                    code = result.error.code if result.error else "STAGE_FAILED"
                    self.tasks.update_status(
                        task.id,
                        TaskStatus.FAILED,
                        current_stage=stage_name,
                        error_code=code,
                        error_message=message,
                    )
                    self.session.commit()
                    return

            self.tasks.update_status(task.id, TaskStatus.COMPLETED, current_stage=None)
            self.store.write_json(
                task.id,
                "task.json",
                {
                    "taskId": task.id,
                    "status": TaskStatus.COMPLETED.value,
                    "domain": task.domain,
                    "semanticMode": task.semantic_mode,
                },
            )
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            self.tasks.update_status(
                task.id,
                TaskStatus.FAILED,
                current_stage=task.current_stage,
                error_code="INTERNAL_ERROR",
                error_message=str(exc),
            )
            self.session.commit()
            raise

    def _record_stage_result(self, task_id: str, result: StageResult) -> None:
        result_path = self.store.task_dir(task_id) / "stages" / f"{result.stage}_attempt_1.json"
        result_path.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.session.add(
            StageRunModel(
                task_id=task_id,
                stage_name=result.stage,
                status=result.status.value,
                attempt=1,
                started_at=result.started_at,
                finished_at=result.finished_at,
                duration_ms=result.duration_ms,
                worker_pid=os.getpid(),
                gpu_id=self.settings.gpu_physical_id,
                peak_gpu_memory_mib=self._peak_gpu_memory(result),
                error_code=result.error.code if result.error else None,
                error_message=result.error.message if result.error else None,
                traceback_path=result.error.traceback_path if result.error else None,
            )
        )
        self._record_artifact(task_id, result.stage, self.store.relative_to_task(task_id, result_path))
        for relative_path in result.outputs.values():
            self._record_artifact(task_id, result.stage, relative_path)

    def _record_artifact(self, task_id: str, stage_name: str, relative_path: str) -> None:
        path = self.store.task_dir(task_id) / relative_path
        if not path.exists():
            return
        self.session.add(
            ArtifactModel(
                task_id=task_id,
                stage_name=stage_name,
                artifact_type=self._artifact_type(path).value,
                relative_path=relative_path,
                mime_type=self._mime_type(path),
                size_bytes=path.stat().st_size if path.is_file() else None,
            )
        )

    @staticmethod
    def _artifact_type(path: Path) -> ArtifactType:
        if path.is_dir():
            return ArtifactType.MASK if "mask" in path.name.lower() else ArtifactType.JSON
        suffix = path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            return ArtifactType.IMAGE
        if suffix == ".json":
            return ArtifactType.JSON
        if suffix == ".npy":
            return ArtifactType.NUMPY
        if suffix == ".ply":
            return ArtifactType.POINT_CLOUD
        if suffix == ".log":
            return ArtifactType.LOG
        if suffix in {".html", ".htm"}:
            return ArtifactType.REPORT
        return ArtifactType.JSON

    @staticmethod
    def _mime_type(path: Path) -> str | None:
        suffix = path.suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".json": "application/json",
            ".npy": "application/octet-stream",
            ".ply": "application/octet-stream",
            ".log": "text/plain",
            ".html": "text/html",
            ".htm": "text/html",
        }.get(suffix)

    @staticmethod
    def _peak_gpu_memory(result: StageResult) -> int | None:
        value = result.metrics.get("peak_gpu_memory_mib")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

