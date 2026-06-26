from __future__ import annotations

from scene_spatial.domain.detection import DetectionMask


def merge_detections(detections: list[DetectionMask]) -> list[DetectionMask]:
    seen: set[str] = set()
    merged: list[DetectionMask] = []
    for detection in detections:
        if detection.id in seen:
            continue
        seen.add(detection.id)
        merged.append(detection)
    return merged
