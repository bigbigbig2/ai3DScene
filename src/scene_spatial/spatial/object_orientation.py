from __future__ import annotations

from pydantic import BaseModel


class ObjectOrientation(BaseModel):
    yaw: float
    unit: str = "degree"


def default_orientation() -> ObjectOrientation:
    return ObjectOrientation(yaw=0.0, unit="degree")
