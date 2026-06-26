from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scene_spatial.api.app import create_app
from scene_spatial.infrastructure.settings import get_settings


@pytest.fixture
def runtime_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("SCENE_DATABASE_URL", f"sqlite:///{runtime / 'data' / 'scene_spatial.db'}")
    monkeypatch.setenv("SCENE_OUTPUT_ROOT", str(runtime / "outputs"))
    monkeypatch.setenv("SCENE_INPUT_ROOT", str(runtime / "inputs"))
    monkeypatch.setenv("SCENE_LOG_ROOT", str(runtime / "logs"))
    monkeypatch.setenv("SCENE_TMP_ROOT", str(runtime / "tmp"))
    monkeypatch.setenv("SCENE_FAKE_MODELS", "true")
    get_settings.cache_clear()
    yield runtime
    get_settings.cache_clear()
    for key in list(os.environ):
        if key.startswith("SCENE_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def client(runtime_env: Path):
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
