from __future__ import annotations

from typing import Any

import numpy as np

from scene_spatial.spatial.solvers.base import (
    SolverContext,
    confidence_from_points,
    min_area_rect,
    object_payload,
    points_for_mask,
    project_to_ground_uv,
    uv_to_world,
)
from scene_spatial.spatial.solvers.region_geometry import (
    centerlines_from_mask,
    convex_hull_uv,
    polygon_area_estimate,
    polygons_from_mask,
)


def solve_road(detection: Any, mask: np.ndarray, ctx: SolverContext) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = points_for_mask(ctx, mask)
    uv = project_to_ground_uv(ctx, raw)
    polygons = polygons_from_mask(mask, ctx, max_polygons=16, simplify_ratio=0.008)
    if not polygons:
        polygons = _fallback_polygon_from_points(uv, ctx)
    centerlines = centerlines_from_mask(mask, ctx, max_lines=8, min_component_pixels=10)
    rect = min_area_rect(uv)
    estimated_width = _estimate_road_width(uv, centerlines, rect)
    confidence = confidence_from_points(len(raw), len(raw), int(mask.sum()), float(detection.score)) if len(raw) else 0.0
    road = {
        "id": detection.id,
        "category": "road",
        "polygons": polygons,
        "centerlines": centerlines,
        "junctions": [],
        "estimatedWidth": float(estimated_width),
        "confidence": float(confidence),
        "solverMethod": "opencv_contour_shapely_polygon_skimage_skeleton_graph",
    }
    if len(uv):
        center = uv_to_world(ctx, rect["center"])
        width = float(rect["width"])
        length = float(rect["length"])
    else:
        center = ctx.origin.copy()
        width = length = 0.0
    diagnostics = {
        "solverMethod": "road_region_contour_skeleton_graph_ground_projection",
        "rawPointCount": int(len(raw)),
        "pointCount": int(len(raw)),
        "maskPixelCount": int(mask.sum()),
        "polygonCount": len(polygons),
        "centerlineCount": len(centerlines),
        "rectMethod": rect.get("method"),
        "rotationConfidence": 0.0,
    }
    obj = object_payload(
        detection,
        "road",
        "region_center",
        center,
        {"width": width, "height": 0.03, "length": length, "unit": "relative"},
        0.0,
        confidence,
        diagnostics,
        extra={"regionGeometry": road},
    )
    return road, obj


def _estimate_road_width(uv: np.ndarray, centerlines: list[dict[str, Any]], rect: dict[str, Any]) -> float:
    if len(uv) == 0:
        return 0.0
    if centerlines:
        line_uv = np.asarray(centerlines[0].get("pointsUV", []), dtype=np.float64)
        if len(line_uv) >= 2:
            length = float(np.sum(np.linalg.norm(np.diff(line_uv, axis=0), axis=1)))
            if length > 1e-6:
                area = polygon_area_estimate(uv)
                if area > 0:
                    return float(area / length)
    return float(rect.get("width", 0.0) or 0.0)


def _fallback_polygon_from_points(uv: np.ndarray, ctx: SolverContext) -> list[dict[str, Any]]:
    hull = convex_hull_uv(uv)
    if len(hull) < 3:
        return []
    return [
        {
            "points": [[float(v) for v in uv_to_world(ctx, point).tolist()] for point in hull],
            "pointsUV": hull.tolist(),
            "unit": "relative",
        }
    ]
