from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from scene_spatial.domain.enums import StageStatus


class StageError(BaseModel):
    code: str
    message: str
    traceback_path: str | None = None


class StageContext(BaseModel):
    task_id: str
    task_dir: Path
    input_image: Path | None = None
    domain: str
    gpu_physical_id: int
    config_snapshot_path: Path
    attempt: int = 1
    fake_models: bool = True
    sam_python: Path | None = None
    sam_worker: Path | None = None
    moge_python: Path | None = None
    moge_worker: Path | None = None


class StageResult(BaseModel):
    stage: str
    status: StageStatus
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int = 0
    outputs: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: StageError | None = None

    @classmethod
    def completed(
        cls,
        stage: str,
        started_at: datetime,
        outputs: dict[str, str] | None = None,
        metrics: dict[str, float | int | str] | None = None,
        warnings: list[str] | None = None,
    ) -> "StageResult":
        finished_at = datetime.now(UTC)
        return cls(
            stage=stage,
            status=StageStatus.COMPLETED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=int((finished_at - started_at).total_seconds() * 1000),
            outputs=outputs or {},
            metrics=metrics or {},
            warnings=warnings or [],
        )

    @classmethod
    def failed(
        cls,
        stage: str,
        started_at: datetime,
        code: str,
        message: str,
        outputs: dict[str, str] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> "StageResult":
        finished_at = datetime.now(UTC)
        return cls(
            stage=stage,
            status=StageStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=int((finished_at - started_at).total_seconds() * 1000),
            outputs=outputs or {},
            metrics=metrics or {},
            error=StageError(code=code, message=message),
        )
