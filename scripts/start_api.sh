#!/usr/bin/env bash
set -euo pipefail

cd /home/ai3d/src/scene-spatial-poc
export PYTHONPATH="/home/ai3d/src/scene-spatial-poc/src:${PYTHONPATH:-}"
exec /home/ai3d/envs/scene-core/bin/uvicorn \
  scene_spatial.api.app:app \
  --host 0.0.0.0 \
  --port 8181 \
  --workers 1
