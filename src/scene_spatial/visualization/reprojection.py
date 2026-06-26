from __future__ import annotations

from pydantic import BaseModel


class ReprojectionMetrics(BaseModel):
    proxy_reprojection_iou: float | None = None
    ready_for_manual_review: bool = True


def empty_reprojection_metrics() -> ReprojectionMetrics:
    return ReprojectionMetrics()
