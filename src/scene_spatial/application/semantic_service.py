from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from scene_spatial.domain.enums import ArtifactType, TaskStatus
from scene_spatial.domain.semantic import SceneSemanticProposal, SemanticImportResponse
from scene_spatial.infrastructure.artifact_store import ArtifactStore
from scene_spatial.infrastructure.db_models import ArtifactModel
from scene_spatial.infrastructure.repositories.task_repository import TaskRepository
from scene_spatial.infrastructure.settings import Settings, project_root
from scene_spatial.semantics.prompt_builder import PromptBuilder


class SemanticService:
    def __init__(self, settings: Settings, session: Session) -> None:
        self.settings = settings
        self.session = session
        self.store = ArtifactStore(settings)
        self.tasks = TaskRepository(session)

    def import_manual_proposal(
        self,
        task_id: str,
        proposal: SceneSemanticProposal,
    ) -> SemanticImportResponse:
        task = self.tasks.require(task_id)
        allowed_statuses = {
            TaskStatus.WAITING_SEMANTIC_PROPOSAL.value,
            TaskStatus.SEMANTIC_READY.value,
        }
        if task.status not in allowed_statuses:
            raise ValueError(f"Task cannot import semantic proposal from status {task.status}")

        self.tasks.update_status(task_id, TaskStatus.SEMANTIC_VALIDATING)

        proposal_payload = proposal.model_dump(mode="json")
        self.store.write_json(task_id, "semantic/proposal.raw.json", proposal_payload)
        self.store.write_json(task_id, "semantic/proposal.json", proposal_payload)

        validation_payload = {
            "valid": True,
            "warnings": [warning.model_dump(mode="json") for warning in proposal.warnings],
            "categoryCount": len(proposal.categoryProposals),
            "patternHintCount": len(proposal.patternHints),
        }
        self.store.write_json(task_id, "semantic/validation.json", validation_payload)

        builder = PromptBuilder(project_root() / "configs" / "categories.yaml")
        sam_tasks = builder.build_sam_tasks(proposal)
        self.store.write_json(task_id, "semantic/sam_tasks.json", sam_tasks)

        for relative_path in [
            "semantic/proposal.raw.json",
            "semantic/proposal.json",
            "semantic/validation.json",
            "semantic/sam_tasks.json",
        ]:
            path = self.store.task_dir(task_id) / relative_path
            self.session.add(
                ArtifactModel(
                    task_id=task_id,
                    stage_name="semantic_import",
                    artifact_type=ArtifactType.JSON.value,
                    relative_path=relative_path,
                    mime_type="application/json",
                    size_bytes=Path(path).stat().st_size,
                )
            )

        self.tasks.update_status(task_id, TaskStatus.SEMANTIC_READY)
        self.session.flush()

        return SemanticImportResponse(
            task_id=task_id,
            status=TaskStatus.SEMANTIC_READY.value,
            validation=validation_payload,
        )
