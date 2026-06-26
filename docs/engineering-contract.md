# Scene Spatial PoC Engineering Contract

This contract is the implementation baseline for Stage 0 and Stage 1.
The architecture source of truth is:

```text
scene-spatial-poc-工程架构与启动实施方案-中等规模版.md
```

## Runtime Shape

The project is a modular monolith with three runtime process families:

```text
FastAPI API process
Pipeline Worker process
Short-lived SAM / MoGe model subprocesses
```

The API process never loads SAM, MoGe, Torch, or Open3D-heavy workloads.
Long-running work is claimed by the Pipeline Worker from SQLite.

## API Prefix

The stable API prefix is:

```text
/api/v1
```

Stage 1 only exposes:

```text
GET /health
GET /ready
```

Stage 2 will add:

```text
POST /api/v1/tasks
GET /api/v1/tasks/{task_id}
POST /api/v1/tasks/{task_id}/semantic-proposal
POST /api/v1/tasks/{task_id}/run
GET /api/v1/tasks/{task_id}/artifacts
GET /api/v1/tasks/{task_id}/result
```

## Task Status Values

Internal status values are uppercase strings:

```text
CREATED
PREPROCESSING
WAITING_SEMANTIC_PROPOSAL
SEMANTIC_VALIDATING
SEMANTIC_READY
QUEUED
RUNNING
BUILDING_SAM_TASKS
SEGMENTING
MASK_POSTPROCESSING
GEOMETRY_ESTIMATING
PIXEL_ALIGNING
GROUND_SOLVING
OBJECT_SOLVING
GROUP_SOLVING
EXPORTING
EVALUATING
PREVIEW_READY
COMPLETED
FAILED
CANCELLED
WAITING_MANUAL_GROUND
WAITING_SCALE_ANCHOR
```

## Pipeline Stage Names

Stage names are lowercase snake_case identifiers:

```text
preprocess
semantic_import
build_sam_tasks
sam_segment
mask_postprocess
moge_estimate
pixel_align
ground_solve
object_solve
group_solve
export
evaluate
```

## Artifact Layout

Each task owns one artifact directory:

```text
outputs/<task_id>/
├── task.json
├── config_snapshot/
├── stages/
├── input/
├── semantic/
├── detection/
├── geometry/
├── pointcloud/
├── spatial/
├── visualizations/
├── evaluation/
└── logs/
```

Large arrays, masks, images, and point clouds live on disk. SQLite stores only
state, metadata, relative paths, errors, timings, and confidence summaries.

## File Protocols

Model subprocess communication is file-based:

```text
sam_request.json -> model_workers/sam3_worker.py -> sam_response.json
moge_request.json -> model_workers/moge2_worker.py -> moge_response.json
```

The core package must not import SAM, MoGe, Torch, or model-specific packages.

## Server Layout

The intended deployment layout is:

```text
/home/ai3d/src/scene-spatial-poc
/home/ai3d/data/scene-spatial
/home/ai3d/inputs/scene-spatial
/home/ai3d/outputs/scene-spatial
/home/ai3d/logs/scene-spatial
/home/ai3d/tmp/scene-spatial
/home/ai3d/models/scene-spatial
```

The Stage 1 app keeps local defaults under `.runtime/` so development can start
without touching server paths.
