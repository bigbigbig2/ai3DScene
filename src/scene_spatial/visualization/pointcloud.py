from __future__ import annotations

from pathlib import Path

import numpy as np


def scene_pointcloud_path(task_dir: Path) -> Path:
    return task_dir / "pointcloud" / "scene.ply"


def write_scene_pointcloud(task_dir: Path, max_points: int = 60000) -> Path | None:
    points_path = task_dir / "geometry" / "points.npy"
    if not points_path.exists():
        return None
    try:
        points = np.load(points_path)
    except Exception:
        return None
    if points.ndim != 3 or points.shape[-1] < 3:
        return None
    xyz = points[..., :3].reshape(-1, 3)
    xyz = xyz[np.isfinite(xyz).all(axis=1)]
    if len(xyz) == 0:
        return None
    if len(xyz) > max_points:
        step = max(1, len(xyz) // max_points)
        xyz = xyz[::step][:max_points]
    target = scene_pointcloud_path(task_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as file_obj:
        file_obj.write("ply\n")
        file_obj.write("format ascii 1.0\n")
        file_obj.write(f"element vertex {len(xyz)}\n")
        file_obj.write("property float x\n")
        file_obj.write("property float y\n")
        file_obj.write("property float z\n")
        file_obj.write("end_header\n")
        for x, y, z in xyz:
            file_obj.write(f"{float(x):.6f} {float(y):.6f} {float(z):.6f}\n")
    return target
