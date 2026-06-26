from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scene_spatial.infrastructure.settings import Settings


TASK_SUBDIRECTORIES = [
    "config_snapshot",
    "stages",
    "input",
    "input/tiles",
    "semantic",
    "detection/raw",
    "detection/masks",
    "detection/tiles",
    "geometry",
    "pointcloud/objects",
    "spatial",
    "visualizations",
    "evaluation",
    "logs",
]


class ArtifactStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def task_dir(self, task_id: str) -> Path:
        return self.settings.output_root / task_id

    def create_task_layout(self, task_id: str) -> Path:
        task_dir = self.task_dir(task_id)
        task_dir.mkdir(parents=True, exist_ok=False)
        for relative in TASK_SUBDIRECTORIES:
            (task_dir / relative).mkdir(parents=True, exist_ok=True)
        return task_dir

    def write_json(self, task_id: str, relative_path: str, payload: dict[str, Any]) -> Path:
        path = self.task_dir(task_id) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)
        return path

    def relative_to_task(self, task_id: str, path: Path) -> str:
        return path.relative_to(self.task_dir(task_id)).as_posix()
