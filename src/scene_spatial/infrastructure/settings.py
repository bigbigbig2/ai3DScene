from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_runtime_root() -> Path:
    return project_root() / ".runtime"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SCENE_",
        extra="ignore",
    )

    env: str = "development"
    database_url: str = Field(
        default_factory=lambda: f"sqlite:///{default_runtime_root() / 'data' / 'scene_spatial.db'}"
    )
    output_root: Path = Field(default_factory=lambda: default_runtime_root() / "outputs")
    input_root: Path = Field(default_factory=lambda: default_runtime_root() / "inputs")
    log_root: Path = Field(default_factory=lambda: default_runtime_root() / "logs")
    tmp_root: Path = Field(default_factory=lambda: default_runtime_root() / "tmp")

    gpu_physical_id: int = 0
    sam_python: Path = Path("/home/ai3d/envs/scene-sam3/bin/python")
    moge_python: Path = Path("/home/ai3d/envs/scene-moge2/bin/python")
    sam_worker: Path = Field(default_factory=lambda: project_root() / "model_workers" / "sam3_worker.py")
    moge_worker: Path = Field(
        default_factory=lambda: project_root() / "model_workers" / "moge2_worker.py"
    )

    worker_poll_seconds: int = 2
    task_lease_seconds: int = 1800
    fake_models: bool = True

    def database_path(self) -> Path | None:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            return Path(self.database_url.removeprefix(prefix))
        return None

    def runtime_directories(self) -> dict[str, Path]:
        directories = {
            "output_root": self.output_root,
            "input_root": self.input_root,
            "log_root": self.log_root,
            "tmp_root": self.tmp_root,
        }
        db_path = self.database_path()
        if db_path is not None:
            directories["database_parent"] = db_path.parent
        return directories

    def ensure_runtime_directories(self) -> None:
        for path in self.runtime_directories().values():
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
