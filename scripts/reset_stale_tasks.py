from __future__ import annotations

from scene_spatial.infrastructure.database import create_scene_engine, create_session_factory
from scene_spatial.infrastructure.db_models import Base
from scene_spatial.infrastructure.settings import get_settings
from scene_spatial.worker.recovery import recover_stale_jobs


def main() -> None:
    settings = get_settings()
    settings.ensure_runtime_directories()
    engine = create_scene_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        recovered = recover_stale_jobs(session)
        print(f"Recovered stale tasks: {recovered}")
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
