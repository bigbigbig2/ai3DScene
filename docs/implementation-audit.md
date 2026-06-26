# Implementation Audit

Source of truth:

```text
scene-spatial-poc-宸ョ▼鏋舵瀯涓庡惎鍔ㄥ疄鏂芥柟妗?涓瓑瑙勬ā鐗?md
```

The first-stage semantic/spatial document is used as algorithm and acceptance
detail only. If the two documents conflict, the medium-scale engineering
architecture document wins.

Editor work is intentionally out of scope for the current implementation pass.
The backend still exports `SpatialSceneObservation` and evaluation artifacts so
an editor can consume them later.

## Stage Status

| Stage | Current implementation | Remaining server verification |
| --- | --- | --- |
| 0. Engineering contract | API prefix, task states, stage names, artifact layout, schemas, and deployment paths are captured in `docs/engineering-contract.md` and `schemas/`. | Review with server paths before deployment. |
| 1. Minimal engineering skeleton | FastAPI app, settings, SQLite models, runtime directories, health/ready endpoints, Alembic env, initial migration. | Run `uvicorn`, `/health`, `/ready`, and Alembic on server. |
| 2. Task creation | `POST /api/v1/tasks` creates DB row, task directory, normalized image copies, metadata, and initial artifacts. | Run upload smoke with real images. |
| 3. Manual semantic import | Pydantic contract, validator/normalizer/provider, `categories.yaml`, prompt builder, `sam_tasks.json`, import API. | Test several online-VLM JSON outputs. |
| 4. Worker and Fake Pipeline | SQLite queue, claim, heartbeat, stale recovery, orchestrator, stage recording, artifacts, result API, corrections, rerun. | Run `python scripts/smoke_fake_pipeline.py` and `pytest`. |
| 5. MoGe integration | File protocol, model worker wrapper, real subprocess stage path, fake worker smoke script. | Replace worker body with real MoGe, then run `scripts/verify_moge2.py`. |
| 6. SAM integration | File protocol, model worker wrapper, real subprocess stage path, fake worker smoke script. | Replace worker body with real SAM 3, then run `scripts/verify_sam3.py`. |
| 7. Core spatial chain | Implemented backend spatial stages for pixel alignment, ground plane fitting, coordinate system, object anchors, dimensions, orientation, roads, and groups. Uses NumPy by default, Open3D/OpenCV when installed. | Validate against real SAM/MoGe outputs and add golden fixtures. |
| 8. Expansion and evaluation | Result export, artifacts, corrections, road output, grid/group estimation, mask bbox evaluation, backend visualization path helpers. | Improve pool/grid/road accuracy with real scenes and quantitative labels. |

## Main Architecture Checklist

- API process does not import model packages: satisfied by subprocess file protocols.
- Worker process owns long-running pipeline: implemented by `scene_spatial.worker.main`.
- SQLite queue and local artifact store: implemented.
- Model subprocess protocol: implemented for SAM and MoGe request/response files.
- GPU lock/monitor utilities: implemented as infrastructure modules.
- Rerun without deleting old artifacts: implemented as conservative requeue from `fromStage`.
- Corrections API: implemented for ground points, scale anchor, and object transform.
- Editor preview: deferred by user request.

## Verification Commands

Run on the target server or any machine with Python 3.11+:

```bash
pip install -e ".[dev]"
python scripts/smoke_fake_pipeline.py
pytest
python scripts/verify_sam3.py --fake
python scripts/verify_moge2.py --fake
bash scripts/inspect_gpu.sh
```

Only after the fake path is green should `SCENE_FAKE_MODELS=false` be enabled.

