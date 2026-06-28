from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from scene_spatial.spatial.solver_utils import load_detections, load_mask, resolve_task_path

GROUND_CATEGORIES = {"ground", "road", "vegetation_region"}
EXCLUSION_CATEGORIES = {"building", "rectangular_treatment_pool", "tree", "street_light", "water", "sky", "vehicle", "person"}


@dataclass(frozen=True)
class GroundCandidateResult:
    mask: np.ndarray
    semantic_mask: np.ndarray
    normal_mask: np.ndarray | None
    diagnostics: dict[str, Any]


def select_ground_candidates(
    task_dir: Path,
    shape: tuple[int, int],
    validity: np.ndarray,
    normals: np.ndarray | None = None,
) -> GroundCandidateResult:
    if shape == (0, 0):
        empty = np.zeros(shape, dtype=bool)
        return GroundCandidateResult(empty, empty, None, {"reason": "empty point map"})

    detections = load_detections(task_dir)
    semantic = np.zeros(shape, dtype=bool)
    exclusions = np.zeros(shape, dtype=bool)
    counts: dict[str, int] = {}
    for detection in detections:
        mask = load_mask(resolve_task_path(task_dir, detection.mask_path), shape)
        counts[detection.category] = counts.get(detection.category, 0) + int(mask.sum())
        if detection.category in GROUND_CATEGORIES:
            semantic |= mask
        if detection.category in EXCLUSION_CATEGORIES:
            exclusions |= mask

    fallback_used = False
    if not semantic.any():
        semantic = _lower_image_prior(shape)
        fallback_used = True

    candidate = semantic & ~exclusions & validity.astype(bool)
    if int(candidate.sum()) < 64:
        candidate = semantic & validity.astype(bool)

    normal_mask = None
    normal_filtered = False
    if normals is not None and normals.shape[:2] == shape and candidate.any():
        normal_mask = _normal_consistency_mask(normals, candidate)
        if normal_mask is not None and int((candidate & normal_mask).sum()) >= 32:
            candidate = candidate & normal_mask
            normal_filtered = True

    diagnostics = {
        "semanticPixelCount": int(semantic.sum()),
        "exclusionPixelCount": int(exclusions.sum()),
        "candidatePixelCount": int(candidate.sum()),
        "categoryPixelCounts": counts,
        "fallbackLowerImagePrior": fallback_used,
        "normalFilterApplied": normal_filtered,
        "normalCandidatePixelCount": int(normal_mask.sum()) if normal_mask is not None else None,
    }
    return GroundCandidateResult(candidate.astype(bool), semantic.astype(bool), normal_mask, diagnostics)


def candidate_points(points: np.ndarray, validity: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if points.ndim != 3 or points.shape[-1] < 3 or mask.size == 0:
        return np.empty((0, 3), dtype=np.float32)
    selected = points[..., :3][mask.astype(bool) & validity.astype(bool)]
    if len(selected) == 0:
        return selected.reshape(0, 3)
    return selected[np.isfinite(selected).all(axis=1)]


def _lower_image_prior(shape: tuple[int, int]) -> np.ndarray:
    height, width = shape
    mask = np.zeros(shape, dtype=bool)
    start = int(height * 0.45)
    mask[start:height, :width] = True
    return mask


def _normal_consistency_mask(normals: np.ndarray, seed_mask: np.ndarray) -> np.ndarray | None:
    normal_values = normals[..., :3][seed_mask]
    normal_values = normal_values[np.isfinite(normal_values).all(axis=1)]
    if len(normal_values) < 32:
        return None
    norms = np.linalg.norm(normal_values, axis=1)
    normal_values = normal_values[norms > 1e-6]
    if len(normal_values) < 32:
        return None
    normal_values = normal_values / np.linalg.norm(normal_values, axis=1, keepdims=True)
    expected = np.median(normal_values, axis=0)
    expected = expected / max(np.linalg.norm(expected), 1e-9)
    dense = normals[..., :3].astype(np.float64)
    dense_norm = np.linalg.norm(dense, axis=2, keepdims=True)
    dense_norm = np.maximum(dense_norm, 1e-9)
    dense_unit = dense / dense_norm
    dot = np.abs(np.sum(dense_unit * expected[None, None, :], axis=2))
    return (dot >= 0.45) & np.isfinite(dot)