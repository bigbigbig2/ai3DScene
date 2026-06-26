from __future__ import annotations

from pathlib import Path


def depth_visualization_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "depth.png"
