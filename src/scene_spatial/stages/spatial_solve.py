from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from scene_spatial.domain.stage import StageContext, StageResult
from scene_spatial.spatial.alignment.pixel_transform import build_pixel_mapping
from scene_spatial.spatial.ground.candidate_selector import candidate_points, select_ground_candidates
from scene_spatial.spatial.ground.ransac_plane import solve_ground_plane
from scene_spatial.spatial.grouping import solve_groups
from scene_spatial.spatial.quality.geometry_validator import validate_objects
from scene_spatial.spatial.quality.reprojection_validator import summarize_reprojection_readiness
from scene_spatial.spatial.solver_utils import (
    bbox_iou,
    load_array,
    load_detections,
    load_mask,
    load_validity,
    mask_bbox,
    read_json,
    resolve_task_path,
    write_json,
)
from scene_spatial.spatial.solvers import SolverContext, solve_detection
from scene_spatial.stages.base import PipelineStage
from scene_spatial.visualization.ground import render_ground_candidate_preview
from scene_spatial.visualization.masks import render_pixel_alignment_preview
from scene_spatial.visualization.spatial import render_group_layout_preview, render_object_layout_preview

INSTANCE_SCORE_THRESHOLDS = {
    "building": 0.50,
    "rectangular_treatment_pool": 0.45,
    "tree": 0.30,
    "street_light": 0.35,
}
INSTANCE_MAX_AREA_RATIO = {
    "building": 0.28,
    "rectangular_treatment_pool": 0.18,
    "tree": 0.08,
    "street_light": 0.04,
}
REGION_CATEGORIES = {"ground", "road", "vegetation_region", "water"}
REGION_MASK_SUBTRACTION_CATEGORIES = {"building", "rectangular_treatment_pool", "tree", "street_light"}


class PixelAlignStage(PipelineStage):
    name = "pixel_align"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        points = load_array(ctx.task_dir / "geometry" / "points.npy")
        point_shape = tuple(points.shape[:2]) if points.ndim >= 2 else (0, 0)
        metadata = read_json(ctx.task_dir / "input" / "metadata.json")
        mapping = build_pixel_mapping(metadata, point_shape)
        write_json(ctx.task_dir / "geometry" / "pixel_mapping.json", mapping)

        outputs = {"pixel_mapping": "geometry/pixel_mapping.json"}
        if render_pixel_alignment_preview(ctx.task_dir, point_shape):
            outputs["pixel_alignment_preview"] = "visualizations/pixel_alignment.png"
        sam_to_moge = mapping.get("samToMoge", {}) if isinstance(mapping.get("samToMoge"), dict) else {}
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={
                "point_map_height": int(point_shape[0]),
                "point_map_width": int(point_shape[1]),
                "scale_x": float(sam_to_moge.get("scaleX", 1.0)),
                "scale_y": float(sam_to_moge.get("scaleY", 1.0)),
            },
        )


class GroundSolveStage(PipelineStage):
    name = "ground_solve"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        points = load_array(ctx.task_dir / "geometry" / "points.npy")
        shape = points.shape[:2] if points.ndim >= 2 else (0, 0)
        validity = load_validity(ctx.task_dir / "geometry" / "validity.npy", shape)
        normals = _load_optional_array(ctx.task_dir / "geometry" / "normals.npy", shape)

        selected = select_ground_candidates(ctx.task_dir, shape, validity, normals)
        selected_points = candidate_points(points, validity, selected.mask)
        ground, coord, diagnostics = solve_ground_plane(points, validity, selected_points, normals)
        diagnostics.update(selected.diagnostics)

        write_json(ctx.task_dir / "spatial" / "ground.json", ground)
        write_json(ctx.task_dir / "spatial" / "coordinate_system.json", coord)
        write_json(ctx.task_dir / "spatial" / "ground_candidate_mask.json", {"schemaVersion": "1.0", **selected.diagnostics})
        write_json(ctx.task_dir / "spatial" / "ground_diagnostics.json", {"schemaVersion": "1.0", **diagnostics})

        outputs = {
            "ground": "spatial/ground.json",
            "coordinate_system": "spatial/coordinate_system.json",
            "ground_candidates": "spatial/ground_candidate_mask.json",
            "ground_diagnostics": "spatial/ground_diagnostics.json",
        }
        if render_ground_candidate_preview(ctx.task_dir, selected.mask):
            outputs["ground_candidates_preview"] = "visualizations/ground_candidates.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={
                "ground_point_count": int(ground.get("pointCount", 0)),
                "ground_confidence": float(ground.get("confidence", 0.0)),
                "candidate_point_count": int(len(selected_points)),
            },
        )


class ObjectSolveStage(PipelineStage):
    name = "object_solve"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        points = load_array(ctx.task_dir / "geometry" / "points.npy")
        shape = points.shape[:2] if points.ndim >= 2 else (0, 0)
        validity = load_validity(ctx.task_dir / "geometry" / "validity.npy", shape)
        ground = read_json(ctx.task_dir / "spatial" / "ground.json")
        coord = read_json(ctx.task_dir / "spatial" / "coordinate_system.json")
        detections = load_detections(ctx.task_dir)
        region_exclusion_mask, region_exclusion_counts = _build_region_exclusion_mask(ctx.task_dir, detections, shape)
        solver_ctx = SolverContext(points=points, validity=validity, ground=ground, coord=coord)

        objects: list[dict[str, Any]] = []
        roads: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for detection in detections:
            accepted, reason = _should_solve_detection(detection, shape)
            if not accepted:
                rejected.append(_rejection_record(detection, reason, shape))
                continue
            mask = load_mask(resolve_task_path(ctx.task_dir, detection.mask_path), shape)
            original_mask_pixels = int(mask.sum())
            if _is_region_detection(detection):
                mask = mask & ~region_exclusion_mask
                if original_mask_pixels > 0 and int(mask.sum()) < 8:
                    rejected.append(_rejection_record(detection, "region_empty_after_instance_subtraction", shape))
                    continue
            obj, road = solve_detection(detection, mask, solver_ctx)
            if obj is not None:
                objects.append(obj)
            if road is not None:
                roads.append(road)

        objects, quality = validate_objects(objects)
        diagnostics = {
            "schemaVersion": "1.0",
            "solverArchitecture": "category_specific_geometry_chain",
            "objectCount": len(objects),
            "roadCount": len(roads),
            "rejectedDetectionCount": len(rejected),
            "quality": quality,
            "categoryCounts": _category_counts(objects),
            "regionMaskSubtraction": {
                "categories": region_exclusion_counts,
                "subtractedPixelCount": int(region_exclusion_mask.sum()),
                "policy": "subtract building/tree/street_light instance masks from region masks before region solving",
            },
        }
        write_json(ctx.task_dir / "spatial" / "objects.json", {"schemaVersion": "1.0", "objects": objects})
        write_json(ctx.task_dir / "spatial" / "roads.json", {"schemaVersion": "1.0", "roads": roads})
        write_json(ctx.task_dir / "spatial" / "rejected_detections.json", {"schemaVersion": "1.0", "rejected": rejected})
        write_json(ctx.task_dir / "spatial" / "object_diagnostics.json", diagnostics)

        outputs = {
            "objects": "spatial/objects.json",
            "roads": "spatial/roads.json",
            "rejected_detections": "spatial/rejected_detections.json",
            "object_diagnostics": "spatial/object_diagnostics.json",
        }
        if render_object_layout_preview(ctx.task_dir):
            outputs["object_layout_preview"] = "visualizations/object_layout.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={
                "object_count": len(objects),
                "road_count": len(roads),
                "tree_count": diagnostics["categoryCounts"].get("tree", 0),
                "rejected_count": len(rejected),
            },
        )


class GroupSolveStage(PipelineStage):
    name = "group_solve"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        objects_payload = read_json(ctx.task_dir / "spatial" / "objects.json")
        coord = read_json(ctx.task_dir / "spatial" / "coordinate_system.json")
        objects = objects_payload.get("objects", []) if isinstance(objects_payload.get("objects"), list) else []
        groups = solve_groups(objects, coord)
        diagnostics = summarize_reprojection_readiness(objects, groups)
        diagnostics["solverArchitecture"] = "hdbscan_pca_ransac_grid_along_path"

        write_json(ctx.task_dir / "spatial" / "groups.json", {"schemaVersion": "1.0", "groups": groups})
        write_json(ctx.task_dir / "spatial" / "group_diagnostics.json", diagnostics)
        outputs = {"groups": "spatial/groups.json", "group_diagnostics": "spatial/group_diagnostics.json"}
        if render_group_layout_preview(ctx.task_dir):
            outputs["group_layout_preview"] = "visualizations/group_layout.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={"group_count": len(groups)},
        )


class EvaluateStage(PipelineStage):
    name = "evaluate"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        detections = load_detections(ctx.task_dir)
        points = load_array(ctx.task_dir / "geometry" / "points.npy")
        shape = points.shape[:2] if points.ndim >= 2 else (0, 0)
        ious: list[float] = []
        for detection in detections:
            if not detection.mask_path:
                continue
            mask = load_mask(resolve_task_path(ctx.task_dir, detection.mask_path), shape)
            computed_bbox = mask_bbox(mask)
            if computed_bbox is not None:
                ious.append(bbox_iou(detection.bbox, computed_bbox))
        group_diag = read_json(ctx.task_dir / "spatial" / "group_diagnostics.json") if (ctx.task_dir / "spatial" / "group_diagnostics.json").exists() else {}
        metrics = {
            "schemaVersion": "1.0",
            "maskBBoxIoU": float(np.mean(ious)) if ious else None,
            "evaluatedDetections": len(ious),
            "needsReviewCount": group_diag.get("needsReviewCount"),
            "readyForManualReview": True,
        }
        write_json(ctx.task_dir / "evaluation" / "metrics.json", metrics)
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"metrics": "evaluation/metrics.json"},
            metrics={"evaluated_detections": len(ious)},
        )


def _build_region_exclusion_mask(task_dir: Path, detections: list[Any], shape: tuple[int, int]) -> tuple[np.ndarray, dict[str, int]]:
    mask = np.zeros(shape, dtype=bool)
    counts: dict[str, int] = {}
    for detection in detections:
        if detection.category not in REGION_MASK_SUBTRACTION_CATEGORIES or not detection.mask_path:
            continue
        instance_mask = load_mask(resolve_task_path(task_dir, detection.mask_path), shape)
        counts[detection.category] = counts.get(detection.category, 0) + int(instance_mask.sum())
        mask |= instance_mask
    return mask, counts


def _is_region_detection(detection: Any) -> bool:
    return detection.object_mode == "region" or detection.category in REGION_CATEGORIES


def _load_optional_array(path: Path, shape: tuple[int, int]) -> np.ndarray | None:
    if not path.exists():
        return None
    value = load_array(path)
    if value.ndim >= 2 and value.shape[:2] == shape:
        return value
    return None


def _should_solve_detection(detection: Any, shape: tuple[int, int]) -> tuple[bool, str | None]:
    if detection.object_mode == "region":
        return True, None
    score_threshold = INSTANCE_SCORE_THRESHOLDS.get(detection.category, 0.35)
    if float(detection.score) < score_threshold:
        return False, f"low_score<{score_threshold:.2f}"
    bbox_w = max(0, int(detection.bbox[2]) - int(detection.bbox[0]))
    bbox_h = max(0, int(detection.bbox[3]) - int(detection.bbox[1]))
    if detection.category == "building" and (bbox_w < 10 or bbox_h < 10):
        return False, "building_bbox_too_small"
    if detection.category in {"street_light", "tree"} and bbox_h < 8:
        return False, f"{detection.category}_bbox_too_short"
    area_ratio = _bbox_area_ratio(detection.bbox, shape)
    max_area = INSTANCE_MAX_AREA_RATIO.get(detection.category, 0.35)
    if area_ratio > max_area:
        return False, f"bbox_area_ratio>{max_area:.2f}"
    return True, None


def _rejection_record(detection: Any, reason: str | None, shape: tuple[int, int]) -> dict[str, Any]:
    return {
        "id": detection.id,
        "category": detection.category,
        "score": float(detection.score),
        "bbox": list(detection.bbox),
        "bboxAreaRatio": _bbox_area_ratio(detection.bbox, shape),
        "reason": reason or "unknown",
    }


def _bbox_area_ratio(bbox: tuple[int, int, int, int], shape: tuple[int, int]) -> float:
    height, width = shape
    if height <= 0 or width <= 0:
        return 0.0
    bbox_w = max(0, int(bbox[2]) - int(bbox[0]))
    bbox_h = max(0, int(bbox[3]) - int(bbox[1]))
    return float((bbox_w * bbox_h) / max(1, width * height))


def _category_counts(objects: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for obj in objects:
        category = str(obj.get("category", "unknown"))
        counts[category] = counts.get(category, 0) + 1
    return counts

