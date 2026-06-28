from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PixelTransform:
    original_size: tuple[int, int]
    sam_size: tuple[int, int]
    moge_size: tuple[int, int]
    scale_x: float
    scale_y: float
    offset_x: float
    offset_y: float
    matrix: list[list[float]]
    crop: Any = None
    padding: Any = None
    source: str = "metadata"

    def map_xy(self, xy: np.ndarray) -> np.ndarray:
        if xy.size == 0:
            return xy.astype(np.float64)
        points = xy.astype(np.float64).copy()
        points[:, 0] = points[:, 0] * self.scale_x + self.offset_x
        points[:, 1] = points[:, 1] * self.scale_y + self.offset_y
        return points

    def as_payload(self) -> dict[str, Any]:
        return {
            "originalSize": list(self.original_size),
            "samSize": list(self.sam_size),
            "mogeSize": list(self.moge_size),
            "scaleX": float(self.scale_x),
            "scaleY": float(self.scale_y),
            "offsetX": float(self.offset_x),
            "offsetY": float(self.offset_y),
            "crop": self.crop,
            "padding": self.padding,
            "matrix": self.matrix,
            "source": self.source,
        }


def build_pixel_mapping(metadata: dict[str, Any], point_shape: tuple[int, int]) -> dict[str, Any]:
    transform = load_sam_to_moge_transform(metadata, point_shape)
    height, width = point_shape
    verified = height > 0 and width > 0 and transform.sam_size[0] > 0 and transform.sam_size[1] > 0
    return {
        "schemaVersion": "1.0",
        "sourceImageShape": [int(metadata.get("height", transform.original_size[1])), int(metadata.get("width", transform.original_size[0]))],
        "pointMapShape": [int(height), int(width)],
        "samToMoge": transform.as_payload(),
        "resampling": "nearest",
        "verified": bool(verified),
        "normalPath": "geometry/normals.npy",
        "fallback": kornia_lightglue_fallback_state(enabled=False),
    }


def load_sam_to_moge_transform(metadata: dict[str, Any], point_shape: tuple[int, int]) -> PixelTransform:
    transforms = metadata.get("transforms") if isinstance(metadata.get("transforms"), dict) else {}
    width = int(metadata.get("width", 0) or 0)
    height = int(metadata.get("height", 0) or 0)
    original_size = _size_tuple(transforms.get("originalSize"), default=(width, height))
    sam_size = _size_tuple(transforms.get("samSize"), default=(width, height))
    moge_size = _size_tuple(transforms.get("mogeSize"), default=(int(point_shape[1]), int(point_shape[0])))
    if point_shape[0] > 0 and point_shape[1] > 0:
        moge_size = (int(point_shape[1]), int(point_shape[0]))

    direct = transforms.get("samToMoge") if isinstance(transforms.get("samToMoge"), dict) else None
    if direct:
        scale_x = float(direct.get("scaleX", moge_size[0] / max(1, sam_size[0])))
        scale_y = float(direct.get("scaleY", moge_size[1] / max(1, sam_size[1])))
        offset_x = float(direct.get("offsetX", 0.0))
        offset_y = float(direct.get("offsetY", 0.0))
        matrix = direct.get("matrix") or _matrix(scale_x, scale_y, offset_x, offset_y)
        return PixelTransform(
            original_size=original_size,
            sam_size=sam_size,
            moge_size=moge_size,
            scale_x=scale_x,
            scale_y=scale_y,
            offset_x=offset_x,
            offset_y=offset_y,
            matrix=_clean_matrix(matrix, scale_x, scale_y, offset_x, offset_y),
            crop=direct.get("crop"),
            padding=direct.get("padding"),
            source="metadata.samToMoge",
        )

    scale_x = moge_size[0] / max(1, sam_size[0])
    scale_y = moge_size[1] / max(1, sam_size[1])
    return PixelTransform(
        original_size=original_size,
        sam_size=sam_size,
        moge_size=moge_size,
        scale_x=float(scale_x),
        scale_y=float(scale_y),
        offset_x=0.0,
        offset_y=0.0,
        matrix=_matrix(scale_x, scale_y, 0.0, 0.0),
        source="size_ratio_fallback",
    )


def apply_mask_to_moge(mask: np.ndarray, transform: PixelTransform, point_shape: tuple[int, int]) -> np.ndarray:
    if mask.size == 0 or point_shape == (0, 0):
        return np.zeros(point_shape, dtype=bool)
    ys, xs = np.where(mask)
    xy = np.column_stack([xs, ys])
    mapped = transform.map_xy(xy)
    mapped_x = np.rint(mapped[:, 0]).astype(np.int64)
    mapped_y = np.rint(mapped[:, 1]).astype(np.int64)
    keep = (mapped_x >= 0) & (mapped_x < point_shape[1]) & (mapped_y >= 0) & (mapped_y < point_shape[0])
    out = np.zeros(point_shape, dtype=bool)
    out[mapped_y[keep], mapped_x[keep]] = True
    return out


def kornia_lightglue_fallback_state(enabled: bool) -> dict[str, Any]:
    available = _module_available("kornia")
    return {
        "engine": "kornia_lightglue",
        "available": available,
        "enabled": bool(enabled and available),
        "reason": "metadata transform is deterministic; feature matching is reserved for unknown crop/warp cases",
    }


def _size_tuple(value: Any, default: tuple[int, int]) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (int(value[0] or 0), int(value[1] or 0))
    return default


def _matrix(scale_x: float, scale_y: float, offset_x: float, offset_y: float) -> list[list[float]]:
    return [[float(scale_x), 0.0, float(offset_x)], [0.0, float(scale_y), float(offset_y)], [0.0, 0.0, 1.0]]


def _clean_matrix(value: Any, scale_x: float, scale_y: float, offset_x: float, offset_y: float) -> list[list[float]]:
    if isinstance(value, list) and len(value) == 3 and all(isinstance(row, list) and len(row) == 3 for row in value):
        return [[float(cell) for cell in row] for row in value]
    return _matrix(scale_x, scale_y, offset_x, offset_y)


def _module_available(name: str) -> bool:
    try:
        __import__(name)
    except Exception:
        return False
    return True