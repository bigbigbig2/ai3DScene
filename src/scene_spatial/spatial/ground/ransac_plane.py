from __future__ import annotations

from typing import Any

import numpy as np

from scene_spatial.spatial.ground.local_ground import fit_radial_local_planes, residual_stats
from scene_spatial.spatial.solver_utils import (
    fallback_plane,
    fit_plane_ransac,
    plane_basis,
    project_points_to_plane,
    valid_points,
)


def solve_ground_plane(
    points: np.ndarray,
    validity: np.ndarray,
    candidate_points: np.ndarray,
    normals: np.ndarray | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    raw_candidate_count = int(len(candidate_points))
    cleaned = clean_ground_points(candidate_points)
    fallback_used = False
    if len(cleaned) < 32:
        cleaned = clean_ground_points(valid_points(points, validity))
        fallback_used = True
    plane = fit_plane_ransac(cleaned) if len(cleaned) >= 3 else fallback_plane()
    residuals = residual_stats(cleaned, plane.get("plane", [0.0, 1.0, 0.0, 0.0]))
    plane_payload = {
        "schemaVersion": "1.0",
        **plane,
        "candidatePointCount": raw_candidate_count,
        "cleanedCandidatePointCount": int(len(cleaned)),
        "fallbackToFullValidPointCloud": fallback_used,
        "residuals": residuals,
        "localPlanes": fit_local_planes(cleaned, plane.get("plane", [0.0, 1.0, 0.0, 0.0])),
    }
    coord = build_coordinate_system(cleaned, plane_payload)
    diagnostics = {
        "rawCandidatePointCount": raw_candidate_count,
        "cleanedCandidatePointCount": int(len(cleaned)),
        "fallbackToFullValidPointCloud": fallback_used,
        "normalArrayUsed": normals is not None,
        "residuals": residuals,
    }
    return plane_payload, coord, diagnostics


def clean_ground_points(points: np.ndarray) -> np.ndarray:
    finite = _finite(points)
    if len(finite) < 16:
        return finite
    filtered = _mad_filter(finite, threshold=4.0)
    clustered = _open3d_largest_cluster(filtered)
    return clustered if len(clustered) >= 16 else filtered


def build_coordinate_system(points: np.ndarray, ground: dict[str, Any]) -> dict[str, Any]:
    plane = ground.get("plane", [0.0, 1.0, 0.0, 0.0])
    normal = np.asarray(ground.get("normal", plane[:3]), dtype=np.float64)
    x_axis, y_axis, z_axis = plane_basis(normal)
    origin = np.zeros(3, dtype=np.float64)
    if len(points) > 0:
        projected = project_points_to_plane(points.astype(np.float64), plane)
        origin = np.median(projected, axis=0)
    return {
        "schemaVersion": "1.0",
        "origin": [float(v) for v in origin.tolist()],
        "xAxis": [float(v) for v in x_axis.tolist()],
        "yAxis": [float(v) for v in y_axis.tolist()],
        "zAxis": [float(v) for v in z_axis.tolist()],
        "unit": "relative",
        "method": "plane_basis_from_constrained_ground_ransac",
    }


def fit_local_planes(points: np.ndarray, plane: list[float]) -> list[dict[str, Any]]:
    return fit_radial_local_planes(
        points,
        plane,
        lambda subset: fit_plane_ransac(subset, iterations=80),
    )


def _open3d_largest_cluster(points: np.ndarray) -> np.ndarray:
    try:
        import open3d as o3d
    except Exception:
        return points
    if len(points) < 32:
        return points
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points.astype(np.float64))
    try:
        cloud, _ = cloud.remove_statistical_outlier(nb_neighbors=24, std_ratio=2.2)
        arr = np.asarray(cloud.points)
        if len(arr) < 32:
            return points
        span = np.linalg.norm(np.nanmax(arr, axis=0) - np.nanmin(arr, axis=0))
        eps = max(span * 0.035, 1e-4)
        labels = np.asarray(cloud.cluster_dbscan(eps=eps, min_points=12, print_progress=False))
    except Exception:
        return points
    valid = labels >= 0
    if not valid.any():
        return arr
    label_values, counts = np.unique(labels[valid], return_counts=True)
    best = label_values[int(np.argmax(counts))]
    clustered = arr[labels == best]
    return clustered if len(clustered) >= 16 else arr


def _finite(points: np.ndarray) -> np.ndarray:
    if len(points) == 0:
        return points.reshape(0, 3)
    return points[np.isfinite(points).all(axis=1)]


def _mad_filter(points: np.ndarray, threshold: float) -> np.ndarray:
    if len(points) < 16:
        return points
    median = np.median(points, axis=0)
    mad = np.median(np.abs(points - median), axis=0)
    mad = np.maximum(mad, 1e-6)
    keep = (np.abs(points - median) / mad < threshold).all(axis=1)
    filtered = points[keep]
    return filtered if len(filtered) >= 8 else points
