from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CATEGORY_COLORS: dict[str, tuple[int, int, int]] = {
    "building": (37, 99, 235),
    "road": (71, 85, 105),
    "ground": (216, 195, 138),
    "vegetation_region": (34, 197, 94),
    "street_light": (245, 158, 11),
    "water": (14, 165, 233),
    "rectangular_treatment_pool": (124, 58, 237),
}


def masks_visualization_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "masks.png"


def detection_overlay_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "detection_overlay.png"


def mask_contact_sheet_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "mask_contact_sheet.png"


def postprocess_overlay_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "postprocess_overlay.png"


def pixel_alignment_preview_path(task_dir: Path) -> Path:
    return task_dir / "visualizations" / "pixel_alignment.png"


def render_detection_overlay(
    task_dir: Path,
    output_path: Path | None = None,
    detections_relative: str = "detection/detections.json",
) -> Path | None:
    detections = _load_detections(task_dir / detections_relative)
    if not detections:
        return None
    base = _load_base_image(task_dir)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font()

    for detection in detections:
        color = CATEGORY_COLORS.get(str(detection.get("category")), (139, 92, 246))
        mask = _load_detection_mask(task_dir, detection, base.size)
        if mask is not None:
            tint = Image.new("RGBA", base.size, (*color, 70))
            empty = Image.new("RGBA", base.size, (0, 0, 0, 0))
            overlay.alpha_composite(Image.composite(tint, empty, mask))
        bbox = _bbox(detection)
        if bbox is None:
            continue
        draw.rectangle(bbox, outline=(*color, 255), width=3)
        label = f"{detection.get('id', '-')}/{detection.get('category', '-')}"
        score = detection.get("score")
        if isinstance(score, int | float):
            label += f" {score:.2f}"
        _draw_label(draw, bbox[0], bbox[1], label, color, font)

    result = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    target = output_path or detection_overlay_path(task_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    result.save(target)
    return target


def render_mask_contact_sheet(
    task_dir: Path,
    output_path: Path | None = None,
    detections_relative: str = "detection/detections.json",
    max_items: int = 64,
) -> Path | None:
    detections = _load_detections(task_dir / detections_relative)[:max_items]
    if not detections:
        return None

    thumb_w, thumb_h = 180, 132
    columns = 4
    rows = (len(detections) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_w, rows * thumb_h), (248, 250, 252))
    font = _font()

    for index, detection in enumerate(detections):
        col = index % columns
        row = index // columns
        x = col * thumb_w
        y = row * thumb_h
        color = CATEGORY_COLORS.get(str(detection.get("category")), (139, 92, 246))
        mask = _load_detection_mask(task_dir, detection, (thumb_w, thumb_h - 28))
        tile = Image.new("RGB", (thumb_w, thumb_h), (255, 255, 255))
        if mask is not None:
            mask_rgb = Image.new("RGB", mask.size, color)
            tile.paste(mask_rgb, (0, 0), mask)
        sheet.paste(tile, (x, y))
        draw = ImageDraw.Draw(sheet)
        draw.rectangle([x, y, x + thumb_w - 1, y + thumb_h - 1], outline=(226, 232, 240))
        draw.rectangle([x, y + thumb_h - 28, x + thumb_w, y + thumb_h], fill=(15, 23, 42))
        draw.text((x + 6, y + thumb_h - 22), str(detection.get("id", "-"))[:28], fill=(255, 255, 255), font=font)

    target = output_path or mask_contact_sheet_path(task_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)
    return target


def render_pixel_alignment_preview(task_dir: Path, point_shape: list[int] | tuple[int, int]) -> Path | None:
    if len(point_shape) < 2 or int(point_shape[0]) <= 0 or int(point_shape[1]) <= 0:
        return None
    detections = _load_detections(task_dir / "detection" / "detections.json")
    if not detections:
        return None
    width, height = int(point_shape[1]), int(point_shape[0])
    base = _load_base_image(task_dir).resize((width, height), Image.Resampling.BILINEAR)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    for detection in detections:
        color = CATEGORY_COLORS.get(str(detection.get("category")), (139, 92, 246))
        mask = _load_detection_mask(task_dir, detection, base.size)
        if mask is None:
            continue
        tint = Image.new("RGBA", base.size, (*color, 80))
        empty = Image.new("RGBA", base.size, (0, 0, 0, 0))
        overlay.alpha_composite(Image.composite(tint, empty, mask))
    result = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    target = pixel_alignment_preview_path(task_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    result.save(target)
    return target


def _load_base_image(task_dir: Path) -> Image.Image:
    for relative in ["input/original.png", "input/sam_full.png", "input/moge_input.png"]:
        path = task_dir / relative
        if path.exists():
            return Image.open(path).convert("RGB")
    return Image.new("RGB", (640, 480), (248, 250, 252))


def _load_detections(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    detections = payload.get("detections", [])
    return detections if isinstance(detections, list) else []


def _load_detection_mask(task_dir: Path, detection: dict[str, Any], size: tuple[int, int]) -> Image.Image | None:
    mask_path = detection.get("maskPath")
    if not mask_path:
        return None
    path = Path(str(mask_path))
    if not path.is_absolute():
        path = task_dir / path
    if not path.exists():
        return None
    try:
        mask = Image.open(path).convert("L")
    except OSError:
        return None
    if mask.size != size:
        mask = mask.resize(size, Image.Resampling.NEAREST)
    return mask.point(lambda value: 255 if value > 127 else 0)


def _bbox(detection: dict[str, Any]) -> tuple[int, int, int, int] | None:
    value = detection.get("bbox")
    if not isinstance(value, list | tuple) or len(value) < 4:
        return None
    return int(value[0]), int(value[1]), int(value[2]), int(value[3])


def _font() -> ImageFont.ImageFont:
    return ImageFont.load_default()


def _draw_label(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    label: str,
    color: tuple[int, int, int],
    font: ImageFont.ImageFont,
) -> None:
    text_bbox = draw.textbbox((x, y), label, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    top = max(0, y - text_h - 6)
    draw.rectangle([x, top, x + text_w + 8, top + text_h + 6], fill=(*color, 230))
    draw.text((x + 4, top + 3), label, fill=(255, 255, 255), font=font)
