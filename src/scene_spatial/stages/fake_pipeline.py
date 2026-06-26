from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from scene_spatial.domain.stage import StageContext, StageResult
from scene_spatial.stages.base import PipelineStage
from scene_spatial.visualization.depth import (
    render_depth_preview,
    render_normals_preview,
    render_validity_preview,
)
from scene_spatial.visualization.ground import render_ground_candidate_preview
from scene_spatial.visualization.masks import (
    postprocess_overlay_path,
    render_pixel_alignment_preview,
    render_detection_overlay,
    render_mask_contact_sheet,
)
from scene_spatial.visualization.pointcloud import write_scene_pointcloud
from scene_spatial.visualization.spatial import (
    render_group_layout_preview,
    render_object_layout_preview,
    render_scene_preview_report,
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_fake_geometry(task_dir: Path) -> None:
    metadata = _read_json(task_dir / "input" / "metadata.json")
    width = int(metadata.get("width", 64))
    height = int(metadata.get("height", 48))
    xs = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    zs = np.linspace(0.2, 2.0, height, dtype=np.float32)
    grid_x, grid_z = np.meshgrid(xs, zs)
    grid_y = np.zeros_like(grid_x)
    points = np.stack([grid_x, grid_y, grid_z], axis=-1)
    depth = grid_z.copy()
    normals = np.zeros_like(points)
    normals[..., 1] = 1.0
    validity = np.ones((height, width), dtype=bool)
    geometry_dir = task_dir / "geometry"
    geometry_dir.mkdir(parents=True, exist_ok=True)
    np.save(geometry_dir / "points.npy", points)
    np.save(geometry_dir / "depth.npy", depth)
    np.save(geometry_dir / "normals.npy", normals)
    np.save(geometry_dir / "validity.npy", validity)


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

        outputs = {
            "detections": "detection/detections.json",
            "mask_dir": "detection/masks",
        }
        if render_detection_overlay(ctx.task_dir):
            outputs["detection_overlay"] = "visualizations/detection_overlay.png"
        if render_mask_contact_sheet(ctx.task_dir):
            outputs["mask_contact_sheet"] = "visualizations/mask_contact_sheet.png"

        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
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
        outputs = {"detections": "detection/detections.json", "mask_dir": "detection/masks"}
        if render_detection_overlay(ctx.task_dir, output_path=postprocess_overlay_path(ctx.task_dir)):
            outputs["postprocess_overlay"] = "visualizations/postprocess_overlay.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={"postprocessed": 1},
        )


class MogeEstimateStage(PipelineStage):
    name = "moge_estimate"
    timeout_seconds = 600

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        _write_fake_geometry(ctx.task_dir)

        _write_json(
            ctx.task_dir / "geometry" / "camera.json",
            {
                "schemaVersion": "1.0",
                "model": "fake_moge2" if ctx.fake_models else "moge2",
                "intrinsics": {"fx": 1.0, "fy": 1.0, "cx": 0.5, "cy": 0.5},
                "unit": "relative",
            },
        )

        outputs = {
            "points": "geometry/points.npy",
            "depth": "geometry/depth.npy",
            "normals": "geometry/normals.npy",
            "validity": "geometry/validity.npy",
            "camera": "geometry/camera.json",
        }
        if render_depth_preview(ctx.task_dir):
            outputs["depth_preview"] = "visualizations/depth.png"
        if render_normals_preview(ctx.task_dir):
            outputs["normals_preview"] = "visualizations/normals.png"
        if render_validity_preview(ctx.task_dir):
            outputs["validity_preview"] = "visualizations/validity.png"
        if write_scene_pointcloud(ctx.task_dir):
            outputs["pointcloud"] = "pointcloud/scene.ply"

        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
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
        metadata = _read_json(ctx.task_dir / "input" / "metadata.json")
        point_shape = [int(metadata.get("height", 0)), int(metadata.get("width", 0))]
        outputs = {"pixel_mapping": "geometry/pixel_mapping.json"}
        if render_pixel_alignment_preview(ctx.task_dir, point_shape):
            outputs["pixel_alignment_preview"] = "visualizations/pixel_alignment.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
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
        metadata = _read_json(ctx.task_dir / "input" / "metadata.json")
        candidate_mask = np.ones((int(metadata["height"]), int(metadata["width"])), dtype=bool)
        outputs = {
            "ground": "spatial/ground.json",
            "coordinate_system": "spatial/coordinate_system.json",
        }
        if render_ground_candidate_preview(ctx.task_dir, candidate_mask):
            outputs["ground_candidates_preview"] = "visualizations/ground_candidates.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
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
        outputs = {"objects": "spatial/objects.json"}
        if render_object_layout_preview(ctx.task_dir):
            outputs["object_layout_preview"] = "visualizations/object_layout.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
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
        outputs = {"groups": "spatial/groups.json"}
        if render_group_layout_preview(ctx.task_dir):
            outputs["group_layout_preview"] = "visualizations/group_layout.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
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
        outputs = {"result": "spatial/spatial_scene_observation.json"}
        if render_scene_preview_report(ctx.task_dir):
            outputs["scene_preview_report"] = "visualizations/scene_preview.html"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
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

