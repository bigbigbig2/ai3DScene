from __future__ import annotations

from pydantic import BaseModel, Field


class GroundPlane(BaseModel):
    plane: list[float] = Field(min_length=4, max_length=4)
    normal: list[float] = Field(min_length=3, max_length=3)
    inlier_ratio: float
    point_count: int
    method: str
    confidence: float


def fallback_ground_plane() -> GroundPlane:
    return GroundPlane(
        plane=[0.0, 1.0, 0.0, 0.0],
        normal=[0.0, 1.0, 0.0],
        inlier_ratio=0.0,
        point_count=0,
        method="fallback",
        confidence=0.0,
    )
