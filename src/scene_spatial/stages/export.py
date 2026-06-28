from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from scene_spatial.domain.stage import StageContext, StageResult
from scene_spatial.spatial.solver_utils import read_json, write_json
from scene_spatial.stages.base import PipelineStage
from scene_spatial.visualization.spatial import render_scene_preview_report


class ExportStage(PipelineStage):
    name = "export"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        objects_payload = _read_optional(ctx, "spatial/objects.json")
        roads_payload = _read_optional(ctx, "spatial/roads.json")
        groups_payload = _read_optional(ctx, "spatial/groups.json")
        ground = _read_optional(ctx, "spatial/ground.json")
        coordinate_system = _read_optional(ctx, "spatial/coordinate_system.json")
        object_diagnostics = _read_optional(ctx, "spatial/object_diagnostics.json")
        ground_diagnostics = _read_optional(ctx, "spatial/ground_diagnostics.json")
        group_diagnostics = _read_optional(ctx, "spatial/group_diagnostics.json")
        evaluation = _read_optional(ctx, "evaluation/metrics.json")

        objects = objects_payload.get("objects", []) if isinstance(objects_payload.get("objects"), list) else []
        roads = roads_payload.get("roads", []) if isinstance(roads_payload.get("roads"), list) else []
        groups = groups_payload.get("groups", []) if isinstance(groups_payload.get("groups"), list) else []
        observation: dict[str, Any] = {
            "schemaVersion": "1.0",
            "taskId": ctx.task_id,
            "source": "refined_spatial_scene_observation",
            "solverArchitecture": "pixel_align_ground_object_group_geometry_chain",
            "ground": ground,
            "coordinateSystem": coordinate_system,
            "objects": objects,
            "roads": roads,
            "groups": groups,
            "diagnostics": {
                "ground": ground_diagnostics,
                "objects": object_diagnostics,
                "groups": group_diagnostics,
                "evaluation": evaluation,
            },
            "artifacts": {
                "detections": "detection/detections.json",
                "pixelMapping": "geometry/pixel_mapping.json",
                "ground": "spatial/ground.json",
                "coordinateSystem": "spatial/coordinate_system.json",
                "objects": "spatial/objects.json",
                "roads": "spatial/roads.json",
                "groups": "spatial/groups.json",
                "objectDiagnostics": "spatial/object_diagnostics.json",
                "groundDiagnostics": "spatial/ground_diagnostics.json",
                "groupDiagnostics": "spatial/group_diagnostics.json",
            },
        }
        write_json(ctx.task_dir / "spatial" / "spatial_scene_observation.json", observation)
        outputs = {"result": "spatial/spatial_scene_observation.json"}
        if render_scene_preview_report(ctx.task_dir):
            outputs["scene_preview_report"] = "visualizations/scene_preview.html"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={"object_count": len(objects), "road_count": len(roads), "group_count": len(groups)},
        )


def _read_optional(ctx: StageContext, relative_path: str) -> dict[str, Any]:
    path = ctx.task_dir / relative_path
    return read_json(path) if path.exists() else {}
