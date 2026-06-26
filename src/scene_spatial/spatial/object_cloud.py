from __future__ import annotations

from pydantic import BaseModel


class ObjectCloudSummary(BaseModel):
    object_id: str
    point_count: int
    raw_path: str | None = None
    clean_path: str | None = None
    confidence: float = 0.0


def empty_cloud_summary(object_id: str) -> ObjectCloudSummary:
    return ObjectCloudSummary(object_id=object_id, point_count=0)
