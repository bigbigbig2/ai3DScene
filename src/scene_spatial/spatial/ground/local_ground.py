from __future__ import annotations

from typing import Any, Callable

import numpy as np

from scene_spatial.spatial.solver_utils import signed_distance_to_plane

PlaneFitFn = Callable[[np.ndarray], dict[str, Any]]


def fit_radial_local_planes(
    points: np.ndarray,
    global_plane: list[float],
    fit_plane: PlaneFitFn,
    *,
    min_points: int = 32,
    band_count: int = 3,
) -> list[dict[str, Any]]:
    if len(points) < min_points * 3:
        return []
    center = np.median(points, axis=0)
    radius = np.linalg.norm(points - center[None, :], axis=1)
    quantiles = np.quantile(radius, np.linspace(0.0, 1.0, band_count + 1))
    planes: list[dict[str, Any]] = []
    for index in range(band_count):
        lower = quantiles[index]
        upper = quantiles[index + 1]
        upper_mask = radius <= upper if index == band_count - 1 else radius < upper
        subset = points[(radius >= lower) & upper_mask]
        if len(subset) < min_points:
            continue
        local = fit_plane(subset)
        residual = residual_stats(subset, local.get("plane", global_plane))
        planes.append(
            {
                "id": f"radial_band_{index + 1}",
                "pointCount": int(len(subset)),
                "plane": local.get("plane"),
                "normal": local.get("normal"),
                "inlierRatio": local.get("inlierRatio"),
                "residualMedian": residual.get("median"),
                "residualP95": residual.get("p95"),
            }
        )
    return planes


def residual_stats(points: np.ndarray, plane: list[float]) -> dict[str, float | int | None]:
    if len(points) == 0:
        return {"count": 0, "median": None, "mean": None, "p95": None}
    residual = np.abs(signed_distance_to_plane(points.astype(np.float64), plane))
    residual = residual[np.isfinite(residual)]
    if len(residual) == 0:
        return {"count": 0, "median": None, "mean": None, "p95": None}
    return {
        "count": int(len(residual)),
        "median": float(np.median(residual)),
        "mean": float(np.mean(residual)),
        "p95": float(np.percentile(residual, 95)),
    }
