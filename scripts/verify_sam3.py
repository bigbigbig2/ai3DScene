from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from scene_spatial.infrastructure.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fake", action="store_true", help="run the fake worker path")
    args = parser.parse_args()

    settings = get_settings()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        image_path = root / "sam_input.png"
        tasks_path = root / "sam_tasks.json"
        request_path = root / "sam_request.json"
        response_path = root / "sam_response.json"

        Image.new("RGB", (96, 64), color=(128, 128, 128)).save(image_path)
        tasks_path.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "tasks": [
                        {
                            "category": "building",
                            "objectMode": "instance",
                            "conceptPrompts": ["industrial building"],
                            "runFullImage": True,
                            "runTiles": False,
                            "expectedScale": "large",
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        request_path.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "taskId": "verify_sam3",
                    "imagePath": str(image_path),
                    "tasksPath": str(tasks_path),
                    "outputDir": str(root / "detection"),
                    "device": "cuda:0",
                    "dtype": "bfloat16",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        command = [
            str(settings.sam_python if not args.fake else sys.executable),
            str(settings.sam_worker),
            "--request",
            str(request_path),
            "--response",
            str(response_path),
        ]
        if args.fake:
            command.append("--fake")

        subprocess.run(command, check=True)
        print(response_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
