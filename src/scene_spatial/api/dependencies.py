from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from scene_spatial.infrastructure.settings import Settings, get_settings


def get_app_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", get_settings())


def get_db_session(request: Request) -> Session:
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[Session, Depends(get_db_session)]
