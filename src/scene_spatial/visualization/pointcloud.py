from __future__ import annotations

from pathlib import Path


def scene_pointcloud_path(task_dir: Path) -> Path:
    return task_dir / "pointcloud" / "scene.ply"
