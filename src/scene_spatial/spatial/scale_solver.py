from __future__ import annotations

from pydantic import BaseModel


class ScaleSolution(BaseModel):
    unit: str
    scale_factor: float
    source: str


def relative_scale() -> ScaleSolution:
    return ScaleSolution(unit="relative", scale_factor=1.0, source="default")
