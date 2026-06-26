from __future__ import annotations

from pydantic import BaseModel


class SpatialGroup(BaseModel):
    id: str
    category: str
    object_ids: list[str]
    pattern_type: str
    confidence: float


def empty_groups() -> list[SpatialGroup]:
    return []
