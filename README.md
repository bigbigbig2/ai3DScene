# Scene Spatial PoC

Detailed current engineering guide:

```text
docs/current-project-guide.md
`````

This repository is the engineering skeleton for the medium-scale Scene Spatial PoC.
The implementation follows `scene-spatial-poc-宸ョ▼鏋舵瀯涓庡惎鍔ㄥ疄鏂芥柟妗?涓瓑瑙勬ā鐗?md`.

Current scope:

1. Stage 0: freeze the engineering contract for API paths, task states, pipeline stages, artifact layout, and model worker file protocols.
2. Stage 1: provide the minimal FastAPI application, settings model, runtime directory validation, and health/readiness endpoints.

Run locally after installing dependencies:

```bash
uvicorn scene_spatial.api.app:app --host 0.0.0.0 --port 8180
```

Useful endpoints:

```text
GET /health
GET /ready
```

Server deployment is intended to use:

```text
/home/ai3d/src/scene-spatial-poc
/home/ai3d/data/scene-spatial
/home/ai3d/outputs/scene-spatial
/home/ai3d/logs/scene-spatial
/home/ai3d/tmp/scene-spatial
/home/ai3d/models/scene-spatial
```




