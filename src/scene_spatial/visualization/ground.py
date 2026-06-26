from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def ground_visualization_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "ground_candidates.png"


def render_ground_candidate_preview(task_dir: Path, candidate_mask: np.ndarray) -> Path | None:
    if candidate_mask.ndim != 2 or candidate_mask.size == 0:
        return None
    base = _load_base_image(task_dir).resize((candidate_mask.shape[1], candidate_mask.shape[0]), Image.Resampling.BILINEAR)
    mask = Image.fromarray(np.where(candidate_mask, 170, 0).astype(np.uint8), mode="L")
    tint = Image.new("RGBA", base.size, (34, 197, 94, 120))
    overlay = Image.composite(tint, Image.new("RGBA", base.size, (0, 0, 0, 0)), mask)
    result = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    target = ground_visualization_path(task_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    result.save(target)
    return target


def _load_base_image(task_dir: Path) -> Image.Image:
    for relative in ["input/original.png", "input/moge_input.png"]:
        path = task_dir / relative
        if path.exists():
            return Image.open(path).convert("RGB")
    return Image.new("RGB", (640, 480), (248, 250, 252))
