from __future__ import annotations

import argparse
import json
from pathlib import Path


def _write_fake_npy(path: Path) -> None:
    try:
        import numpy as np

        np.save(path, np.zeros((2, 2, 3), dtype=np.float32))
    except ModuleNotFoundError:
        path.write_bytes(b"FAKE_NPY_PLACEHOLDER\n")


def run_fake(request_path: Path, response_path: Path) -> None:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    output_dir = Path(request["outputDir"])
    if not output_dir.is_absolute():
        output_dir = request_path.parent / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for name in ["points", "depth", "normals", "validity"]:
        _write_fake_npy(output_dir / f"{name}.npy")

    camera_path = output_dir / "camera.json"
    camera_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "model": "fake_moge2",
                "intrinsics": {"fx": 1.0, "fy": 1.0, "cx": 0.5, "cy": 0.5},
                "unit": "relative",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    response_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "pointsPath": str(output_dir / "points.npy"),
                "depthPath": str(output_dir / "depth.npy"),
                "normalsPath": str(output_dir / "normals.npy"),
                "validityPath": str(output_dir / "validity.npy"),
                "cameraPath": str(camera_path),
                "durationMs": 0,
                "peakGpuMemoryMiB": 0,
            },
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

    if not args.fake:
        raise SystemExit("Real MoGe-2 integration is implemented on the deployment server.")
    run_fake(Path(args.request), Path(args.response))


if __name__ == "__main__":
    main()
