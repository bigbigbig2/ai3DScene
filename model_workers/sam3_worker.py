from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def run_fake(request_path: Path, response_path: Path) -> None:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    output_dir = Path(request["outputDir"])
    if not output_dir.is_absolute():
        output_dir = request_path.parent / output_dir
    mask_dir = output_dir / "masks"
    mask_dir.mkdir(parents=True, exist_ok=True)

    image_path = Path(request["imagePath"])
    if not image_path.is_absolute():
        image_path = request_path.parent / image_path

    with Image.open(image_path) as image:
        width, height = image.size

    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    bbox = [int(width * 0.3), int(height * 0.3), int(width * 0.7), int(height * 0.7)]
    draw.rectangle(bbox, fill=255)
    mask_path = mask_dir / "building_001.png"
    mask.save(mask_path)

    detections_path = output_dir / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "model": "fake_sam3",
                "detections": [
                    {
                        "id": "building_001",
                        "category": "building",
                        "bbox": bbox,
                        "score": 0.9,
                        "maskPath": str(mask_path),
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    response_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "model": "fake_sam3",
                "detectionsPath": str(detections_path),
                "maskDir": str(mask_dir),
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
        raise SystemExit("Real SAM 3 integration is implemented on the deployment server.")
    run_fake(Path(args.request), Path(args.response))


if __name__ == "__main__":
    main()
