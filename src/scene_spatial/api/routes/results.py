from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from scene_spatial.api.dependencies import SessionDep, SettingsDep
from scene_spatial.infrastructure.artifact_store import ArtifactStore
from scene_spatial.infrastructure.db_models import ArtifactModel
from scene_spatial.infrastructure.repositories.task_repository import TaskRepository

router = APIRouter()


@router.get("/tasks/{task_id}/artifacts")
def list_artifacts(task_id: str, settings: SettingsDep, session: SessionDep) -> dict[str, object]:
    try:
        TaskRepository(session).require(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    rows = session.execute(
        select(ArtifactModel).where(ArtifactModel.task_id == task_id).order_by(ArtifactModel.id.asc())
    ).scalars()
    return {
        "taskId": task_id,
        "artifacts": [
            {
                "id": row.id,
                "stageName": row.stage_name,
                "artifactType": row.artifact_type,
                "relativePath": row.relative_path,
                "mimeType": row.mime_type,
                "sizeBytes": row.size_bytes,
                "createdAt": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


@router.get("/tasks/{task_id}/artifacts/{artifact_id}")
def get_artifact(task_id: str, artifact_id: int, settings: SettingsDep, session: SessionDep):
    try:
        TaskRepository(session).require(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    artifact = session.get(ArtifactModel, artifact_id)
    if artifact is None or artifact.task_id != task_id:
        raise HTTPException(status_code=404, detail="Artifact not found")

    task_dir = ArtifactStore(settings).task_dir(task_id).resolve()
    artifact_path = (task_dir / artifact.relative_path).resolve()
    if task_dir not in artifact_path.parents and artifact_path != task_dir:
        raise HTTPException(status_code=400, detail="Artifact path escapes task directory")
    if not artifact_path.exists() or artifact_path.is_dir():
        raise HTTPException(status_code=404, detail="Artifact file is not available")

    return FileResponse(
        artifact_path,
        media_type=artifact.mime_type or "application/octet-stream",
        filename=artifact_path.name,
    )


@router.get("/tasks/{task_id}/result")
def get_result(task_id: str, settings: SettingsDep, session: SessionDep) -> dict[str, object]:
    try:
        TaskRepository(session).require(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result_path = ArtifactStore(settings).task_dir(task_id) / "spatial" / "spatial_scene_observation.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Result is not available yet")
    return json.loads(result_path.read_text(encoding="utf-8"))
