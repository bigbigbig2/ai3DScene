#!/usr/bin/env bash
set -euo pipefail

GPU_ID="${SCENE_GPU_PHYSICAL_ID:-0}"

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi not found"
  exit 1
fi

nvidia-smi --id="${GPU_ID}"
nvidia-smi --id="${GPU_ID}" --query-gpu=index,name,memory.total,memory.used,memory.free --format=csv
