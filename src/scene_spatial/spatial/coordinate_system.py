from __future__ import annotations

from pydantic import BaseModel, Field


class CoordinateSystem(BaseModel):
    origin: list[float] = Field(min_length=3, max_length=3)
    x_axis: list[float] = Field(min_length=3, max_length=3)
    y_axis: list[float] = Field(min_length=3, max_length=3)
    z_axis: list[float] = Field(min_length=3, max_length=3)
    unit: str = "relative"


def default_coordinate_system() -> CoordinateSystem:
    return CoordinateSystem(
        origin=[0.0, 0.0, 0.0],
        x_axis=[1.0, 0.0, 0.0],
        y_axis=[0.0, 1.0, 0.0],
        z_axis=[0.0, 0.0, 1.0],
        unit="relative",
    )
