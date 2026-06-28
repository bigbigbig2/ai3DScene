from __future__ import annotations

from typing import Any

import numpy as np


def fit_rows_ransac(items: list[dict[str, Any]], points: np.ndarray, min_row_size: int = 3) -> list[dict[str, Any]]:
    if len(points) < min_row_size:
        return []
    remaining = list(range(len(points)))
    rows: list[dict[str, Any]] = []
    threshold = _row_threshold(points)
    rng = np.random.default_rng(7)
    while len(remaining) >= min_row_size:
        subset = points[remaining]
        best: list[int] = []
        if len(subset) < 2:
            break
        for _ in range(80):
            a, b = rng.choice(len(subset), size=2, replace=False)
            p0 = subset[a]
            direction = subset[b] - p0
            norm = np.linalg.norm(direction)
            if norm < 1e-9:
                continue
            direction = direction / norm
            distances = np.abs(np.cross(direction, subset - p0))
            inliers = [remaining[i] for i, distance in enumerate(distances) if distance <= threshold]
            if len(inliers) > len(best):
                best = inliers
        if len(best) < min_row_size:
            break
        row_points = points[best]
        axis = _principal_axis(row_points)
        order = np.argsort(row_points @ axis)
        ordered_indices = [best[int(i)] for i in order]
        rows.append(
            {
                "id": f"row_{len(rows) + 1:02d}",
                "objectIds": [str(items[index].get("id")) for index in ordered_indices],
                "axis": [float(axis[0]), float(axis[1])],
                "pointCount": int(len(best)),
            }
        )
        remaining = [index for index in remaining if index not in set(best)]
    return rows


def _row_threshold(points: np.ndarray) -> float:
    if len(points) < 2:
        return 0.0
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=-1)
    nearest = np.min(np.where(distances > 1e-6, distances, np.inf), axis=1)
    nearest = nearest[np.isfinite(nearest)]
    if len(nearest) == 0:
        return 0.05
    return max(float(np.median(nearest) * 0.45), 0.03)


def _principal_axis(points: np.ndarray) -> np.ndarray:
    if len(points) < 2:
        return np.array([1.0, 0.0], dtype=np.float64)
    centered = points - points.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    axis = vh[0]
    return axis / max(np.linalg.norm(axis), 1e-9)