from __future__ import annotations

from sqlalchemy.orm import Session

from scene_spatial.infrastructure.db_models import StageRunModel


class StageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, stage_run: StageRunModel) -> StageRunModel:
        self.session.add(stage_run)
        self.session.flush()
        return stage_run
