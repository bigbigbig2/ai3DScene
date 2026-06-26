from __future__ import annotations

from pydantic import BaseModel


class CameraIntrinsics(BaseModel):
    fx: float
    fy: float
    cx: float
    cy: float


class GeometryFrame(BaseModel):
    schema_version: str = "1.0"
    points_path: str
    depth_path: str
    normals_path: str
    validity_path: str
    camera_path: str
    pixel_mapping_path: str | None = None
