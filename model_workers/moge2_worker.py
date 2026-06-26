from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from moge.model.v2 import MoGeModel


DEFAULT_CHECKPOINT = (
    "/home/ai3d/models/moge-2-vitl/model.pt"
)


def resolve_path(request_path: Path, value: str) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    candidates = [
        request_path.parent / path,
        request_path.parent.parent / path,
        Path.cwd() / path,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return (request_path.parent.parent / path).resolve()


def to_numpy(value: object) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        return (
            value.detach()
            .float()
            .cpu()
            .numpy()
        )

    return np.asarray(value)


def estimate_normals(
    points: np.ndarray,
    validity: np.ndarray,
) -> np.ndarray:
    points = np.asarray(points, dtype=np.float32)
    validity = np.asarray(validity, dtype=bool)

    finite = np.isfinite(points).all(axis=-1)
    valid = validity & finite

    # 无效点先归零，避免 inf / NaN 进入差分运算。
    safe_points = np.where(
        finite[..., None],
        points,
        0.0,
    ).astype(np.float32, copy=False)

    dx = np.zeros_like(safe_points)
    dy = np.zeros_like(safe_points)

    dx[:, 1:-1] = (
        safe_points[:, 2:] - safe_points[:, :-2]
    )
    dy[1:-1, :] = (
        safe_points[2:, :] - safe_points[:-2, :]
    )

    # 只有中心点及上下左右邻域全部有效时才计算法线。
    neighborhood_valid = np.zeros_like(valid)

    neighborhood_valid[1:-1, 1:-1] = (
        valid[1:-1, 1:-1]
        & valid[1:-1, :-2]
        & valid[1:-1, 2:]
        & valid[:-2, 1:-1]
        & valid[2:, 1:-1]
    )

    normals = np.cross(dx, dy)
    lengths = np.linalg.norm(normals, axis=-1)

    good = (
        neighborhood_valid
        & np.isfinite(lengths)
        & (lengths > 1e-8)
    )

    normals[good] /= lengths[good, None]
    normals[~good] = 0.0

    return normals.astype(np.float32, copy=False)


def write_fake_npy(path: Path) -> None:
    np.save(
        path,
        np.zeros((2, 2, 3), dtype=np.float32),
    )


def run_fake(request_path: Path, response_path: Path) -> None:
    request = json.loads(
        request_path.read_text(encoding="utf-8")
    )

    output_dir = resolve_path(
        request_path,
        request["outputDir"],
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    for name in [
        "points",
        "depth",
        "normals",
        "validity",
    ]:
        write_fake_npy(output_dir / f"{name}.npy")

    camera_path = output_dir / "camera.json"
    camera_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "model": "fake_moge2",
                "intrinsics": {
                    "fx": 1.0,
                    "fy": 1.0,
                    "cx": 0.5,
                    "cy": 0.5,
                },
                "unit": "relative",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "model": "fake_moge2",
                "pointsPath": str(
                    output_dir / "points.npy"
                ),
                "depthPath": str(
                    output_dir / "depth.npy"
                ),
                "normalsPath": str(
                    output_dir / "normals.npy"
                ),
                "validityPath": str(
                    output_dir / "validity.npy"
                ),
                "cameraPath": str(camera_path),
                "durationMs": 0,
                "peakGpuMemoryMiB": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def run_real(request_path: Path, response_path: Path) -> None:
    started = time.perf_counter()

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

    request = json.loads(
        request_path.read_text(encoding="utf-8")
    )

    image_path = resolve_path(
        request_path,
        request["imagePath"],
    )
    output_dir = resolve_path(
        request_path,
        request["outputDir"],
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    checkpoint = Path(
        os.environ.get(
            "SCENE_MOGE_CHECKPOINT",
            DEFAULT_CHECKPOINT,
        )
    )

    if not image_path.is_file():
        raise FileNotFoundError(
            f"图片不存在：{image_path}"
        )

    if not checkpoint.is_file():
        raise FileNotFoundError(
            f"MoGe checkpoint 不存在：{checkpoint}"
        )

    device = str(request.get("device") or "cuda:0")

    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA 不可用")

    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()

    model = MoGeModel.from_pretrained(
        str(checkpoint)
    )
    model = model.to(device).eval()

    pil_image = Image.open(image_path).convert("RGB")
    image_array = np.asarray(pil_image)

    image = torch.from_numpy(image_array.copy())
    image = image.permute(2, 0, 1)
    image = image.float().div(255.0).to(device)

    with torch.inference_mode():
        output = model.infer(image)

    required_keys = {
        "points",
        "depth",
        "mask",
        "intrinsics",
    }

    missing = required_keys - set(output)

    if missing:
        raise KeyError(
            f"MoGe 输出缺少字段：{sorted(missing)}"
        )

    points = to_numpy(output["points"]).astype(
        np.float32,
        copy=False,
    )
    depth = to_numpy(output["depth"]).astype(
        np.float32,
        copy=False,
    )
    mask = to_numpy(output["mask"])
    intrinsics = to_numpy(output["intrinsics"]).astype(
        np.float32,
        copy=False,
    )

    if points.ndim != 3 or points.shape[-1] != 3:
        raise ValueError(
            f"points shape 非法：{points.shape}"
        )

    height, width = points.shape[:2]

    if depth.shape != (height, width):
        raise ValueError(
            f"depth shape 非法：{depth.shape}"
        )

    if mask.shape != (height, width):
        raise ValueError(
            f"mask shape 非法：{mask.shape}"
        )

    validity = (
        (mask > 0.5)
        & np.isfinite(depth)
        & np.isfinite(points).all(axis=-1)
    )

    normals = estimate_normals(
        points,
        validity,
    )

    points_path = output_dir / "points.npy"
    depth_path = output_dir / "depth.npy"
    normals_path = output_dir / "normals.npy"
    validity_path = output_dir / "validity.npy"
    camera_path = output_dir / "camera.json"

    np.save(points_path, points)
    np.save(depth_path, depth)
    np.save(normals_path, normals)
    np.save(validity_path, validity.astype(np.bool_))

    camera_payload = {
        "schemaVersion": "1.0",
        "model": "moge2",
        "intrinsics": {
            "fx": float(intrinsics[0, 0]),
            "fy": float(intrinsics[1, 1]),
            "cx": float(intrinsics[0, 2]),
            "cy": float(intrinsics[1, 2]),
        },
        "intrinsicsMatrix": intrinsics.tolist(),
        "imageSize": {
            "width": int(width),
            "height": int(height),
        },
        "unit": "relative",
        "coordinateSystem": "camera",
    }

    camera_path.write_text(
        json.dumps(
            camera_payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    peak_memory_mib = 0

    if device.startswith("cuda"):
        peak_memory_mib = int(
            torch.cuda.max_memory_allocated()
            / 1024
            / 1024
        )

    duration_ms = int(
        (time.perf_counter() - started) * 1000
    )

    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "model": "moge2",
                "pointsPath": str(points_path),
                "depthPath": str(depth_path),
                "normalsPath": str(normals_path),
                "validityPath": str(validity_path),
                "cameraPath": str(camera_path),
                "durationMs": duration_ms,
                "peakGpuMemoryMiB": peak_memory_mib,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    parser.add_argument("--fake", action="store_true")
    args = parser.parse_args()

    request_path = Path(args.request).resolve()
    response_path = Path(args.response).resolve()

    if args.fake:
        run_fake(request_path, response_path)
    else:
        run_real(request_path, response_path)


if __name__ == "__main__":
    main()
