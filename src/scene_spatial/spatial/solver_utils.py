from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Detection:
    id: str
    category: str
    object_mode: str
    bbox: tuple[int, int, int, int]
    score: float
    mask_path: str


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_array(path: Path) -> np.ndarray:
    try:
        return np.load(path)
    except Exception:
        return np.zeros((2, 2, 3), dtype=np.float32)


def load_validity(path: Path, shape: tuple[int, int]) -> np.ndarray:
    if not path.exists():
        return np.ones(shape, dtype=bool)
    try:
        validity = np.load(path)
    except Exception:
        return np.ones(shape, dtype=bool)
    if validity.ndim == 3:
        validity = validity[..., 0]
    return resize_bool(validity.astype(bool), shape)


def load_mask(path: Path, shape: tuple[int, int]) -> np.ndarray:
    if not path.exists():
        return np.zeros(shape, dtype=bool)
    with Image.open(path) as image:
        image = image.convert("L")
        if image.size != (shape[1], shape[0]):
            image = image.resize((shape[1], shape[0]), Image.Resampling.NEAREST)
        return clean_mask(np.asarray(image) > 127)



def clean_mask(mask: np.ndarray) -> np.ndarray:
    try:
        import cv2
    except ModuleNotFoundError:
        return mask.astype(bool)
    source = mask.astype("uint8") * 255
    kernel = np.ones((3, 3), np.uint8)
    opened = cv2.morphologyEx(source, cv2.MORPH_OPEN, kernel)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)
    return closed > 127


def fit_plane_open3d(points: np.ndarray, threshold: float | None) -> dict[str, Any] | None:
    try:
        import open3d as o3d
    except ModuleNotFoundError:
        return None
    if len(points) < 3:
        return None
    if threshold is None:
        span = np.linalg.norm(np.nanmax(points, axis=0) - np.nanmin(points, axis=0))
        threshold = max(span * 0.01, 1e-4)
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points.astype(np.float64))
    try:
        plane_model, inliers = cloud.segment_plane(
            distance_threshold=float(threshold),
            ransac_n=3,
            num_iterations=160,
        )
    except RuntimeError:
        return None
    if len(inliers) < 3:
        return None
    normal = orient_plane_normal(np.asarray(plane_model[:3], dtype=np.float64))
    d = float(plane_model[3])
    if float(np.dot(normal, np.asarray(plane_model[:3], dtype=np.float64))) < 0:
        d = -d
    inlier_ratio = float(len(inliers) / len(points))
    return {
        "plane": [float(normal[0]), float(normal[1]), float(normal[2]), d],
        "normal": [float(normal[0]), float(normal[1]), float(normal[2])],
        "inlierRatio": inlier_ratio,
        "pointCount": int(len(inliers)),
        "method": "open3d_segment_plane",
        "confidence": min(0.98, max(0.05, inlier_ratio)),
    }

def resize_bool(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if mask.shape[:2] == shape:
        return mask.astype(bool)
    image = Image.fromarray(mask.astype("uint8") * 255, mode="L")
    image = image.resize((shape[1], shape[0]), Image.Resampling.NEAREST)
    return np.asarray(image) > 127


def load_detections(task_dir: Path) -> list[Detection]:
    path = task_dir / "detection" / "detections.json"
    if not path.exists():
        return []
    payload = read_json(path)
    detections: list[Detection] = []
    for item in payload.get("detections", []):
        bbox = item.get("bbox", [0, 0, 0, 0])
        detections.append(
            Detection(
                id=str(item.get("id", f"det_{len(detections) + 1:03d}")),
                category=str(item.get("category", "unknown")),
                object_mode=str(item.get("objectMode", item.get("object_mode", "instance"))),
                bbox=(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
                score=float(item.get("score", 0.0)),
                mask_path=str(item.get("maskPath", "")),
            )
        )
    return detections


def resolve_task_path(task_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else task_dir / path


def valid_points(points: np.ndarray, validity: np.ndarray | None = None) -> np.ndarray:
    if points.ndim != 3 or points.shape[-1] < 3:
        return np.empty((0, 3), dtype=np.float32)
    mask = np.isfinite(points[..., :3]).all(axis=-1)
    if validity is not None:
        mask &= validity.astype(bool)
    return points[..., :3][mask]


def sample_points(points: np.ndarray, max_points: int = 50000) -> np.ndarray:
    if len(points) <= max_points:
        return points
    step = max(1, len(points) // max_points)
    return points[::step][:max_points]


def fit_plane_ransac(points: np.ndarray, iterations: int = 160, threshold: float | None = None) -> dict[str, Any]:
    points = sample_points(points.astype(np.float64), 50000)
    if len(points) < 3:
        return fallback_plane()

    open3d_result = fit_plane_open3d(points, threshold)
    if open3d_result is not None:
        return open3d_result

    if threshold is None:
        span = np.linalg.norm(np.nanmax(points, axis=0) - np.nanmin(points, axis=0))
        threshold = max(span * 0.01, 1e-4)

    rng = np.random.default_rng(42)
    best_inliers: np.ndarray | None = None
    best_normal: np.ndarray | None = None
    best_d = 0.0

    for _ in range(iterations):
        sample = points[rng.choice(len(points), size=3, replace=False)]
        normal = np.cross(sample[1] - sample[0], sample[2] - sample[0])
        norm = np.linalg.norm(normal)
        if norm < 1e-9:
            continue
        normal = normal / norm
        d = -float(np.dot(normal, sample[0]))
        distances = np.abs(points @ normal + d)
        inliers = distances < threshold
        if best_inliers is None or int(inliers.sum()) > int(best_inliers.sum()):
            best_inliers = inliers
            best_normal = normal
            best_d = d

    if best_inliers is None or best_normal is None or int(best_inliers.sum()) < 3:
        return fallback_plane()

    inlier_points = points[best_inliers]
    centroid = inlier_points.mean(axis=0)
    centered = inlier_points - centroid
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    normal = vh[-1]
    normal = orient_plane_normal(normal)
    d = -float(np.dot(normal, centroid))
    inlier_ratio = float(best_inliers.mean())
    return {
        "plane": [float(normal[0]), float(normal[1]), float(normal[2]), d],
        "normal": [float(normal[0]), float(normal[1]), float(normal[2])],
        "inlierRatio": inlier_ratio,
        "pointCount": int(len(inlier_points)),
        "method": "numpy_ransac_svd",
        "confidence": min(0.95, max(0.05, inlier_ratio)),
    }


def fallback_plane() -> dict[str, Any]:
    return {
        "plane": [0.0, 1.0, 0.0, 0.0],
        "normal": [0.0, 1.0, 0.0],
        "inlierRatio": 0.0,
        "pointCount": 0,
        "method": "fallback",
        "confidence": 0.0,
    }


def orient_plane_normal(normal: np.ndarray) -> np.ndarray:
    normal = normal.astype(np.float64)
    norm = np.linalg.norm(normal)
    if norm < 1e-9:
        return np.array([0.0, 1.0, 0.0], dtype=np.float64)
    normal = normal / norm
    axis = int(np.argmax(np.abs(normal)))
    if normal[axis] < 0:
        normal = -normal
    return normal


def plane_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y_axis = orient_plane_normal(normal)
    reference = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    if abs(float(np.dot(y_axis, reference))) > 0.95:
        reference = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    x_axis = np.cross(reference, y_axis)
    x_axis = x_axis / max(np.linalg.norm(x_axis), 1e-9)
    z_axis = np.cross(y_axis, x_axis)
    z_axis = z_axis / max(np.linalg.norm(z_axis), 1e-9)
    return x_axis, y_axis, z_axis


def project_points_to_plane(points: np.ndarray, plane: list[float]) -> np.ndarray:
    normal = np.asarray(plane[:3], dtype=np.float64)
    normal = normal / max(np.linalg.norm(normal), 1e-9)
    d = float(plane[3])
    distances = points @ normal + d
    return points - distances[:, None] * normal[None, :]


def signed_distance_to_plane(points: np.ndarray, plane: list[float]) -> np.ndarray:
    normal = np.asarray(plane[:3], dtype=np.float64)
    normal = normal / max(np.linalg.norm(normal), 1e-9)
    d = float(plane[3])
    return points @ normal + d


def pca_direction(points_2d: np.ndarray) -> np.ndarray:
    if len(points_2d) < 2:
        return np.array([1.0, 0.0], dtype=np.float64)
    centered = points_2d - points_2d.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    direction = vh[0]
    return direction / max(np.linalg.norm(direction), 1e-9)


def oriented_bbox_2d(points_2d: np.ndarray) -> dict[str, Any]:
    if len(points_2d) == 0:
        return {
            "center": [0.0, 0.0],
            "width": 0.0,
            "length": 0.0,
            "direction": [1.0, 0.0],
        }
    direction = pca_direction(points_2d)
    perpendicular = np.array([-direction[1], direction[0]], dtype=np.float64)
    u = points_2d @ direction
    v = points_2d @ perpendicular
    u_min, u_max = float(np.percentile(u, 2)), float(np.percentile(u, 98))
    v_min, v_max = float(np.percentile(v, 2)), float(np.percentile(v, 98))
    center = ((u_min + u_max) * 0.5) * direction + ((v_min + v_max) * 0.5) * perpendicular
    return {
        "center": [float(center[0]), float(center[1])],
        "width": max(0.0, v_max - v_min),
        "length": max(0.0, u_max - u_min),
        "direction": [float(direction[0]), float(direction[1])],
    }


def yaw_from_direction(direction_2d: list[float]) -> float:
    return math.degrees(math.atan2(float(direction_2d[0]), float(direction_2d[1])))


def mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def bbox_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0, ix1 - ix0 + 1) * max(0, iy1 - iy0 + 1)
    area_a = max(0, ax1 - ax0 + 1) * max(0, ay1 - ay0 + 1)
    area_b = max(0, bx1 - bx0 + 1) * max(0, by1 - by0 + 1)
    union = area_a + area_b - inter
    return float(inter / union) if union else 0.0

