from __future__ import annotations

from typing import Any

import numpy as np

from scene_spatial.spatial.grouping.along_path_solver import nearest_neighbor_edges
from scene_spatial.spatial.grouping.grid_solver import detect_grid
from scene_spatial.spatial.grouping.row_solver import fit_rows_ransac

REGION_CATEGORIES = {"ground", "road", "vegetation_region"}


def solve_groups(objects: list[dict[str, Any]], coord: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    by_category: dict[str, list[dict[str, Any]]] = {}
    for obj in objects:
        if not _is_group_candidate(obj):
            continue
        by_category.setdefault(str(obj.get("category", "unknown")), []).append(obj)

    groups: list[dict[str, Any]] = []
    for category, items in by_category.items():
        min_size = 4 if category in {"street_light", "tree"} else 3
        if len(items) < min_size:
            continue
        points = np.asarray([_center_2d(item, coord) for item in items], dtype=np.float64)
        labels, method = _cluster_labels(points, min_cluster_size=min_size)
        if not any(label >= 0 for label in labels) and len(items) >= min_size:
            labels = np.zeros(len(items), dtype=np.int64)
            method = f"{method}_single_cluster_fallback"
        for label in sorted({int(v) for v in labels if int(v) >= 0}):
            indices = [index for index, value in enumerate(labels) if int(value) == label]
            if len(indices) < min_size:
                continue
            cluster_items = [items[index] for index in indices]
            cluster_points = points[indices]
            axis_a, axis_b = _principal_axes(cluster_points)
            rows = fit_rows_ransac(cluster_items, cluster_points, min_row_size=3)
            grid = detect_grid(cluster_items, cluster_points, axis_a, axis_b)
            edges = nearest_neighbor_edges(cluster_items, cluster_points, multiplier=2.2 if category in {"street_light", "tree"} else 1.8)
            hull = _hull(cluster_points)
            pattern = _pattern_type(category, rows, grid, len(cluster_items))
            groups.append(
                {
                    "id": f"{category}_group_{len(groups) + 1:03d}",
                    "category": category,
                    "objectIds": [str(item.get("id")) for item in cluster_items],
                    "patternType": pattern,
                    "clusterMethod": method,
                    "axisA": [float(axis_a[0]), float(axis_a[1])],
                    "axisB": [float(axis_b[0]), float(axis_b[1])],
                    "rows": rows,
                    "grid": grid,
                    "edges": edges,
                    "hull": hull,
                    "noiseObjectIds": [str(items[index].get("id")) for index, value in enumerate(labels) if int(value) == -1],
                    "confidence": _group_confidence(len(cluster_items), rows, grid, method),
                }
            )
    return groups


def _is_group_candidate(obj: dict[str, Any]) -> bool:
    if obj.get("category") in REGION_CATEGORIES:
        return False
    quality = obj.get("geometryQuality", {}) if isinstance(obj.get("geometryQuality"), dict) else {}
    if quality and not quality.get("groupEligible", False):
        return False
    if obj.get("needsReview"):
        return False
    confidence = obj.get("confidence", {}) if isinstance(obj.get("confidence"), dict) else {}
    return float(confidence.get("position", 0.0) or 0.0) >= 0.18


def _center_2d(obj: dict[str, Any], coord: dict[str, Any] | None) -> list[float]:
    position = np.asarray(obj.get("anchor", {}).get("position", [0.0, 0.0, 0.0]), dtype=np.float64)
    if coord:
        origin = np.asarray(coord.get("origin", [0.0, 0.0, 0.0]), dtype=np.float64)
        x_axis = np.asarray(coord.get("xAxis", [1.0, 0.0, 0.0]), dtype=np.float64)
        z_axis = np.asarray(coord.get("zAxis", [0.0, 0.0, 1.0]), dtype=np.float64)
        rel = position - origin
        return [float(rel @ x_axis), float(rel @ z_axis)]
    return [float(position[0]), float(position[2])]


def _cluster_labels(points: np.ndarray, min_cluster_size: int) -> tuple[np.ndarray, str]:
    try:
        import hdbscan
    except Exception:
        return _adaptive_dbscan_labels(points, min_cluster_size), "adaptive_dbscan_fallback"
    try:
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=max(1, min_cluster_size // 2))
        labels = clusterer.fit_predict(points)
        return labels.astype(np.int64), "hdbscan"
    except Exception:
        return _adaptive_dbscan_labels(points, min_cluster_size), "adaptive_dbscan_fallback"


def _adaptive_dbscan_labels(points: np.ndarray, min_cluster_size: int) -> np.ndarray:
    labels = np.full(len(points), -1, dtype=np.int64)
    if len(points) < min_cluster_size:
        return labels
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=-1)
    nonzero = distances[distances > 1e-6]
    if len(nonzero) == 0:
        labels[:] = 0
        return labels
    nearest = np.min(np.where(distances > 1e-6, distances, np.inf), axis=1)
    nearest = nearest[np.isfinite(nearest)]
    eps = float(np.median(nearest) * 2.6) if len(nearest) else float(np.percentile(nonzero, 20))
    eps = max(eps, float(np.percentile(nonzero, 10)))
    visited: set[int] = set()
    cluster_id = 0
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
                n = int(neighbor)
                if n not in visited:
                    visited.add(n)
                    queue.append(n)
        if len(cluster) >= min_cluster_size:
            for index in cluster:
                labels[index] = cluster_id
            cluster_id += 1
    return labels


def _principal_axes(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(points) < 2:
        return np.array([1.0, 0.0], dtype=np.float64), np.array([0.0, 1.0], dtype=np.float64)
    centered = points - points.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    axis_a = vh[0] / max(np.linalg.norm(vh[0]), 1e-9)
    axis_b = np.array([-axis_a[1], axis_a[0]], dtype=np.float64)
    return axis_a, axis_b


def _hull(points: np.ndarray) -> list[list[float]]:
    if len(points) < 3:
        return [[float(v) for v in point.tolist()] for point in points]
    try:
        from shapely.geometry import MultiPoint
    except Exception:
        min_xy = np.min(points, axis=0)
        max_xy = np.max(points, axis=0)
        corners = [min_xy, [max_xy[0], min_xy[1]], max_xy, [min_xy[0], max_xy[1]]]
        return [[float(v) for v in np.asarray(point).tolist()] for point in corners]
    hull = MultiPoint(points).convex_hull
    if hull.geom_type != "Polygon":
        return [[float(v) for v in point.tolist()] for point in points]
    return [[float(v) for v in point] for point in hull.exterior.coords[:-1]]


def _pattern_type(category: str, rows: list[dict[str, Any]], grid: dict[str, Any] | None, count: int) -> str:
    if grid is not None:
        return "grid"
    if category in {"street_light", "tree"}:
        return "along_path" if count >= 4 else "cluster"
    if rows:
        return "row"
    return "cluster"


def _group_confidence(count: int, rows: list[dict[str, Any]], grid: dict[str, Any] | None, method: str) -> float:
    score = 0.35 + min(0.30, count * 0.04)
    if method == "hdbscan":
        score += 0.12
    if rows:
        score += 0.08
    if grid is not None:
        score += 0.12
    return float(min(0.92, score))