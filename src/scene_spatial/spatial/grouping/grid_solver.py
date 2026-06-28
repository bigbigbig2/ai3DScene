from __future__ import annotations

from typing import Any

import numpy as np


def detect_grid(items: list[dict[str, Any]], points: np.ndarray, axis_a: np.ndarray, axis_b: np.ndarray) -> dict[str, Any] | None:
    if len(points) < 6:
        return None
    proj_a = points @ axis_a
    proj_b = points @ axis_b
    rows = _cluster_1d(proj_b)
    cols = _cluster_1d(proj_a)
    if len(rows) < 2 or len(cols) < 2:
        return None
    assignments = []
    for index, item in enumerate(items):
        row_id = _nearest_cluster(proj_b[index], rows)
        col_id = _nearest_cluster(proj_a[index], cols)
        assignments.append({"objectId": str(item.get("id")), "rowId": int(row_id), "columnId": int(col_id)})
    row_spacing = _median_spacing([cluster["center"] for cluster in rows])
    col_spacing = _median_spacing([cluster["center"] for cluster in cols])
    row_cv = _spacing_cv([cluster["center"] for cluster in rows])
    col_cv = _spacing_cv([cluster["center"] for cluster in cols])
    if row_cv > 0.75 or col_cv > 0.75:
        return None
    return {
        "type": "grid",
        "rowCount": len(rows),
        "columnCount": len(cols),
        "rowSpacing": row_spacing,
        "columnSpacing": col_spacing,
        "rowSpacingCv": row_cv,
        "columnSpacingCv": col_cv,
        "assignments": assignments,
    }


def _cluster_1d(values: np.ndarray) -> list[dict[str, Any]]:
    if len(values) == 0:
        return []
    order = np.argsort(values)
    sorted_values = values[order]
    diffs = np.diff(sorted_values)
    positive = diffs[diffs > 1e-6]
    if len(positive) == 0:
        return [{"center": float(np.median(values)), "indices": [int(i) for i in order.tolist()]}]
    threshold = float(np.median(positive) * 1.7)
    clusters: list[list[int]] = [[int(order[0])]]
    for local_index, diff in enumerate(diffs, start=1):
        if diff > threshold:
            clusters.append([])
        clusters[-1].append(int(order[local_index]))
    return [{"center": float(np.median(values[cluster])), "indices": cluster} for cluster in clusters if cluster]


def _nearest_cluster(value: float, clusters: list[dict[str, Any]]) -> int:
    centers = np.asarray([cluster["center"] for cluster in clusters], dtype=np.float64)
    return int(np.argmin(np.abs(centers - value))) + 1


def _median_spacing(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    diffs = np.diff(np.sort(np.asarray(values, dtype=np.float64)))
    diffs = diffs[diffs > 1e-6]
    return float(np.median(diffs)) if len(diffs) else 0.0


def _spacing_cv(values: list[float]) -> float:
    if len(values) < 3:
        return 0.0
    diffs = np.diff(np.sort(np.asarray(values, dtype=np.float64)))
    diffs = diffs[diffs > 1e-6]
    if len(diffs) < 2:
        return 0.0
    mean = float(np.mean(diffs))
    return float(np.std(diffs) / mean) if mean > 1e-9 else 0.0