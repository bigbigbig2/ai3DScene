from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from scene_spatial import __version__
from scene_spatial.api.dependencies import SettingsDep

router = APIRouter()


def _check_writable_directory(path: Path) -> dict[str, str | bool]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        marker = path / ".ready_check"
        marker.write_text("ok", encoding="utf-8")
        marker.unlink(missing_ok=True)
    except Exception as exc:
        return {"ok": False, "path": str(path), "error": str(exc)}
    return {"ok": True, "path": str(path)}


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "scene-spatial-poc",
        "version": __version__,
    }


@router.get("/ready")
def ready(settings: SettingsDep):
    checks = {
        name: _check_writable_directory(path)
        for name, path in settings.runtime_directories().items()
    }
    ok = all(check["ok"] for check in checks.values())
    payload = {
        "status": "ready" if ok else "not_ready",
        "checks": checks,
        "fakeModels": settings.fake_models,
    }
    if not ok:
        return JSONResponse(status_code=503, content=payload)
    return payload
