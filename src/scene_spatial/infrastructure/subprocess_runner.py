from __future__ import annotations

import subprocess
from pathlib import Path


class SubprocessResultError(RuntimeError):
    pass


class SubprocessRunner:
    def run(
        self,
        command: list[str],
        cwd: Path,
        timeout_seconds: int,
        stdout_path: Path | None = None,
        stderr_path: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if stdout_path:
            stdout_path.parent.mkdir(parents=True, exist_ok=True)
        if stderr_path:
            stderr_path.parent.mkdir(parents=True, exist_ok=True)

        stdout_file = stdout_path.open("w", encoding="utf-8") if stdout_path else subprocess.PIPE
        stderr_file = stderr_path.open("w", encoding="utf-8") if stderr_path else subprocess.PIPE
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                timeout=timeout_seconds,
                text=True,
                stdout=stdout_file,
                stderr=stderr_file,
                check=False,
            )
        finally:
            if stdout_path:
                stdout_file.close()
            if stderr_path:
                stderr_file.close()

        if completed.returncode != 0:
            raise SubprocessResultError(
                f"Command failed with exit code {completed.returncode}: {' '.join(command)}"
            )
        return completed
