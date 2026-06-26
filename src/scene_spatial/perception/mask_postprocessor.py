from __future__ import annotations

from pathlib import Path


class MaskPostprocessor:
    def postprocess_directory(self, mask_dir: Path) -> dict[str, object]:
        masks = sorted(path.name for path in mask_dir.glob("*.png")) if mask_dir.exists() else []
        return {
            "maskCount": len(masks),
            "masks": masks,
            "method": "passthrough",
        }
