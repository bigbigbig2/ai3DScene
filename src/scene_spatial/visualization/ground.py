from __future__ import annotations

from pathlib import Path


def ground_visualization_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "ground.png"
