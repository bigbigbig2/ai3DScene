from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from scene_spatial.api.dependencies import SessionDep, SettingsDep
from scene_spatial.application.correction_service import CorrectionService

router = APIRouter()


@router.post("/tasks/{task_id}/corrections/ground-points")
def submit_ground_points(
    task_id: str,
    payload: dict[str, Any],
    settings: SettingsDep,
    session: SessionDep,
) -> dict[str, Any]:
    return _submit(task_id, "ground_points", payload, settings, session)


@router.post("/tasks/{task_id}/corrections/scale-anchor")
def submit_scale_anchor(
    task_id: str,
    payload: dict[str, Any],
    settings: SettingsDep,
    session: SessionDep,
) -> dict[str, Any]:
    return _submit(task_id, "scale_anchor", payload, settings, session)


@router.post("/tasks/{task_id}/corrections/object-transform")
def submit_object_transform(
    task_id: str,
    payload: dict[str, Any],
    settings: SettingsDep,
    session: SessionDep,
) -> dict[str, Any]:
    return _submit(task_id, "object_transform", payload, settings, session)


def _submit(
    task_id: str,
    correction_type: str,
    payload: dict[str, Any],
    settings: SettingsDep,
    session: SessionDep,
) -> dict[str, Any]:
    try:
        response = CorrectionService(settings, session).submit(task_id, correction_type, payload)
        session.commit()
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
