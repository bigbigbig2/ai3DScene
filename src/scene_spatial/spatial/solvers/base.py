from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from scene_spatial.spatial.solver_utils import (
    oriented_bbox_2d,
    project_points_to_plane,
    signed_distance_to_plane,
    yaw_from_direction,
)


@dataclass(frozen=True)
class SolverContext:
    points: np.ndarray
    validity: np.ndarray
    ground: dict[str, Any]
    coord: dict[str, Any]

    @property
    def plane(self) -> list[float]:
        return list(self.ground.get("plane", [0.0, 1.0, 0.0, 0.0]))

    @property
    def origin(self) -> np.ndarray:
        return np.asarray(self.coord.get("origin", [0.0, 0.0, 0.0]), dtype=np.float64)

    @property
    def x_axis(self) -> np.ndarray:
        return np.asarray(self.coord.get("xAxis", [1.0, 0.0, 0.0]), dtype=np.float64)

    @property
    def y_axis(self) -> np.ndarray:
        return np.asarray(self.coord.get("yAxis", [0.0, 1.0, 0.0]), dtype=np.float64)

    @property
    def z_axis(self) -> np.ndarray:
        return np.asarray(self.coord.get("zAxis", [0.0, 0.0, 1.0]), dtype=np.float64)


def points_for_mask(ctx: SolverContext, mask: np.ndarray) -> np.ndarray:
    if ctx.points.ndim != 3 or ctx.points.shape[-1] < 3 or mask.size == 0:
        return np.empty((0, 3), dtype=np.float32)
    selected = ctx.points[..., :3][mask.astype(bool) & ctx.validity.astype(bool)]
    return finite_points(selected)


def clean_object_points(points: np.ndarray, category: str) -> np.ndarray:
    cleaned = finite_points(points)
    cleaned = mad_filter(cleaned, threshold=4.2 if category in {"street_light", "tree"} else 4.8)
    cleaned = open3d_largest_cluster(cleaned, category)
    return cleaned


def project_to_ground_uv(ctx: SolverContext, points: np.ndarray) -> np.ndarray:
    if len(points) == 0:
        return np.empty((0, 2), dtype=np.float64)
    projected = project_points_to_plane(points.astype(np.float64), ctx.plane)
    relative = projected - ctx.origin[None, :]
    return np.column_stack([relative @ ctx.x_axis, relative @ ctx.z_axis])


def uv_to_world(ctx: SolverContext, uv: np.ndarray | list[float]) -> np.ndarray:
    values = np.asarray(uv, dtype=np.float64)
    return ctx.origin + values[0] * ctx.x_axis + values[1] * ctx.z_axis


def robust_height(ctx: SolverContext, points: np.ndarray) -> float:
    if len(points) == 0:
        return 0.0
    distances = signed_distance_to_plane(points.astype(np.float64), ctx.plane)
    distances = distances[np.isfinite(distances)]
    if len(distances) == 0:
        return 0.0
    p02 = float(np.percentile(distances, 2))
    p95 = float(np.percentile(distances, 95))
    abs95 = float(np.percentile(np.abs(distances), 95))
    return max(0.0, p95 - p02, abs95)


def min_area_rect(uv: np.ndarray) -> dict[str, Any]:
    if len(uv) == 0:
        return {"center": [0.0, 0.0], "width": 0.0, "length": 0.0, "direction": [1.0, 0.0], "method": "empty"}
    try:
        import cv2
    except Exception:
        result = oriented_bbox_2d(uv)
        result["method"] = "pca_percentile_fallback"
        return result
    if len(uv) < 3:
        result = oriented_bbox_2d(uv)
        result["method"] = "pca_percentile_fallback"
        return result
    pts = uv.astype("float32")
    rect = cv2.minAreaRect(pts)
    box = cv2.boxPoints(rect).astype(np.float64)
    edges = [(box[(i + 1) % 4] - box[i]) for i in range(4)]
    lengths = np.asarray([np.linalg.norm(edge) for edge in edges], dtype=np.float64)
    if float(lengths.max()) <= 1e-9:
        result = oriented_bbox_2d(uv)
        result["method"] = "pca_percentile_fallback"
        return result
    long_index = int(np.argmax(lengths))
    direction = edges[long_index] / max(lengths[long_index], 1e-9)
    center = np.asarray(rect[0], dtype=np.float64)
    long_len = float(lengths[long_index])
    short_len = float(lengths[(long_index + 1) % 4])
    return {
        "center": [float(center[0]), float(center[1])],
        "width": max(0.0, min(short_len, long_len)),
        "length": max(0.0, max(short_len, long_len)),
        "direction": [float(direction[0]), float(direction[1])],
        "corners": [[float(v) for v in point.tolist()] for point in box],
        "method": "opencv_min_area_rect",
    }


def yaw_from_rect(rect: dict[str, Any]) -> float:
    return yaw_from_direction(rect.get("direction", [1.0, 0.0]))


def confidence_from_points(raw_count: int, kept_count: int, mask_pixels: int, detection_score: float) -> float:
    if mask_pixels <= 0 or raw_count <= 0 or kept_count <= 0:
        return 0.0
    density = min(1.0, kept_count / max(1, mask_pixels))
    retention = min(1.0, kept_count / max(1, raw_count))
    return float(max(0.05, min(0.95, 0.25 * detection_score + 0.45 * retention + 0.30 * density)))


def object_payload(
    detection: Any,
    category: str,
    anchor_type: str,
    position: np.ndarray,
    dimensions: dict[str, float | str],
    yaw: float,
    confidence: float,
    diagnostics: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": detection.id,
        "category": category,
        "anchor": {"type": anchor_type, "position": [float(v) for v in position.tolist()]},
        "dimensions": dimensions,
        "rotation": {"yaw": float(yaw), "unit": "degree"},
        "source": {"bbox": list(detection.bbox), "maskPath": detection.mask_path},
        "confidence": {
            "category": float(detection.score),
            "detection": float(detection.score),
            "mask": 0.8 if int(diagnostics.get("maskPixelCount", 0)) > 0 else 0.0,
            "position": float(confidence),
            "dimensions": float(confidence),
            "rotation": float(diagnostics.get("rotationConfidence", confidence)),
        },
        "geometryDiagnostics": diagnostics,
    }
    if extra:
        payload.update(extra)
    payload["needsReview"] = is_suspicious_dimensions(dimensions) or confidence < 0.20
    return payload


def is_suspicious_dimensions(dimensions: dict[str, float | str]) -> bool:
    values = [float(dimensions.get(key, 0.0) or 0.0) for key in ["width", "height", "length"]]
    if min(values) < 0.0:
        return True
    if max(values) <= 0.0:
        return True
    return max(values) > 300.0


def finite_points(points: np.ndarray) -> np.ndarray:
    if len(points) == 0:
        return points.reshape(0, 3)
    return points[np.isfinite(points).all(axis=1)]


def mad_filter(points: np.ndarray, threshold: float = 4.5) -> np.ndarray:
    if len(points) < 16:
        return points
    median = np.median(points, axis=0)
    mad = np.median(np.abs(points - median), axis=0)
    mad = np.maximum(mad, 1e-6)
    keep = (np.abs(points - median) / mad < threshold).all(axis=1)
    filtered = points[keep]
    return filtered if len(filtered) >= 8 else points


def open3d_largest_cluster(points: np.ndarray, category: str) -> np.ndarray:
    try:
        import open3d as o3d
    except Exception:
        return points
    if len(points) < 24:
        return points
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points.astype(np.float64))
    try:
        cloud, _ = cloud.remove_statistical_outlier(nb_neighbors=18, std_ratio=2.5)
        arr = np.asarray(cloud.points)
        if len(arr) < 16:
            return points
        span = np.linalg.norm(np.nanmax(arr, axis=0) - np.nanmin(arr, axis=0))
        base = 0.06 if category in {"street_light", "tree"} else 0.045
        eps = max(span * base, 1e-4)
        min_points = 5 if category in {"street_light", "tree"} else 10
        labels = np.asarray(cloud.cluster_dbscan(eps=eps, min_points=min_points, print_progress=False))
    except Exception:
        return points
    valid = labels >= 0
    if not valid.any():
        return arr
    label_values, counts = np.unique(labels[valid], return_counts=True)
    best = label_values[int(np.argmax(counts))]
    clustered = arr[labels == best]
    return clustered if len(clustered) >= 8 else arr