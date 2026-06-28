from __future__ import annotations

from typing import Any

import numpy as np


def nearest_neighbor_edges(items: list[dict[str, Any]], points: np.ndarray, multiplier: float = 1.8) -> list[list[str]]:
    if len(items) < 2:
        return []
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=-1)
    nonzero = distances[distances > 1e-6]
    if len(nonzero) == 0:
        return []
    nearest = np.min(np.where(distances > 1e-6, distances, np.inf), axis=1)
    nearest = nearest[np.isfinite(nearest)]
    threshold = float(np.median(nearest) * multiplier) if len(nearest) else float(np.median(nonzero) * multiplier)
    edges: set[tuple[str, str]] = set()
    for index, item in enumerate(items):
        row = distances[index].copy()
        row[index] = np.inf
        neighbor = int(np.argmin(row))
        if np.isfinite(row[neighbor]) and row[neighbor] <= threshold:
            a, b = sorted([str(item.get("id")), str(items[neighbor].get("id"))])
            edges.add((a, b))
    return [[a, b] for a, b in sorted(edges)]