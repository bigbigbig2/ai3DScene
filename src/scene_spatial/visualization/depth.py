from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def depth_visualization_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "depth.png"


def normals_visualization_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "normals.png"


def validity_visualization_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "validity.png"


def render_depth_preview(task_dir: Path) -> Path | None:
    depth_path = task_dir / "geometry" / "depth.npy"
    points_path = task_dir / "geometry" / "points.npy"
    depth: np.ndarray | None = None
    if depth_path.exists():
        depth = _load_array(depth_path)
        if depth.ndim == 3:
            depth = depth[..., 0]
    elif points_path.exists():
        points = _load_array(points_path)
        if points.ndim == 3 and points.shape[-1] >= 3:
            depth = points[..., 2]
    if depth is None or depth.ndim != 2:
        return None
    target = depth_visualization_path(task_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    _heatmap(depth).save(target)
    return target


def render_normals_preview(task_dir: Path) -> Path | None:
    normals_path = task_dir / "geometry" / "normals.npy"
    if not normals_path.exists():
        return None
    normals = _load_array(normals_path)
    if normals.ndim != 3 or normals.shape[-1] < 3:
        return None
    rgb = np.clip((normals[..., :3].astype(np.float32) * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
    target = normals_visualization_path(task_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(target)
    return target


def render_validity_preview(task_dir: Path) -> Path | None:
    validity_path = task_dir / "geometry" / "validity.npy"
    if not validity_path.exists():
        return None
    validity = _load_array(validity_path)
    if validity.ndim == 3:
        validity = validity[..., 0]
    if validity.ndim != 2:
        return None
    image = np.where(validity.astype(bool), 255, 0).astype(np.uint8)
    target = validity_visualization_path(task_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image, mode="L").save(target)
    return target


def _load_array(path: Path) -> np.ndarray:
    try:
        return np.load(path)
    except Exception:
        return np.zeros((2, 2), dtype=np.float32)


def _heatmap(values: np.ndarray) -> Image.Image:
    values = values.astype(np.float32)
    finite = np.isfinite(values)
    if not finite.any():
        normalized = np.zeros(values.shape, dtype=np.float32)
    else:
        valid = values[finite]
        lo, hi = np.percentile(valid, [2, 98])
        if hi <= lo:
            hi = lo + 1.0
        normalized = np.clip((values - lo) / (hi - lo), 0, 1)
        normalized[~finite] = 0
    r = np.clip(255 * np.maximum(0, normalized * 2 - 0.35), 0, 255)
    g = np.clip(255 * (1 - np.abs(normalized - 0.55) * 1.8), 0, 255)
    b = np.clip(255 * (1 - normalized * 1.25), 0, 255)
    rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB")
