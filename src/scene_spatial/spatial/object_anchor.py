from __future__ import annotations

from pydantic import BaseModel, Field


class ObjectAnchor(BaseModel):
    type: str
    position: list[float] = Field(min_length=3, max_length=3)


def fallback_bottom_center() -> ObjectAnchor:
    return ObjectAnchor(type="bottom_center", position=[0.0, 0.0, 0.0])
