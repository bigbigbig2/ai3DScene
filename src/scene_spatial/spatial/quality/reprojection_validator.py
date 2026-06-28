from __future__ import annotations

from typing import Any


def summarize_reprojection_readiness(objects: list[dict[str, Any]], groups: list[dict[str, Any]]) -> dict[str, Any]:
    review_count = sum(1 for obj in objects if obj.get("needsReview"))
    return {
        "schemaVersion": "1.0",
        "objectCount": len(objects),
        "groupCount": len(groups),
        "needsReviewCount": int(review_count),
        "readyForManualReview": True,
    }