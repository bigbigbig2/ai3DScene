from __future__ import annotations

from abc import ABC, abstractmethod

from scene_spatial.domain.stage import StageContext, StageResult


class PipelineStage(ABC):
    name: str
    timeout_seconds: int = 600

    @abstractmethod
    def execute(self, ctx: StageContext) -> StageResult:
        raise NotImplementedError
