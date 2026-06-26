from __future__ import annotations

import argparse
import socket
import time

from scene_spatial.application.orchestrator import PipelineOrchestrator
from scene_spatial.infrastructure.database import create_scene_engine, create_session_factory
from scene_spatial.infrastructure.db_models import Base
from scene_spatial.infrastructure.settings import get_settings
from scene_spatial.worker.heartbeat import refresh_task_lease
from scene_spatial.worker.job_claimer import JobClaimer
from scene_spatial.worker.recovery import recover_stale_jobs


def run_worker(once: bool = False) -> None:
    settings = get_settings()
    settings.ensure_runtime_directories()
    engine = create_scene_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    worker_id = f"{socket.gethostname()}:{time.time_ns()}"

    try:
        while True:
            session = session_factory()
            try:
                recover_stale_jobs(session)
                task = JobClaimer(settings, session, worker_id).claim_next()
                if task is not None:
                    refresh_task_lease(session, settings, task)
                    session.commit()
                    PipelineOrchestrator(settings, session).run(task)
                elif once:
                    return
            finally:
                session.close()

            if once:
                return
            time.sleep(settings.worker_poll_seconds)
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="claim and run at most one queued task")
    args = parser.parse_args()
    run_worker(once=args.once)


if __name__ == "__main__":
    main()
