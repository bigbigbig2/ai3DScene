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
from scene_spatial.spatial.solvers.building_solver import solve_building
from scene_spatial.spatial.solvers.road_solver import solve_road
from scene_spatial.spatial.solvers.street_light_solver import solve_street_light
from scene_spatial.spatial.solvers.tree_solver import solve_tree
from scene_spatial.spatial.solvers.vegetation_solver import solve_region

REGION_CATEGORIES = {"ground", "vegetation_region"}


def solve_detection(detection: Any, mask: np.ndarray, ctx: SolverContext) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if detection.category == "building":
        return solve_building(detection, mask, ctx), None
    if detection.category == "tree":
        return solve_tree(detection, mask, ctx), None
    if detection.category == "street_light":
        return solve_street_light(detection, mask, ctx), None
    if detection.category == "road":
        road, road_object = solve_road(detection, mask, ctx)
        return road_object, road
    if detection.category in REGION_CATEGORIES or detection.object_mode == "region":
        return solve_region(detection, mask, ctx), None
    return solve_generic_object(detection, mask, ctx), None


def solve_generic_object(detection: Any, mask: np.ndarray, ctx: SolverContext) -> dict[str, Any]:
    raw = points_for_mask(ctx, mask)
    points = clean_object_points(raw, detection.category)
    uv = project_to_ground_uv(ctx, points)
    rect = min_area_rect(uv)
    if len(uv):
        center = uv_to_world(ctx, rect["center"])
        height = robust_height(ctx, points)
        width = float(rect["width"])
        length = float(rect["length"])
        yaw = yaw_from_rect(rect)
    else:
        center = ctx.origin.copy()
        width = height = length = yaw = 0.0
    confidence = confidence_from_points(len(raw), len(points), int(mask.sum()), float(detection.score))
    diagnostics = {
        "solverMethod": "generic_open3d_clean_ground_projection_min_area_rect",
        "rawPointCount": int(len(raw)),
        "pointCount": int(len(points)),
        "maskPixelCount": int(mask.sum()),
        "rectMethod": rect.get("method"),
        "rotationConfidence": confidence * 0.5,
    }
    return object_payload(
        detection,
        detection.category,
        "bottom_center",
        center,
        {"width": width, "height": height, "length": length, "unit": "relative"},
        yaw,
        confidence,
        diagnostics,
    )