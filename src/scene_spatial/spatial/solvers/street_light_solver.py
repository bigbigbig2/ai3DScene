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


def solve_street_light(detection: Any, mask: np.ndarray, ctx: SolverContext) -> dict[str, Any]:
    raw = points_for_mask(ctx, mask)
    points = clean_object_points(raw, "street_light")
    mask_pixels = int(mask.sum())
    if len(points) == 0:
        diagnostics = {
            "solverMethod": "street_light_prior_empty",
            "rawPointCount": int(len(raw)),
            "pointCount": 0,
            "maskPixelCount": mask_pixels,
            "rotationConfidence": 0.0,
        }
        return object_payload(
            detection,
            "street_light",
            "ground_contact",
            ctx.origin.copy(),
            {"width": 0.0, "height": 0.0, "length": 0.0, "unit": "relative"},
            0.0,
            0.0,
            diagnostics,
        )

    uv = project_to_ground_uv(ctx, points)
    center_uv = _anchor_uv_from_mask_or_points(mask, uv, ctx)
    anchor = uv_to_world(ctx, center_uv)
    height = robust_height(ctx, points)
    horizontal = uv - center_uv[None, :]
    radius = float(np.percentile(np.linalg.norm(horizontal, axis=1), 75)) if len(horizontal) else 0.0
    diameter = max(radius * 2.0, 0.03)
    confidence = confidence_from_points(len(raw), len(points), mask_pixels, float(detection.score))
    diagnostics = {
        "solverMethod": "street_light_ground_anchor_up_prior",
        "rawPointCount": int(len(raw)),
        "pointCount": int(len(points)),
        "maskPixelCount": mask_pixels,
        "anchorMethod": "bottom_mask_ground_projection",
        "rotationConfidence": 0.15,
        "primitive": "cylinder_pole_plus_head_box",
    }
    extra = {
        "primitive": {
            "type": "pole_with_head",
            "up": [float(v) for v in ctx.y_axis.tolist()],
            "radius": float(diameter * 0.5),
        }
    }
    return object_payload(
        detection,
        "street_light",
        "ground_contact",
        anchor,
        {"width": diameter, "height": height, "length": diameter, "unit": "relative"},
        0.0,
        confidence,
        diagnostics,
        extra=extra,
    )


def _anchor_uv_from_mask_or_points(mask: np.ndarray, uv: np.ndarray, ctx: SolverContext) -> np.ndarray:
    if len(uv) == 0:
        return np.zeros(2, dtype=np.float64)
    bottom = _bottom_band_uv(mask, ctx)
    if len(bottom):
        return np.median(bottom, axis=0)
    return np.median(uv, axis=0)


def _bottom_band_uv(mask: np.ndarray, ctx: SolverContext) -> np.ndarray:
    if mask.size == 0 or ctx.points.ndim != 3:
        return np.empty((0, 2), dtype=np.float64)
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return np.empty((0, 2), dtype=np.float64)
    threshold = np.percentile(ys, 82)
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
