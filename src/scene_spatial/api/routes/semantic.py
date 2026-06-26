from __future__ import annotations

from fastapi import APIRouter, HTTPException

from scene_spatial.api.dependencies import SessionDep, SettingsDep
from scene_spatial.application.semantic_service import SemanticService
from scene_spatial.domain.semantic import SceneSemanticProposal, SemanticImportResponse

router = APIRouter()


@router.post("/tasks/{task_id}/semantic-proposal", response_model=SemanticImportResponse)
def import_semantic_proposal(
    task_id: str,
    proposal: SceneSemanticProposal,
    settings: SettingsDep,
    session: SessionDep,
) -> SemanticImportResponse:
    try:
        response = SemanticService(settings, session).import_manual_proposal(task_id, proposal)
        session.commit()
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
