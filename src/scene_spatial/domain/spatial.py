from __future__ import annotations

from pydantic import BaseModel, Field


class SpatialConfidence(BaseModel):
    category: float = Field(ge=0, le=1)
    detection: float = Field(ge=0, le=1)
    mask: float = Field(ge=0, le=1)
    position: float = Field(ge=0, le=1)
    dimensions: float = Field(ge=0, le=1)
    rotation: float = Field(ge=0, le=1)


class SpatialObject(BaseModel):
    id: str
    category: str
    anchor: dict[str, object]
    dimensions: dict[str, object]
    rotation: dict[str, object]
    confidence: SpatialConfidence


class SpatialSceneObservation(BaseModel):
    schema_version: str = "1.0"
    task_id: str
    source: str
    objects: list[SpatialObject]
    artifacts: dict[str, str]
