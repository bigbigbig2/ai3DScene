from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

from scene_spatial.spatial.solvers.base import SolverContext, project_to_ground_uv, uv_to_world


def polygons_from_mask(
    mask: np.ndarray,
    ctx: SolverContext,
    *,
    max_polygons: int = 24,
    min_contour_points: int = 3,
    simplify_ratio: float = 0.01,
) -> list[dict[str, Any]]:
    polygons: list[dict[str, Any]] = []
    for contour in find_contours(mask)[:max_polygons]:
        if len(contour) < min_contour_points:
            continue
        uv = pixels_to_uv(_downsample(contour, 320), ctx)
        if len(uv) < 3:
            continue
        simplified = simplify_polygon(uv, simplify_ratio=simplify_ratio)
        if len(simplified) < 3:
            continue
        world = [[float(v) for v in uv_to_world(ctx, point).tolist()] for point in simplified]
        polygons.append({"points": world, "pointsUV": simplified.tolist(), "unit": "relative"})
    return polygons


def centerlines_from_mask(
    mask: np.ndarray,
    ctx: SolverContext,
    *,
    max_lines: int = 8,
    min_component_pixels: int = 8,
    max_points_per_line: int = 160,
) -> list[dict[str, Any]]:
    skeleton = skeletonize_mask(mask)
    if skeleton is None or int(skeleton.sum()) < 2:
        return []
    lines: list[dict[str, Any]] = []
    for component in skeleton_components(skeleton, min_component_pixels=min_component_pixels)[:max_lines]:
        ordered_xy = order_skeleton_component(component)
        if len(ordered_xy) < 2:
            continue
        ordered_xy = _downsample(ordered_xy, max_points_per_line)
        uv = pixels_to_uv(ordered_xy, ctx)
        if len(uv) < 2:
            continue
        world = [[float(v) for v in uv_to_world(ctx, point).tolist()] for point in uv]
        lines.append(
            {
                "points": world,
                "pointsUV": uv.tolist(),
                "unit": "relative",
                "method": "skeletonize_connected_component_order",
            }
        )
    return lines


def pixels_to_uv(xy: np.ndarray, ctx: SolverContext) -> np.ndarray:
    if ctx.points.ndim != 3 or len(xy) == 0:
        return np.empty((0, 2), dtype=np.float64)
    height, width = ctx.points.shape[:2]
    x = np.rint(xy[:, 0]).astype(np.int64)
    y = np.rint(xy[:, 1]).astype(np.int64)
    keep = (x >= 0) & (x < width) & (y >= 0) & (y < height)
    x = x[keep]
    y = y[keep]
    if len(x) == 0:
        return np.empty((0, 2), dtype=np.float64)
    valid = ctx.validity[y, x].astype(bool) & np.isfinite(ctx.points[y, x, :3]).all(axis=1)
    if not valid.any():
        return np.empty((0, 2), dtype=np.float64)
    return project_to_ground_uv(ctx, ctx.points[y[valid], x[valid], :3])


def find_contours(mask: np.ndarray) -> list[np.ndarray]:
    source = mask.astype("uint8") * 255
    try:
        import cv2

        contours, _ = cv2.findContours(source, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        return [contour.reshape(-1, 2).astype(np.float64) for contour in contours]
    except Exception:
        try:
            from skimage import measure
        except Exception:
            return []
        contours = measure.find_contours(mask.astype(float), 0.5)
        contours = sorted(contours, key=len, reverse=True)
        return [np.column_stack([contour[:, 1], contour[:, 0]]).astype(np.float64) for contour in contours]


def simplify_polygon(uv: np.ndarray, *, simplify_ratio: float = 0.01) -> np.ndarray:
    if len(uv) < 3:
        return uv
    try:
        from shapely.geometry import Polygon
    except Exception:
        return cv2_simplify(uv, simplify_ratio=simplify_ratio)
    polygon = Polygon(uv)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        return cv2_simplify(uv, simplify_ratio=simplify_ratio)
    if polygon.geom_type == "MultiPolygon":
        polygon = max(polygon.geoms, key=lambda geom: geom.area)
    tolerance = max(float(polygon.length) * simplify_ratio, 1e-6)
    simplified = polygon.simplify(tolerance, preserve_topology=True)
    if simplified.geom_type == "MultiPolygon":
        simplified = max(simplified.geoms, key=lambda geom: geom.area)
    if simplified.geom_type != "Polygon" or simplified.is_empty:
        return cv2_simplify(uv, simplify_ratio=simplify_ratio)
    coords = np.asarray(simplified.exterior.coords[:-1], dtype=np.float64)
    return coords if len(coords) >= 3 else cv2_simplify(uv, simplify_ratio=simplify_ratio)


def cv2_simplify(uv: np.ndarray, *, simplify_ratio: float = 0.01) -> np.ndarray:
    try:
        import cv2
    except Exception:
        return uv
    epsilon = max(float(np.linalg.norm(np.nanmax(uv, axis=0) - np.nanmin(uv, axis=0))) * simplify_ratio, 1e-6)
    approx = cv2.approxPolyDP(uv.astype("float32"), epsilon, True).reshape(-1, 2)
    return approx.astype(np.float64) if len(approx) >= 3 else uv


def skeletonize_mask(mask: np.ndarray) -> np.ndarray | None:
    try:
        from skimage.morphology import skeletonize
    except Exception:
        return None
    try:
        return skeletonize(mask.astype(bool))
    except Exception:
        return None


def skeleton_components(skeleton: np.ndarray, *, min_component_pixels: int) -> list[np.ndarray]:
    ys, xs = np.where(skeleton)
    if len(xs) == 0:
        return []
    points = {(int(x), int(y)) for x, y in zip(xs, ys, strict=False)}
    components: list[np.ndarray] = []
    while points:
        start = points.pop()
        queue = deque([start])
        component = [start]
        while queue:
            point = queue.popleft()
            for neighbor in _neighbors8(point):
                if neighbor in points:
                    points.remove(neighbor)
                    queue.append(neighbor)
                    component.append(neighbor)
        if len(component) >= min_component_pixels:
            components.append(np.asarray(component, dtype=np.float64))
    components.sort(key=len, reverse=True)
    return components


def order_skeleton_component(component_xy: np.ndarray) -> np.ndarray:
    if len(component_xy) < 3:
        return component_xy
    points = {(int(x), int(y)) for x, y in component_xy.tolist()}
    degrees = {point: sum(1 for neighbor in _neighbors8(point) if neighbor in points) for point in points}
    endpoints = [point for point, degree in degrees.items() if degree <= 1]
    start = endpoints[0] if endpoints else tuple(component_xy[np.argmin(component_xy[:, 0])].astype(int))
    ordered: list[tuple[int, int]] = []
    visited: set[tuple[int, int]] = set()
    current = start
    previous: tuple[int, int] | None = None
    while current not in visited:
        ordered.append(current)
        visited.add(current)
        candidates = [neighbor for neighbor in _neighbors8(current) if neighbor in points and neighbor not in visited]
        if previous is not None and len(candidates) > 1:
            direction = np.asarray(current, dtype=np.float64) - np.asarray(previous, dtype=np.float64)
            candidates.sort(key=lambda item: -float(np.dot(np.asarray(item, dtype=np.float64) - current, direction)))
        if not candidates:
            break
        previous, current = current, candidates[0]
    if len(ordered) < max(2, len(component_xy) // 3):
        return _order_points_pca(component_xy)
    return np.asarray(ordered, dtype=np.float64)


def convex_hull_uv(uv: np.ndarray) -> np.ndarray:
    if len(uv) < 3:
        return np.empty((0, 2), dtype=np.float64)
    try:
        from shapely.geometry import MultiPoint
    except Exception:
        return _order_points_pca(uv)
    hull = MultiPoint(uv).convex_hull
    if hull.geom_type != "Polygon":
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray(hull.exterior.coords[:-1], dtype=np.float64)


def polygon_area_estimate(uv: np.ndarray) -> float:
    hull = convex_hull_uv(uv)
    if len(hull) < 3:
        return 0.0
    x = hull[:, 0]
    y = hull[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) * 0.5)


def _neighbors8(point: tuple[int, int]) -> list[tuple[int, int]]:
    x, y = point
    return [
        (x - 1, y - 1),
        (x, y - 1),
        (x + 1, y - 1),
        (x - 1, y),
        (x + 1, y),
        (x - 1, y + 1),
        (x, y + 1),
        (x + 1, y + 1),
    ]


def _order_points_pca(points: np.ndarray) -> np.ndarray:
    centered = points - points.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    axis = vh[0]
    order = np.argsort(points @ axis)
    return points[order]


def _downsample(points: np.ndarray, max_points: int) -> np.ndarray:
    if len(points) <= max_points:
        return points
    step = max(1, len(points) // max_points)
    return points[::step][:max_points]
