from __future__ import annotations

from pydantic import BaseModel, Field

from scene_spatial.domain.enums import Category, ObjectMode


class DetectionMask(BaseModel):
    id: str
    category: Category
    object_mode: ObjectMode
    bbox: list[int] = Field(min_length=4, max_length=4)
    score: float = Field(ge=0, le=1)
    mask_path: str
    partial: bool = False
    warnings: list[str] = Field(default_factory=list)


class DetectionSet(BaseModel):
    schema_version: str = "1.0"
    model: str
    detections: list[DetectionMask]
