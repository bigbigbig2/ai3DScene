from __future__ import annotations

from typing import Any

import numpy as np

from scene_spatial.spatial.solvers.base import (
    SolverContext,
    clean_object_points,
    confidence_from_points,
    min_area_rect,
    object_payload,
    points_for_mask,
    project_to_ground_uv,
    robust_height,
    uv_to_world,
    yaw_from_rect,
)


def solve_building(detection: Any, mask: np.ndarray, ctx: SolverContext) -> dict[str, Any]:
    raw = points_for_mask(ctx, mask)
    points = clean_object_points(raw, "building")
    mask_pixels = int(mask.sum())
    if len(points) == 0:
        diagnostics = {
            "solverMethod": "building_open3d_opencv_empty",
            "rawPointCount": int(len(raw)),
            "pointCount": 0,
            "maskPixelCount": mask_pixels,
            "rotationConfidence": 0.0,
        }
        return object_payload(
            detection,
            "building",
            "bottom_center",
            ctx.origin.copy(),
            {"width": 0.0, "height": 0.0, "length": 0.0, "unit": "relative"},
            0.0,
            0.0,
            diagnostics,
        )

    uv = project_to_ground_uv(ctx, points)
    rect = min_area_rect(uv)
    center = uv_to_world(ctx, rect["center"])
    height = robust_height(ctx, points)
    width = float(rect["width"])
    length = float(rect["length"])
    yaw = yaw_from_rect(rect)
    confidence = confidence_from_points(len(raw), len(points), mask_pixels, float(detection.score))
    footprint_area = max(width * length, 0.0)
    diagnostics = {
        "solverMethod": "building_open3d_clean_ground_projection_opencv_min_area_rect",
        "rawPointCount": int(len(raw)),
        "pointCount": int(len(points)),
        "maskPixelCount": mask_pixels,
        "rectMethod": rect.get("method"),
        "footprintArea": float(footprint_area),
        "rotationConfidence": confidence * (0.9 if rect.get("method") == "opencv_min_area_rect" else 0.65),
        "orientationEvidence": {
            "pointCloudFootprintYaw": float(yaw),
            "deepLsdEnabled": False,
            "deepLsdRole": "optional yaw validator; not loaded in core pipeline",
        },
    }
    extra = {
        "footprint": {
            "type": "oriented_rectangle",
            "cornersUV": rect.get("corners", []),
            "unit": "ground_relative",
        }
    }
    return object_payload(
        detection,
        "building",
        "bottom_center",
        center,
        {"width": width, "height": height, "length": length, "unit": "relative"},
        yaw,
        confidence,
        diagnostics,
        extra=extra,
    )