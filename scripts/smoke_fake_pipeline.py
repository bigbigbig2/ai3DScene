from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from scene_spatial.api.app import create_app
from scene_spatial.infrastructure.settings import get_settings
from scene_spatial.worker.main import run_worker


def proposal() -> dict[str, object]:
    return {
        "schemaVersion": "1.0",
        "scene": {
            "sceneType": "wastewater_treatment_plant",
            "imageType": "oblique_aerial_view",
            "supportedDomain": True,
            "semanticConfidence": 0.9,
        },
        "categoryProposals": [
            {
                "category": "building",
                "objectMode": "instance",
                "semanticConfidence": 0.9,
                "promptHints": ["large rectangular industrial building"],
                "expectedScale": "large",
                "visibleEvidence": ["rectangular roof"],
            }
        ],
        "patternHints": [],
        "warnings": [],
    }


def main() -> None:
    settings = get_settings()
    settings.ensure_runtime_directories()
    smoke_image = settings.tmp_root / "scene_spatial_smoke.png"
    Image.new("RGB", (96, 64), color=(128, 128, 128)).save(smoke_image)

    with TestClient(create_app()) as client:
        with smoke_image.open("rb") as file_obj:
            create_response = client.post(
                "/api/v1/tasks",
                data={"domain": "wastewater_treatment_plant", "semantic_mode": "manual"},
                files={"file": ("scene_spatial_smoke.png", file_obj, "image/png")},
            )
        create_response.raise_for_status()
        created = create_response.json()
        task_id = created.get("taskId") or created["task_id"]

        semantic_response = client.post(f"/api/v1/tasks/{task_id}/semantic-proposal", json=proposal())
        semantic_response.raise_for_status()

        run_response = client.post(f"/api/v1/tasks/{task_id}/run")
        run_response.raise_for_status()

    run_worker(once=True)

    result_path = settings.output_root / task_id / "spatial" / "spatial_scene_observation.json"
    if not result_path.exists():
        raise SystemExit(f"Smoke pipeline did not produce result: {result_path}")

    print(json.dumps({"taskId": task_id, "resultPath": str(result_path)}, indent=2))


if __name__ == "__main__":
    main()

