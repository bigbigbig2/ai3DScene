from __future__ import annotations

from pydantic import BaseModel


class ObjectDimensions(BaseModel):
    width: float
    height: float
    length: float
    unit: str = "relative"


def unit_box_dimensions() -> ObjectDimensions:
    return ObjectDimensions(width=1.0, height=1.0, length=1.0, unit="relative")
