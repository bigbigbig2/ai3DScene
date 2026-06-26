from __future__ import annotations

from pydantic import BaseModel


class ImageTransform(BaseModel):
    source_width: int
    source_height: int
    target_width: int
    target_height: int
    scale_x: float = 1.0
    scale_y: float = 1.0
    pad_x: int = 0
    pad_y: int = 0

    def map_point_to_target(self, x: float, y: float) -> tuple[float, float]:
        return x * self.scale_x + self.pad_x, y * self.scale_y + self.pad_y

    def map_point_to_source(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.pad_x) / self.scale_x, (y - self.pad_y) / self.scale_y
