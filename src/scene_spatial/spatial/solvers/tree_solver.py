from __future__ import annotations

from typing import Any

import numpy as np

from scene_spatial.spatial.solvers.base import (
    SolverContext,
    clean_object_points,
    confidence_from_points,
    object_payload,
    points_for_mask,
    project_to_ground_uv,
    robust_height,
    uv_to_world,
)


def solve_tree(detection: Any, mask: np.ndarray, ctx: SolverContext) -> dict[str, Any]:
    raw = points_for_mask(ctx, mask)
    points = clean_object_points(raw, "tree")
    mask_pixels = int(mask.sum())
    if len(points) == 0:
        diagnostics = {
            "solverMethod": "tree_vertical_instance_empty",
            "rawPointCount": int(len(raw)),
            "pointCount": 0,
            "maskPixelCount": mask_pixels,
            "rotationConfidence": 0.0,
        }
        return object_payload(
            detection,
            "tree",
            "ground_contact",
            ctx.origin.copy(),
            {"width": 0.0, "height": 0.0, "length": 0.0, "unit": "relative"},
            0.0,
            0.0,
            diagnostics,
        )

    uv = project_to_ground_uv(ctx, points)
    bottom_uv = _bottom_band_uv(mask, ctx)
    if len(bottom_uv):
        center_uv = np.median(bottom_uv, axis=0)
        anchor_method = "bottom_mask_ground_projection"
    elif len(uv):
        center_uv = np.median(uv, axis=0)
        anchor_method = "median_ground_projection_fallback"
    else:
        center_uv = np.zeros(2, dtype=np.float64)
        anchor_method = "empty_fallback"
    anchor = uv_to_world(ctx, center_uv)
    horizontal_radius = _robust_radius(uv, center_uv)
    crown_diameter = max(horizontal_radius * 2.0, 0.05)
    height = robust_height(ctx, points)
    confidence = confidence_from_points(len(raw), len(points), mask_pixels, float(detection.score))
    diagnostics = {
        "solverMethod": "tree_instance_ground_anchor_crown_prior",
        "rawPointCount": int(len(raw)),
        "pointCount": int(len(points)),
        "maskPixelCount": mask_pixels,
        "anchorMethod": anchor_method,
        "rotationConfidence": 0.0,
        "primitive": "trunk_cylinder_plus_crown_sphere",
        "vegetationPolicy": "tree is an instance category, not merged into vegetation_region",
    }
    extra = {
        "primitive": {
            "type": "tree",
            "trunkRadius": float(max(crown_diameter * 0.08, 0.015)),
            "crownRadius": float(crown_diameter * 0.5),
            "up": [float(v) for v in ctx.y_axis.tolist()],
        }
    }
    return object_payload(
        detection,
        "tree",
        "ground_contact",
        anchor,
        {"width": crown_diameter, "height": height, "length": crown_diameter, "unit": "relative"},
        0.0,
        confidence,
        diagnostics,
        extra=extra,
    )


def _robust_radius(uv: np.ndarray, center_uv: np.ndarray) -> float:
    if len(uv) == 0:
        return 0.0
    distance = np.linalg.norm(uv - center_uv[None, :], axis=1)
    distance = distance[np.isfinite(distance)]
    if len(distance) == 0:
        return 0.0
    return float(np.percentile(distance, 82))


def _bottom_band_uv(mask: np.ndarray, ctx: SolverContext) -> np.ndarray:
    if mask.size == 0 or ctx.points.ndim != 3:
        return np.empty((0, 2), dtype=np.float64)
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return np.empty((0, 2), dtype=np.float64)
    threshold = np.percentile(ys, 78)
    keep = ys >= threshold
    xs = xs[keep]
    ys = ys[keep]
    height, width = ctx.points.shape[:2]
    inside = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
    xs = xs[inside]
    ys = ys[inside]
    if len(xs) == 0:
        return np.empty((0, 2), dtype=np.float64)
    valid = ctx.validity[ys, xs].astype(bool) & np.isfinite(ctx.points[ys, xs, :3]).all(axis=1)
    if not valid.any():
        return np.empty((0, 2), dtype=np.float64)
    return project_to_ground_uv(ctx, ctx.points[ys[valid], xs[valid], :3])
