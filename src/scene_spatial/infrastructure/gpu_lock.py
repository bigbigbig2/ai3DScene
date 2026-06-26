from __future__ import annotations

import os
import time
from pathlib import Path


class GpuFileLock:
    def __init__(self, lock_file: Path, timeout_seconds: int = 60) -> None:
        self.lock_file = lock_file
        self.timeout_seconds = timeout_seconds
        self._fd: int | None = None

    def acquire(self) -> None:
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.timeout_seconds
        while True:
            try:
                self._fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self._fd, str(os.getpid()).encode("utf-8"))
                return
            except FileExistsError:
                if time.time() >= deadline:
                    raise TimeoutError(f"Timed out waiting for GPU lock: {self.lock_file}")
                time.sleep(0.5)

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self.lock_file.unlink(missing_ok=True)

    def __enter__(self) -> "GpuFileLock":
        self.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()
