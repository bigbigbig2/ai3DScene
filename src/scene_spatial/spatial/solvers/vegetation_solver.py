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
from scene_spatial.spatial.solvers.region_geometry import convex_hull_uv, polygons_from_mask


def solve_region(detection: Any, mask: np.ndarray, ctx: SolverContext) -> dict[str, Any]:
    raw = points_for_mask(ctx, mask)
    uv = project_to_ground_uv(ctx, raw)
    rect = min_area_rect(uv)
    polygons = polygons_from_mask(mask, ctx, max_polygons=24, simplify_ratio=0.012)
    if not polygons:
        polygons = _fallback_polygons(uv, ctx)
    confidence = confidence_from_points(len(raw), len(raw), int(mask.sum()), float(detection.score)) if len(raw) else 0.0
    if len(uv):
        center = uv_to_world(ctx, rect["center"])
        width = float(rect["width"])
        length = float(rect["length"])
    else:
        center = ctx.origin.copy()
        width = length = 0.0
    diagnostics = {
        "solverMethod": _solver_method(detection.category),
        "rawPointCount": int(len(raw)),
        "pointCount": int(len(raw)),
        "maskPixelCount": int(mask.sum()),
        "polygonCount": int(len(polygons)),
        "polygonVertexCount": int(sum(len(poly.get("pointsUV", [])) for poly in polygons)),
        "rectMethod": rect.get("method"),
        "rotationConfidence": 0.0,
    }
    extra = {
        "regionGeometry": {
            "polygons": polygons,
            "method": _region_method(detection.category),
            "semantics": _region_semantics(detection.category),
        }
    }
    height = 0.04 if detection.category == "ground" else 0.12
    return object_payload(
        detection,
        detection.category,
        "region_center",
        center,
        {"width": width, "height": height, "length": length, "unit": "relative"},
        0.0,
        confidence,
        diagnostics,
        extra=extra,
    )


def _fallback_polygons(uv: np.ndarray, ctx: SolverContext) -> list[dict[str, Any]]:
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


def _solver_method(category: str) -> str:
    if category == "vegetation_region":
        return "vegetation_region_contour_multipolygon_ground_projection"
    return "region_contour_multipolygon_ground_projection"


def _region_method(category: str) -> str:
    if category == "vegetation_region":
        return "opencv_contours_shapely_multipolygon_low_vegetation_only"
    return "opencv_contours_shapely_multipolygon"


def _region_semantics(category: str) -> dict[str, Any]:
    if category != "vegetation_region":
        return {}
    return {
        "intendedFor": ["grass_area", "low_vegetation", "green_belt_ground_cover"],
        "excludes": ["individual_tree", "tree_crown", "tree_trunk"],
        "treeHandling": "tree is solved only as an instance category and is subtracted from region masks when available",
    }
