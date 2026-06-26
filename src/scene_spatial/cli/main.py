from __future__ import annotations

import argparse

from scene_spatial.worker.main import run_worker


def main() -> None:
    parser = argparse.ArgumentParser(prog="scene-spatial")
    subparsers = parser.add_subparsers(dest="command", required=True)
    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.command == "worker":
        run_worker(once=args.once)


if __name__ == "__main__":
    main()
