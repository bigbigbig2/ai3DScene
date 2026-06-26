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
from scene_spatial.visualization.ground import render_ground_candidate_preview
from scene_spatial.visualization.masks import render_pixel_alignment_preview
from scene_spatial.visualization.spatial import render_group_layout_preview, render_object_layout_preview


REGION_CATEGORIES = {"ground", "road", "vegetation_region"}
INSTANCE_SCORE_THRESHOLDS = {
    "building": 0.50,
    "street_light": 0.35,
}
INSTANCE_MAX_AREA_RATIO = {
    "building": 0.28,
    "street_light": 0.04,
}


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
            "offsetX": 0.0,
            "offsetY": 0.0,
            "resampling": "nearest",
            "verified": point_shape[0] > 0 and point_shape[1] > 0,
        }
        write_json(ctx.task_dir / "geometry" / "pixel_mapping.json", mapping)
        outputs = {"pixel_mapping": "geometry/pixel_mapping.json"}
        if render_pixel_alignment_preview(ctx.task_dir, point_shape):
            outputs["pixel_alignment_preview"] = "visualizations/pixel_alignment.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
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
        candidate_points = _finite_points(candidate_points)
        candidate_points = _mad_filter_points(candidate_points)
        if len(candidate_points) < 32:
            candidate_points = valid_points(points, validity)
            candidate_points = _mad_filter_points(candidate_points)

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
                "candidatePointCount": int(len(candidate_points)),
            },
        )
        outputs = {
            "ground": "spatial/ground.json",
            "coordinate_system": "spatial/coordinate_system.json",
            "ground_candidates": "spatial/ground_candidate_mask.json",
        }
        if render_ground_candidate_preview(ctx.task_dir, candidate_mask):
            outputs["ground_candidates_preview"] = "visualizations/ground_candidates.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={
                "ground_point_count": int(plane["pointCount"]),
                "ground_confidence": float(plane["confidence"]),
                "candidate_point_count": int(len(candidate_points)),
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
        rejected: list[dict[str, Any]] = []

        for detection in detections:
            accepted, reason = _should_solve_detection(detection, shape)
            if not accepted:
                rejected.append(_rejection_record(detection, reason, shape))
                continue

            mask = load_mask(resolve_task_path(ctx.task_dir, detection.mask_path), shape)
            if detection.object_mode == "region":
                if detection.category == "road":
                    roads.append(self._solve_road(detection.id, mask, points, validity, ground, coord))
                elif detection.category in {"ground", "vegetation_region"}:
                    objects.append(self._solve_region(detection, mask, points, validity, ground, coord))
                continue
            solved = self._solve_object(detection, mask, points, validity, ground, coord)
            objects.append(solved)

        write_json(ctx.task_dir / "spatial" / "objects.json", {"schemaVersion": "1.0", "objects": objects})
        write_json(ctx.task_dir / "spatial" / "roads.json", {"schemaVersion": "1.0", "roads": roads})
        write_json(
            ctx.task_dir / "spatial" / "rejected_detections.json",
            {"schemaVersion": "1.0", "rejected": rejected},
        )
        outputs = {
            "objects": "spatial/objects.json",
            "roads": "spatial/roads.json",
            "rejected_detections": "spatial/rejected_detections.json",
        }
        if render_object_layout_preview(ctx.task_dir):
            outputs["object_layout_preview"] = "visualizations/object_layout.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={"object_count": len(objects), "road_count": len(roads), "rejected_count": len(rejected)},
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
        origin = np.asarray(coord.get("origin", [0.0, 0.0, 0.0]), dtype=np.float64)
        x_axis = np.asarray(coord["xAxis"], dtype=np.float64)
        z_axis = np.asarray(coord["zAxis"], dtype=np.float64)
        selected_raw = points[..., :3][mask & validity] if mask.size else np.empty((0, 3))
        selected = _mad_filter_points(_finite_points(selected_raw))
        if len(selected) == 0:
            center = origin.copy()
            dims = {"width": 0.0, "height": 0.0, "length": 0.0, "unit": "relative"}
            yaw = 0.0
            confidence = 0.0
            diagnostics: dict[str, Any] = {"pointCount": 0, "rawPointCount": int(len(selected_raw))}
        else:
            projected = project_points_to_plane(selected.astype(np.float64), plane)
            uv = np.column_stack([(projected - origin) @ x_axis, (projected - origin) @ z_axis])
            bbox = oriented_bbox_2d(uv)
            center = origin + bbox["center"][0] * x_axis + bbox["center"][1] * z_axis
            distances = np.abs(signed_distance_to_plane(selected.astype(np.float64), plane))
            height = float(np.percentile(distances, 95)) if len(distances) else 0.0
            width = float(bbox["width"])
            length = float(bbox["length"])
            yaw = yaw_from_direction(bbox["direction"])
            if detection.category == "street_light":
                pole_radius = max(0.05, min(width, length, max(width, length) * 0.35))
                width = pole_radius
                length = pole_radius
                yaw = 0.0
            dims = {"width": width, "height": height, "length": length, "unit": "relative"}
            point_ratio = len(selected) / max(1, int(mask.sum()))
            confidence = min(0.95, max(0.05, point_ratio))
            diagnostics = {
                "pointCount": int(len(selected)),
                "rawPointCount": int(len(selected_raw)),
                "maskPixelCount": int(mask.sum()),
                "solverMethod": "mask_pointcloud_mad_ground_projection_min_area_rect",
            }

        needs_review = _is_suspicious_dimensions(dims) or confidence < 0.2
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
                "rotation": 0.5 if detection.category == "street_light" else confidence,
            },
            "geometryDiagnostics": diagnostics,
            "needsReview": bool(needs_review),
        }

    @staticmethod
    def _solve_region(
        detection: Any,
        mask: np.ndarray,
        points: np.ndarray,
        validity: np.ndarray,
        ground: dict[str, Any],
        coord: dict[str, Any],
    ) -> dict[str, Any]:
        plane = ground["plane"]
        origin = np.asarray(coord.get("origin", [0.0, 0.0, 0.0]), dtype=np.float64)
        x_axis = np.asarray(coord["xAxis"], dtype=np.float64)
        z_axis = np.asarray(coord["zAxis"], dtype=np.float64)
        selected = _mad_filter_points(_finite_points(points[..., :3][mask & validity])) if mask.size else np.empty((0, 3))
        if len(selected) == 0:
            center = origin.copy()
            width = length = 0.0
        else:
            projected = project_points_to_plane(selected.astype(np.float64), plane)
            uv = np.column_stack([(projected - origin) @ x_axis, (projected - origin) @ z_axis])
            bbox = oriented_bbox_2d(uv)
            center = origin + bbox["center"][0] * x_axis + bbox["center"][1] * z_axis
            width = float(bbox["width"])
            length = float(bbox["length"])
        return {
            "id": detection.id,
            "category": detection.category,
            "anchor": {"type": "region_center", "position": [float(v) for v in center.tolist()]},
            "dimensions": {"width": width, "height": 0.05, "length": length, "unit": "relative"},
            "rotation": {"yaw": 0.0, "unit": "degree"},
            "source": {"bbox": list(detection.bbox), "maskPath": detection.mask_path},
            "confidence": {
                "category": float(detection.score),
                "detection": float(detection.score),
                "mask": 0.8 if int(mask.sum()) > 0 else 0.0,
                "position": 0.5,
                "dimensions": 0.5,
                "rotation": 0.0,
            },
            "geometryDiagnostics": {"pointCount": int(len(selected)), "solverMethod": "region_ground_projection"},
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
        origin = np.asarray(coord.get("origin", [0.0, 0.0, 0.0]), dtype=np.float64)
        x_axis = np.asarray(coord["xAxis"], dtype=np.float64)
        z_axis = np.asarray(coord["zAxis"], dtype=np.float64)
        selected = _mad_filter_points(_finite_points(points[..., :3][mask & validity])) if mask.size else np.empty((0, 3))
        if len(selected) == 0:
            return {"id": road_id, "polygon3d": [], "centerline": [], "confidence": 0.0}
        projected = project_points_to_plane(selected.astype(np.float64), ground["plane"])
        uv = np.column_stack([(projected - origin) @ x_axis, (projected - origin) @ z_axis])
        bbox = oriented_bbox_2d(uv)
        direction = np.asarray(bbox["direction"], dtype=np.float64)
        center = np.asarray(bbox["center"], dtype=np.float64)
        half_len = bbox["length"] * 0.5
        endpoints_uv = [center - direction * half_len, center + direction * half_len]
        centerline = [(origin + point[0] * x_axis + point[1] * z_axis).tolist() for point in endpoints_uv]
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
        outputs = {"groups": "spatial/groups.json"}
        if render_group_layout_preview(ctx.task_dir):
            outputs["group_layout_preview"] = "visualizations/group_layout.png"
        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={"group_count": len(groups)},
        )

    @staticmethod
    def _solve_groups(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        by_category: dict[str, list[dict[str, Any]]] = {}
        for obj in objects:
            if not _is_group_candidate(obj):
                continue
            by_category.setdefault(str(obj.get("category", "unknown")), []).append(obj)

        for category, items in by_category.items():
            min_size = 4 if category == "street_light" else 3
            points = np.asarray([_center_xz(item) for item in items], dtype=np.float64)
            clusters = _cluster_points(points, min_size=min_size)
            for cluster_index, indices in enumerate(clusters, start=1):
                cluster_items = [items[index] for index in indices]
                centers = np.asarray([item["anchor"]["position"] for item in cluster_items], dtype=np.float64)
                centered = centers - centers.mean(axis=0)
                _, _, vh = np.linalg.svd(centered, full_matrices=False)
                axis_a = vh[0]
                axis_b = vh[1] if len(vh) > 1 else np.array([0.0, 0.0, 1.0])
                coords_a = centers @ axis_a
                coords_b = centers @ axis_b
                spacing_a = median_spacing(coords_a)
                spacing_b = median_spacing(coords_b)
                edges = _nearest_edges(cluster_items)
                groups.append(
                    {
                        "id": f"{category}_group_{cluster_index:03d}",
                        "category": category,
                        "objectIds": [str(item["id"]) for item in cluster_items],
                        "patternType": _pattern_type(category, spacing_a, spacing_b, len(cluster_items)),
                        "axisA": axis_a.tolist(),
                        "axisB": axis_b.tolist(),
                        "spacing": [spacing_a, spacing_b],
                        "edges": edges,
                        "confidence": min(0.85, 0.35 + len(cluster_items) * 0.05),
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


def _finite_points(points: np.ndarray) -> np.ndarray:
    if len(points) == 0:
        return points
    return points[np.isfinite(points).all(axis=1)]


def _mad_filter_points(points: np.ndarray, threshold: float = 4.5) -> np.ndarray:
    if len(points) < 16:
        return points
    median = np.median(points, axis=0)
    mad = np.median(np.abs(points - median), axis=0)
    mad = np.maximum(mad, 1e-6)
    keep = (np.abs(points - median) / mad < threshold).all(axis=1)
    filtered = points[keep]
    return filtered if len(filtered) >= 8 else points


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
    if detection.category == "street_light" and bbox_h < 10:
        return False, "street_light_bbox_too_short"
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


def _is_suspicious_dimensions(dims: dict[str, float | str]) -> bool:
    values = [float(dims.get(key, 0.0) or 0.0) for key in ["width", "height", "length"]]
    return min(values) <= 0.0 or max(values) > 300.0


def _is_group_candidate(obj: dict[str, Any]) -> bool:
    if obj.get("category") in REGION_CATEGORIES:
        return False
    if obj.get("needsReview"):
        return False
    confidence = obj.get("confidence", {}) if isinstance(obj.get("confidence"), dict) else {}
    if float(confidence.get("detection", 0.0) or 0.0) < 0.45:
        return False
    dims = obj.get("dimensions", {}) if isinstance(obj.get("dimensions"), dict) else {}
    return not _is_suspicious_dimensions(dims)


def _center_xz(obj: dict[str, Any]) -> list[float]:
    position = obj.get("anchor", {}).get("position", [0.0, 0.0, 0.0])
    return [float(position[0]), float(position[2])]


def _cluster_points(points: np.ndarray, min_size: int) -> list[list[int]]:
    if len(points) < min_size:
        return []
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=-1)
    nonzero = distances[distances > 1e-6]
    if len(nonzero) == 0:
        return [list(range(len(points)))] if len(points) >= min_size else []
    nearest = np.min(np.where(distances > 1e-6, distances, np.inf), axis=1)
    nearest = nearest[np.isfinite(nearest)]
    eps = float(np.median(nearest) * 2.6) if len(nearest) else float(np.percentile(nonzero, 20))
    eps = max(eps, float(np.percentile(nonzero, 10)))
    visited: set[int] = set()
    clusters: list[list[int]] = []
    for start in range(len(points)):
        if start in visited:
            continue
        queue = [start]
        visited.add(start)
        cluster: list[int] = []
        while queue:
            current = queue.pop()
            cluster.append(current)
            neighbors = np.where(distances[current] <= eps)[0]
            for neighbor in neighbors:
                if int(neighbor) not in visited:
                    visited.add(int(neighbor))
                    queue.append(int(neighbor))
        if len(cluster) >= min_size:
            clusters.append(sorted(cluster))
    return clusters


def _nearest_edges(items: list[dict[str, Any]]) -> list[list[str]]:
    if len(items) < 2:
        return []
    points = np.asarray([_center_xz(item) for item in items], dtype=np.float64)
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=-1)
    nonzero = distances[distances > 1e-6]
    if len(nonzero) == 0:
        return []
    threshold = float(np.median(nonzero) * 1.8)
    edges: set[tuple[str, str]] = set()
    for index, item in enumerate(items):
        row = distances[index].copy()
        row[index] = np.inf
        neighbor = int(np.argmin(row))
        if np.isfinite(row[neighbor]) and row[neighbor] <= threshold:
            a, b = sorted([str(item["id"]), str(items[neighbor]["id"])])
            edges.add((a, b))
    return [[a, b] for a, b in sorted(edges)]


def _pattern_type(category: str, spacing_a: float, spacing_b: float, count: int) -> str:
    if category == "street_light":
        return "along_path" if count >= 4 else "cluster"
    if spacing_a > 0 and spacing_b > 0 and count >= 6:
        return "grid"
    if spacing_a > 0:
        return "row"
    return "cluster"


def median_spacing(values: np.ndarray) -> float:
    if len(values) < 2:
        return 0.0
    sorted_values = np.sort(values)
    diffs = np.diff(sorted_values)
    diffs = diffs[diffs > 1e-6]
    return float(np.median(diffs)) if len(diffs) else 0.0