from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from scene_spatial.worker.main import run_worker


def _proposal() -> dict[str, object]:
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


def _create_ready_task(client: TestClient, runtime_env: Path) -> str:
    source = runtime_env / "source.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 48), color=(128, 128, 128)).save(source)

    with source.open("rb") as file_obj:
        response = client.post(
            "/api/v1/tasks",
            data={"domain": "wastewater_treatment_plant", "semantic_mode": "manual"},
            files={"file": ("source.png", file_obj, "image/png")},
        )
    assert response.status_code == 200, response.text
    created = response.json()
    task_id = created.get("taskId") or created["task_id"]

    response = client.post(f"/api/v1/tasks/{task_id}/semantic-proposal", json=_proposal())
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SEMANTIC_READY"
    return task_id


def test_fake_pipeline_reaches_completed(client: TestClient, runtime_env: Path) -> None:
    task_id = _create_ready_task(client, runtime_env)

    response = client.post(f"/api/v1/tasks/{task_id}/run")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "QUEUED"

    run_worker(once=True)

    response = client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "COMPLETED"

    response = client.get(f"/api/v1/tasks/{task_id}/result")
    assert response.status_code == 200, response.text
    assert response.json()["taskId"] == task_id

    response = client.get(f"/api/v1/tasks/{task_id}/artifacts")
    assert response.status_code == 200, response.text
    assert any(
        artifact["relativePath"] == "spatial/spatial_scene_observation.json"
        for artifact in response.json()["artifacts"]
    )

    response = client.post(
        f"/api/v1/tasks/{task_id}/corrections/scale-anchor",
        json={"objectId": "building_001", "lengthMeters": 30},
    )
    assert response.status_code == 200, response.text
    assert response.json()["correctionType"] == "scale_anchor"

    response = client.post(f"/api/v1/tasks/{task_id}/rerun", json={"fromStage": "moge_estimate"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "QUEUED"

    result_path = runtime_env / "outputs" / task_id / "spatial" / "spatial_scene_observation.json"
    assert result_path.exists()

