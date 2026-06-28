from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


class ImagePreprocessor:
    def prepare_task_images(self, source_path: Path, task_dir: Path) -> dict[str, object]:
        input_dir = task_dir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)

        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            width, height = image.size

            original_path = input_dir / "original.png"
            semantic_path = input_dir / "semantic_input.png"
            sam_path = input_dir / "sam_full.png"
            moge_path = input_dir / "moge_input.png"

            image.save(original_path)
            image.save(semantic_path)
            image.save(sam_path)
            image.save(moge_path)

        identity_transform = {
            "scaleX": 1.0,
            "scaleY": 1.0,
            "offsetX": 0.0,
            "offsetY": 0.0,
            "crop": None,
            "padding": None,
            "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        }
        return {
            "width": width,
            "height": height,
            "original": "input/original.png",
            "semantic_input": "input/semantic_input.png",
            "sam_full": "input/sam_full.png",
            "moge_input": "input/moge_input.png",
            "transforms": {
                "originalSize": [width, height],
                "samSize": [width, height],
                "mogeSize": [width, height],
                "originalToSam": identity_transform,
                "originalToMoge": identity_transform,
                "samToMoge": identity_transform,
            },
        }