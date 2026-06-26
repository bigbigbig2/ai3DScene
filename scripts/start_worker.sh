#!/usr/bin/env bash
set -euo pipefail

cd /home/ai3d/src/scene-spatial-poc
export PYTHONPATH="/home/ai3d/src/scene-spatial-poc/src:${PYTHONPATH:-}"
exec /home/ai3d/envs/scene-core/bin/python \
  -m scene_spatial.worker.main
