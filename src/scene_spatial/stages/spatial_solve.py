from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from scene_spatial.domain.stage import StageContext, StageResult
from scene_spatial.spatial.solver_utils import (
    bbox_iou,
    fit_plane_ransac,
    load_array,
    load_detections,
    load_mask,
    load_validity,
    mask_bbox,
    oriented_bbox_2d,
    plane_basis,
    project_points_to_plane,
    read_json,
    resolve_task_path,
    signed_distance_to_plane,
    valid_points,
    write_json,
    yaw_from_direction,
)
from scene_spatial.stages.base import PipelineStage


class PixelAlignStage(PipelineStage):
    name = "pixel_align"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        points = load_array(ctx.task_dir / "geometry" / "points.npy")
        point_shape = list(points.shape[:2]) if points.ndim >= 2 else [0, 0]
        metadata = read_json(ctx.task_dir / "input" / "metadata.json")
        source_shape = [int(metadata.get("height", 0)), int(metadata.get("width", 0))]
        mapping = {
            "schemaVersion": "1.0",
            "sourceImageShape": source_shape,
            "pointMapShape": point_shape,
            "samToMoge": "scale_nearest",
            "scaleY": float(point_shape[0] / source_shape[0]) if source_shape[0] else 1.0,
            "scaleX": float(point_shape[1] / source_shape[1]) if source_shape[1] else 1.0,
            "resampling": "nearest",
            "verified": point_shape[0] > 0 and point_shape[1] > 0,
        }
        write_json(ctx.task_dir / "geometry" / "pixel_mapping.json", mapping)
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"pixel_mapping": "geometry/pixel_mapping.json"},
            metrics={"point_map_height": point_shape[0], "point_map_width": point_shape[1]},
        )


class GroundSolveStage(PipelineStage):
    name = "ground_solve"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        points = load_array(ctx.task_dir / "geometry" / "points.npy")
        shape = points.shape[:2] if points.ndim >= 2 else (0, 0)
        validity = load_validity(ctx.task_dir / "geometry" / "validity.npy", shape)
        candidate_mask = self._candidate_mask(ctx.task_dir, shape)
        candidate_points = points[..., :3][candidate_mask & validity] if shape != (0, 0) else np.empty((0, 3))
        if len(candidate_points) < 32:
            candidate_points = valid_points(points, validity)

        plane = fit_plane_ransac(candidate_points)
        normal = np.asarray(plane["normal"], dtype=np.float64)
        x_axis, y_axis, z_axis = plane_basis(normal)
        origin = np.zeros(3, dtype=np.float64)
        if len(candidate_points):
            projected = project_points_to_plane(candidate_points.astype(np.float64), plane["plane"])
            origin = np.median(projected, axis=0)

        write_json(ctx.task_dir / "spatial" / "ground.json", {"schemaVersion": "1.0", **plane})
        write_json(
            ctx.task_dir / "spatial" / "coordinate_system.json",
            {
                "schemaVersion": "1.0",
                "origin": origin.tolist(),
                "xAxis": x_axis.tolist(),
                "yAxis": y_axis.tolist(),
                "zAxis": z_axis.tolist(),
                "unit": "relative",
            },
        )
        write_json(
            ctx.task_dir / "spatial" / "ground_candidate_mask.json",
            {
                "schemaVersion": "1.0",
                "candidatePixelCount": int(candidate_mask.sum()) if candidate_mask.size else 0,
            },
        )
        return StageResult.completed(
            self.name,
            started_at,
            outputs={
                "ground": "spatial/ground.json",
                "coordinate_system": "spatial/coordinate_system.json",
                "ground_candidates": "spatial/ground_candidate_mask.json",
            },
            metrics={
                "ground_point_count": int(plane["pointCount"]),
                "ground_confidence": float(plane["confidence"]),
            },
        )

    @staticmethod
    def _candidate_mask(task_dir: Path, shape: tuple[int, int]) -> np.ndarray:
        if shape == (0, 0):
            return np.zeros(shape, dtype=bool)
        detections = load_detections(task_dir)
        candidate = np.zeros(shape, dtype=bool)
        exclusions = np.zeros(shape, dtype=bool)
        for detection in detections:
            mask = load_mask(resolve_task_path(task_dir, detection.mask_path), shape)
            if detection.category in {"ground", "road", "vegetation_region"}:
                candidate |= mask
            if detection.category in {"building", "rectangular_treatment_pool", "street_light", "water"}:
                exclusions |= mask
        return candidate & ~exclusions if candidate.any() else ~exclusions


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
        objects: list[dict[str, Any]] = []
        roads: list[dict[str, Any]] = []

        for detection in detections:
            mask = load_mask(resolve_task_path(ctx.task_dir, detection.mask_path), shape)
            if detection.object_mode == "region":
                if detection.category == "road":
                    roads.append(self._solve_road(detection.id, mask, points, validity, ground, coord))
                continue
            solved = self._solve_object(detection, mask, points, validity, ground, coord)
            objects.append(solved)

        write_json(ctx.task_dir / "spatial" / "objects.json", {"schemaVersion": "1.0", "objects": objects})
        write_json(ctx.task_dir / "spatial" / "roads.json", {"schemaVersion": "1.0", "roads": roads})
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"objects": "spatial/objects.json", "roads": "spatial/roads.json"},
            metrics={"object_count": len(objects), "road_count": len(roads)},
        )

    @staticmethod
    def _solve_object(
        detection: Any,
        mask: np.ndarray,
        points: np.ndarray,
        validity: np.ndarray,
        ground: dict[str, Any],
        coord: dict[str, Any],
    ) -> dict[str, Any]:
        plane = ground["plane"]
        normal = np.asarray(ground["normal"], dtype=np.float64)
        x_axis = np.asarray(coord["xAxis"], dtype=np.float64)
        z_axis = np.asarray(coord["zAxis"], dtype=np.float64)
        selected = points[..., :3][mask & validity] if mask.size else np.empty((0, 3))
        selected = selected[np.isfinite(selected).all(axis=1)] if len(selected) else selected
        if len(selected) == 0:
            center = np.zeros(3)
            dims = {"width": 0.0, "height": 0.0, "length": 0.0, "unit": "relative"}
            yaw = 0.0
            confidence = 0.0
        else:
            projected = project_points_to_plane(selected.astype(np.float64), plane)
            uv = np.column_stack([projected @ x_axis, projected @ z_axis])
            bbox = oriented_bbox_2d(uv)
            center = bbox["center"][0] * x_axis + bbox["center"][1] * z_axis
            distances = np.abs(signed_distance_to_plane(selected.astype(np.float64), plane))
            height = float(np.percentile(distances, 95)) if len(distances) else 0.0
            dims = {
                "width": float(bbox["width"]),
                "height": height,
                "length": float(bbox["length"]),
                "unit": "relative",
            }
            yaw = yaw_from_direction(bbox["direction"])
            confidence = min(0.95, max(0.15, len(selected) / max(1, int(mask.sum()))))

        return {
            "id": detection.id,
            "category": detection.category,
            "anchor": {"type": "bottom_center", "position": [float(v) for v in center.tolist()]},
            "dimensions": dims,
            "rotation": {"yaw": float(yaw), "unit": "degree"},
            "source": {"bbox": list(detection.bbox), "maskPath": detection.mask_path},
            "confidence": {
                "category": float(detection.score),
                "detection": float(detection.score),
                "mask": 0.8 if int(mask.sum()) > 0 else 0.0,
                "position": confidence,
                "dimensions": confidence,
                "rotation": confidence,
            },
        }

    @staticmethod
    def _solve_road(
        road_id: str,
        mask: np.ndarray,
        points: np.ndarray,
        validity: np.ndarray,
        ground: dict[str, Any],
        coord: dict[str, Any],
    ) -> dict[str, Any]:
        x_axis = np.asarray(coord["xAxis"], dtype=np.float64)
        z_axis = np.asarray(coord["zAxis"], dtype=np.float64)
        selected = points[..., :3][mask & validity] if mask.size else np.empty((0, 3))
        selected = selected[np.isfinite(selected).all(axis=1)] if len(selected) else selected
        if len(selected) == 0:
            return {"id": road_id, "polygon3d": [], "centerline": [], "confidence": 0.0}
        projected = project_points_to_plane(selected.astype(np.float64), ground["plane"])
        uv = np.column_stack([projected @ x_axis, projected @ z_axis])
        bbox = oriented_bbox_2d(uv)
        direction = np.asarray(bbox["direction"], dtype=np.float64)
        center = np.asarray(bbox["center"], dtype=np.float64)
        half_len = bbox["length"] * 0.5
        endpoints_uv = [center - direction * half_len, center + direction * half_len]
        centerline = [(point[0] * x_axis + point[1] * z_axis).tolist() for point in endpoints_uv]
        return {
            "id": road_id,
            "polygon3d": [],
            "centerline": [[float(v) for v in point] for point in centerline],
            "estimatedWidth": float(bbox["width"]),
            "mainDirection": [float(direction[0]), float(direction[1])],
            "confidence": 0.5,
        }


class GroupSolveStage(PipelineStage):
    name = "group_solve"

    def execute(self, ctx: StageContext) -> StageResult:
        started_at = datetime.now(UTC)
        objects_payload = read_json(ctx.task_dir / "spatial" / "objects.json")
        groups = self._solve_groups(objects_payload.get("objects", []))
        write_json(ctx.task_dir / "spatial" / "groups.json", {"schemaVersion": "1.0", "groups": groups})
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"groups": "spatial/groups.json"},
            metrics={"group_count": len(groups)},
        )

    @staticmethod
    def _solve_groups(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        by_category: dict[str, list[dict[str, Any]]] = {}
        for obj in objects:
            by_category.setdefault(str(obj.get("category", "unknown")), []).append(obj)
        for category, items in by_category.items():
            if len(items) < 3:
                continue
            centers = np.asarray([item["anchor"]["position"] for item in items], dtype=np.float64)
            centered = centers - centers.mean(axis=0)
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
            axis_a, axis_b = vh[0], vh[1]
            coords_a = centers @ axis_a
            coords_b = centers @ axis_b
            spacing_a = median_spacing(coords_a)
            spacing_b = median_spacing(coords_b)
            groups.append(
                {
                    "id": f"{category}_group_001",
                    "category": category,
                    "objectIds": [str(item["id"]) for item in items],
                    "patternType": "grid" if spacing_a > 0 and spacing_b > 0 else "row",
                    "axisA": axis_a.tolist(),
                    "axisB": axis_b.tolist(),
                    "spacing": [spacing_a, spacing_b],
                    "confidence": 0.6,
                }
            )
        return groups


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
        metrics = {
            "schemaVersion": "1.0",
            "maskBBoxIoU": float(np.mean(ious)) if ious else None,
            "evaluatedDetections": len(ious),
            "readyForManualReview": True,
        }
        write_json(ctx.task_dir / "evaluation" / "metrics.json", metrics)
        return StageResult.completed(
            self.name,
            started_at,
            outputs={"metrics": "evaluation/metrics.json"},
            metrics={"evaluated_detections": len(ious)},
        )


def median_spacing(values: np.ndarray) -> float:
    if len(values) < 2:
        return 0.0
    sorted_values = np.sort(values)
    diffs = np.diff(sorted_values)
    diffs = diffs[diffs > 1e-6]
    return float(np.median(diffs)) if len(diffs) else 0.0
