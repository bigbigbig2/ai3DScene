from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from scene_spatial.api.dependencies import SessionDep, SettingsDep
from scene_spatial.application.task_service import TaskService
from scene_spatial.domain.enums import SemanticMode
from scene_spatial.domain.task import CreateTaskResponse, TaskStatusResponse

router = APIRouter()


class RerunRequest(BaseModel):
    fromStage: str


@router.post("/tasks", response_model=CreateTaskResponse)
def create_task(
    settings: SettingsDep,
    session: SessionDep,
    file: UploadFile = File(...),
    domain: str = Form(...),
    semantic_mode: SemanticMode = Form(SemanticMode.MANUAL),
) -> CreateTaskResponse:
    suffix = Path(file.filename or "upload.png").suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        response = TaskService(settings, session).create_task_from_upload(
            tmp_path,
            domain=domain,
            semantic_mode=semantic_mode,
        )
        session.commit()
        return response
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task(task_id: str, settings: SettingsDep, session: SessionDep) -> TaskStatusResponse:
    try:
        return TaskService(settings, session).get_task_status(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/run", response_model=TaskStatusResponse)
def run_task(task_id: str, settings: SettingsDep, session: SessionDep) -> TaskStatusResponse:
    try:
        response = TaskService(settings, session).enqueue(task_id)
        session.commit()
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/rerun", response_model=TaskStatusResponse)
def rerun_task(
    task_id: str,
    payload: RerunRequest,
    settings: SettingsDep,
    session: SessionDep,
) -> TaskStatusResponse:
    try:
        response = TaskService(settings, session).rerun_from_stage(task_id, payload.fromStage)
        session.commit()
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
