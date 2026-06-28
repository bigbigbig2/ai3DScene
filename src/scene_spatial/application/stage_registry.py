from __future__ import annotations

from scene_spatial.stages.base import PipelineStage
from scene_spatial.stages.fake_pipeline import BuildSamTasksStage, MaskPostprocessStage
from scene_spatial.stages.export import ExportStage
from scene_spatial.stages.model_stages import MogeEstimateStage, SamSegmentStage
from scene_spatial.stages.spatial_solve import (
    EvaluateStage,
    GroundSolveStage,
    GroupSolveStage,
    ObjectSolveStage,
    PixelAlignStage,
)


def build_stage_registry() -> dict[str, PipelineStage]:
    stages: list[PipelineStage] = [
        BuildSamTasksStage(),
        SamSegmentStage(),
        MaskPostprocessStage(),
        MogeEstimateStage(),
        PixelAlignStage(),
        GroundSolveStage(),
        ObjectSolveStage(),
        GroupSolveStage(),
        ExportStage(),
        EvaluateStage(),
    ]
    return {stage.name: stage for stage in stages}

