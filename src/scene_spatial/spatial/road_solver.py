from __future__ import annotations

from pydantic import BaseModel


class RoadObservation(BaseModel):
    id: str
    polygon3d: list[list[float]]
    centerline: list[list[float]]
    estimated_width: float | None = None
    confidence: float = 0.0


def empty_roads() -> list[RoadObservation]:
    return []
