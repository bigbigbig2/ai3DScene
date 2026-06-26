from __future__ import annotations

import subprocess


def query_gpu_free_memory_mib(gpu_id: int) -> int | None:
    command = [
        "nvidia-smi",
        f"--id={gpu_id}",
        "--query-gpu=memory.free",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None

    first_line = completed.stdout.strip().splitlines()[0]
    try:
        return int(first_line)
    except ValueError:
        return None
