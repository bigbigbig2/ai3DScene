from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from scene_spatial.infrastructure.database import create_scene_engine, create_session_factory
from scene_spatial.infrastructure.db_models import Base
from scene_spatial.infrastructure.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_runtime_directories()

    engine = create_scene_engine(settings)
    Base.metadata.create_all(bind=engine)

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)

    try:
        yield
    finally:
        engine.dispose()
