from __future__ import annotations

from typing import Any

REGION_CATEGORIES = {"ground", "road", "vegetation_region"}


def validate_object_geometry(obj: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    dims = obj.get("dimensions", {}) if isinstance(obj.get("dimensions"), dict) else {}
    width = float(dims.get("width", 0.0) or 0.0)
    height = float(dims.get("height", 0.0) or 0.0)
    length = float(dims.get("length", 0.0) or 0.0)
    category = str(obj.get("category", "unknown"))
    diagnostics = obj.get("geometryDiagnostics", {}) if isinstance(obj.get("geometryDiagnostics"), dict) else {}
    point_count = int(diagnostics.get("pointCount", 0) or 0)
    confidence = obj.get("confidence", {}) if isinstance(obj.get("confidence"), dict) else {}
    pos_conf = float(confidence.get("position", 0.0) or 0.0)

    if width <= 0 or length <= 0:
        reasons.append("non_positive_footprint")
    if category not in REGION_CATEGORIES and height <= 0:
        reasons.append("non_positive_height")
    if max(width, height, length) > 300:
        reasons.append("oversized_dimension")
    if category == "building" and point_count < 24:
        reasons.append("building_too_few_points")
    if category in {"tank", "silo", "cooling_tower"} and point_count < 24:
        reasons.append(f"{category}_too_few_points")
    if category == "street_light" and point_count < 5:
        reasons.append("street_light_too_few_points")
    if category == "tree" and point_count < 8:
        reasons.append("tree_too_few_points")
    if pos_conf < 0.18:
        reasons.append("low_position_confidence")

    group_eligible = not reasons and category not in REGION_CATEGORIES
    quality = {
        "valid": len(reasons) == 0,
        "groupEligible": bool(group_eligible),
        "reasons": reasons,
    }
    obj["geometryQuality"] = quality
    if reasons:
        obj["needsReview"] = True
    return obj


def validate_objects(objects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validated = [validate_object_geometry(obj) for obj in objects]
    rejected_for_group = [obj.get("id") for obj in validated if not obj.get("geometryQuality", {}).get("groupEligible")]
    return validated, {
        "schemaVersion": "1.0",
        "objectCount": len(validated),
        "groupEligibleCount": len(validated) - len(rejected_for_group),
        "groupRejectedObjectIds": rejected_for_group,
    }