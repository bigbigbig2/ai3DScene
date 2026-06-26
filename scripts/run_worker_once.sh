#!/usr/bin/env bash
set -euo pipefail

cd "${SCENE_PROJECT_ROOT:-/home/ai3d/src/scene-spatial-poc}"
export PYTHONPATH="${PWD}/src:${PYTHONPATH:-}"
exec "${SCENE_CORE_PYTHON:-/home/ai3d/envs/scene-core/bin/python}" \
  -m scene_spatial.worker.main --once
