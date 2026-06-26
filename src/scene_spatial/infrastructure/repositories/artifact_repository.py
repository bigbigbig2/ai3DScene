from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from scene_spatial.infrastructure.db_models import ArtifactModel


class ArtifactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_task(self, task_id: str) -> list[ArtifactModel]:
        return list(
            self.session.execute(
                select(ArtifactModel).where(ArtifactModel.task_id == task_id).order_by(ArtifactModel.id.asc())
            ).scalars()
        )
