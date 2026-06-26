from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from scene_spatial.domain.enums import SemanticMode, TaskStatus


class TaskRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    status: TaskStatus
    current_stage: str | None = Field(default=None, alias="currentStage")
    domain: str
    input_image_path: str = Field(alias="inputImagePath")
    semantic_mode: SemanticMode = Field(alias="semanticMode")
    priority: int = 0
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")
    worker_id: str | None = Field(default=None, alias="workerId")
    lease_expires_at: datetime | None = Field(default=None, alias="leaseExpiresAt")
    version: int = 1


class CreateTaskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    status: TaskStatus
    task_dir: Path = Field(alias="taskDir")


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    status: TaskStatus
    current_stage: str | None = Field(alias="currentStage")
    domain: str
    input_image_path: str = Field(alias="inputImagePath")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")
