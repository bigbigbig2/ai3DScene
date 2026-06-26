from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from scene_spatial.domain.stage import StageContext, StageResult
from scene_spatial.stages.base import PipelineStage


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_fake_npy(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import numpy as np

        np.save(path, np.zeros((2, 2, 3), dtype=np.float32))
    except ModuleNotFoundError:
        path.write_bytes(b"FAKE_NPY_PLACEHOLDER\n")


class BuildSamTasksStage(PipelineStage):
    name = "build_sam_tasks"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        sam_tasks = ctx.task_dir / "semantic" / "sam_tasks.json"
        if not sam_tasks.exists():
            return StageResult.failed(
                self.name,
                started_at,
                "SAM_TASKS_MISSING",
                "semantic/sam_tasks.json is missing",
            )
        payload = _read_json(sam_tasks)
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"sam_tasks": "semantic/sam_tasks.json"},
            metrics={"task_count": len(payload.get("tasks", []))},
        )


class SamSegmentStage(PipelineStage):
    name = "sam_segment"
    timeout_seconds = 900

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        metadata = _read_json(ctx.task_dir / "input" / "metadata.json")
        width = int(metadata["width"])
        height = int(metadata["height"])

        mask_path = ctx.task_dir / "detection" / "masks" / "building_001.png"
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        x0, y0 = int(width * 0.3), int(height * 0.3)
        x1, y1 = int(width * 0.7), int(height * 0.7)
        draw.rectangle([x0, y0, x1, y1], fill=255)
        mask.save(mask_path)

        detections = {
            "schemaVersion": "1.0",
            "model": "fake_sam3" if ctx.fake_models else "sam3",
            "detections": [
                {
                    "id": "building_001",
                    "category": "building",
                    "objectMode": "instance",
                    "bbox": [x0, y0, x1, y1],
                    "score": 0.9,
                    "maskPath": "detection/masks/building_001.png",
                }
            ],
        }
        _write_json(ctx.task_dir / "detection" / "detections.json", detections)
        _write_json(ctx.task_dir / "detection" / "raw" / "detections.json", detections)

        return StageResult.completed(
            self.name,
            started_at,
            outputs={
                "detections": "detection/detections.json",
                "mask_dir": "detection/masks",
            },
            metrics={"detection_count": 1, "peak_gpu_memory_mib": 0},
            warnings=["fake SAM output generated"],
        )


class MaskPostprocessStage(PipelineStage):
    name = "mask_postprocess"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        detections = ctx.task_dir / "detection" / "detections.json"
        if not detections.exists():
            return StageResult.failed(
                self.name,
                started_at,
                "DETECTIONS_MISSING",
                "detection/detections.json is missing",
            )
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"detections": "detection/detections.json", "mask_dir": "detection/masks"},
            metrics={"postprocessed": 1},
        )


class MogeEstimateStage(PipelineStage):
    name = "moge_estimate"
    timeout_seconds = 600

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        for relative in [
            "geometry/points.npy",
            "geometry/depth.npy",
            "geometry/normals.npy",
            "geometry/validity.npy",
        ]:
            _write_fake_npy(ctx.task_dir / relative)

        _write_json(
            ctx.task_dir / "geometry" / "camera.json",
            {
                "schemaVersion": "1.0",
                "model": "fake_moge2" if ctx.fake_models else "moge2",
                "intrinsics": {"fx": 1.0, "fy": 1.0, "cx": 0.5, "cy": 0.5},
                "unit": "relative",
            },
        )

        return StageResult.completed(
            self.name,
            started_at,
            outputs={
                "points": "geometry/points.npy",
                "depth": "geometry/depth.npy",
                "normals": "geometry/normals.npy",
                "validity": "geometry/validity.npy",
                "camera": "geometry/camera.json",
            },
            metrics={"peak_gpu_memory_mib": 0},
            warnings=["fake MoGe output generated"],
        )


class PixelAlignStage(PipelineStage):
    name = "pixel_align"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        _write_json(
            ctx.task_dir / "geometry" / "pixel_mapping.json",
            {
                "schemaVersion": "1.0",
                "samToMoge": "identity",
                "resampling": "nearest",
                "verified": False,
            },
        )
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"pixel_mapping": "geometry/pixel_mapping.json"},
        )


class GroundSolveStage(PipelineStage):
    name = "ground_solve"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        _write_json(
            ctx.task_dir / "spatial" / "ground.json",
            {
                "schemaVersion": "1.0",
                "plane": [0.0, 1.0, 0.0, 0.0],
                "normal": [0.0, 1.0, 0.0],
                "inlierRatio": 1.0,
                "pointCount": 4,
                "method": "fake",
                "confidence": 0.1,
            },
        )
        _write_json(
            ctx.task_dir / "spatial" / "coordinate_system.json",
            {
                "schemaVersion": "1.0",
                "origin": [0.0, 0.0, 0.0],
                "xAxis": [1.0, 0.0, 0.0],
                "yAxis": [0.0, 1.0, 0.0],
                "zAxis": [0.0, 0.0, 1.0],
                "unit": "relative",
            },
        )
        return StageResult.completed(
            self.name,
            started_at,
            outputs={
                "ground": "spatial/ground.json",
                "coordinate_system": "spatial/coordinate_system.json",
            },
            warnings=["fake ground plane generated"],
        )


class ObjectSolveStage(PipelineStage):
    name = "object_solve"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        objects = {
            "schemaVersion": "1.0",
            "objects": [
                {
                    "id": "building_001",
                    "category": "building",
                    "anchor": {"type": "bottom_center", "position": [0.0, 0.0, 0.0]},
                    "dimensions": {"width": 1.0, "height": 1.0, "length": 1.0, "unit": "relative"},
                    "rotation": {"yaw": 0.0, "unit": "degree"},
                    "confidence": {
                        "category": 0.9,
                        "detection": 0.9,
                        "mask": 0.5,
                        "position": 0.1,
                        "dimensions": 0.1,
                        "rotation": 0.1,
                    },
                }
            ],
        }
        _write_json(ctx.task_dir / "spatial" / "objects.json", objects)
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"objects": "spatial/objects.json"},
            metrics={"object_count": 1},
            warnings=["fake object solve generated"],
        )


class GroupSolveStage(PipelineStage):
    name = "group_solve"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        _write_json(
            ctx.task_dir / "spatial" / "groups.json",
            {"schemaVersion": "1.0", "groups": []},
        )
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"groups": "spatial/groups.json"},
        )


class ExportStage(PipelineStage):
    name = "export"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        objects = _read_json(ctx.task_dir / "spatial" / "objects.json")
        observation = {
            "schemaVersion": "1.0",
            "taskId": ctx.task_id,
            "source": "fake_pipeline" if ctx.fake_models else "pipeline",
            "objects": objects.get("objects", []),
            "artifacts": {
                "detections": "detection/detections.json",
                "ground": "spatial/ground.json",
                "coordinateSystem": "spatial/coordinate_system.json",
            },
        }
        _write_json(ctx.task_dir / "spatial" / "spatial_scene_observation.json", observation)
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"result": "spatial/spatial_scene_observation.json"},
        )


class EvaluateStage(PipelineStage):
    name = "evaluate"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        metrics = {
            "schemaVersion": "1.0",
            "proxyReprojectionIoU": None,
            "mode": "fake",
            "readyForManualReview": True,
        }
        _write_json(ctx.task_dir / "evaluation" / "metrics.json", metrics)
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"metrics": "evaluation/metrics.json"},
        )
