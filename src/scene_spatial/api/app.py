from __future__ import annotations

from fastapi import FastAPI

from scene_spatial import __version__
from scene_spatial.api.lifespan import lifespan
from scene_spatial.api.routes import corrections, health, results, semantic, tasks


def create_app() -> FastAPI:
    app = FastAPI(
        title="Scene Spatial PoC",
        version=__version__,
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
    app.include_router(semantic.router, prefix="/api/v1", tags=["semantic"])
    app.include_router(results.router, prefix="/api/v1", tags=["results"])
    app.include_router(corrections.router, prefix="/api/v1", tags=["corrections"])

    return app


app = create_app()
