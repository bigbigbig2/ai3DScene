from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from scene_spatial.domain.stage import StageContext, StageResult
from scene_spatial.infrastructure.subprocess_runner import SubprocessResultError, SubprocessRunner
from scene_spatial.stages.fake_pipeline import (
    MogeEstimateStage as FakeMogeEstimateStage,
    SamSegmentStage as FakeSamSegmentStage,
    _read_json,
    _write_json,
)
from scene_spatial.visualization.depth import (
    render_depth_preview,
    render_normals_preview,
    render_validity_preview,
)
from scene_spatial.visualization.masks import render_detection_overlay, render_mask_contact_sheet
from scene_spatial.visualization.pointcloud import write_scene_pointcloud


def _worker_path(task_dir: Path, value: object) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    return task_dir / path


class SamSegmentStage(FakeSamSegmentStage):
    def execute(self, ctx: StageContext) -> StageResult:
        if ctx.fake_models:
            return super().execute(ctx)
        started_at = datetime.now(UTC)
        return self._execute_model_worker(ctx, started_at)

    def _execute_model_worker(self, ctx: StageContext, started_at: datetime) -> StageResult:
        if ctx.sam_python is None or ctx.sam_worker is None:
            return StageResult.failed(
                self.name,
                started_at,
                "SAM_WORKER_NOT_CONFIGURED",
                "SAM python or worker path is not configured",
            )

        request_path = ctx.task_dir / "stages" / "sam_request_attempt_1.json"
        response_path = ctx.task_dir / "stages" / "sam_response_attempt_1.json"
        _write_json(
            request_path,
            {
                "schemaVersion": "1.0",
                "taskId": ctx.task_id,
                "imagePath": str(ctx.task_dir / "input" / "sam_full.png"),
                "tasksPath": str(ctx.task_dir / "semantic" / "sam_tasks.json"),
                "outputDir": str(ctx.task_dir / "detection" / "raw"),
                "device": "cuda:0",
                "dtype": "bfloat16",
            },
        )

        try:
            SubprocessRunner().run(
                [
                    str(ctx.sam_python),
                    str(ctx.sam_worker),
                    "--request",
                    str(request_path),
                    "--response",
                    str(response_path),
                ],
                cwd=ctx.task_dir,
                timeout_seconds=self.timeout_seconds,
                stdout_path=ctx.task_dir / "logs" / "sam.stdout.log",
                stderr_path=ctx.task_dir / "logs" / "sam.stderr.log",
            )
        except (OSError, SubprocessResultError) as exc:
            return StageResult.failed(self.name, started_at, "SAM_WORKER_FAILED", str(exc))

        if not response_path.exists():
            return StageResult.failed(
                self.name,
                started_at,
                "SAM_RESPONSE_MISSING",
                "SAM worker did not write a response file",
            )

        response = _read_json(response_path)
        if response.get("status") != "completed":
            return StageResult.failed(
                self.name,
                started_at,
                "SAM_INFERENCE_ERROR",
                str(response.get("error", "SAM worker failed")),
            )

        detections_path = _worker_path(ctx.task_dir, response["detectionsPath"])
        mask_dir = _worker_path(ctx.task_dir, response["maskDir"])
        final_detections = ctx.task_dir / "detection" / "detections.json"
        final_mask_dir = ctx.task_dir / "detection" / "masks"
        if not detections_path.exists():
            return StageResult.failed(
                self.name,
                started_at,
                "SAM_OUTPUT_MISSING",
                f"SAM detections file is missing: {detections_path}",
            )
        shutil.copyfile(detections_path, final_detections)
        if mask_dir.exists():
            shutil.copytree(mask_dir, final_mask_dir, dirs_exist_ok=True)

        outputs = {
            "request": "stages/sam_request_attempt_1.json",
            "response": "stages/sam_response_attempt_1.json",
            "detections": "detection/detections.json",
            "mask_dir": "detection/masks",
        }
        if render_detection_overlay(ctx.task_dir):
            outputs["detection_overlay"] = "visualizations/detection_overlay.png"
        if render_mask_contact_sheet(ctx.task_dir):
            outputs["mask_contact_sheet"] = "visualizations/mask_contact_sheet.png"

        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={
                "duration_ms": int(response.get("durationMs", 0)),
                "peak_gpu_memory_mib": int(response.get("peakGpuMemoryMiB", 0)),
            },
        )


class MogeEstimateStage(FakeMogeEstimateStage):
    def execute(self, ctx: StageContext) -> StageResult:
        if ctx.fake_models:
            return super().execute(ctx)
        started_at = datetime.now(UTC)
        return self._execute_model_worker(ctx, started_at)

    def _execute_model_worker(self, ctx: StageContext, started_at: datetime) -> StageResult:
        if ctx.moge_python is None or ctx.moge_worker is None:
            return StageResult.failed(
                self.name,
                started_at,
                "MOGE_WORKER_NOT_CONFIGURED",
                "MoGe python or worker path is not configured",
            )

        request_path = ctx.task_dir / "stages" / "moge_request_attempt_1.json"
        response_path = ctx.task_dir / "stages" / "moge_response_attempt_1.json"
        _write_json(
            request_path,
            {
                "schemaVersion": "1.0",
                "taskId": ctx.task_id,
                "imagePath": str(ctx.task_dir / "input" / "moge_input.png"),
                "outputDir": str(ctx.task_dir / "geometry"),
                "device": "cuda:0",
                "dtype": "float16",
            },
        )

        try:
            SubprocessRunner().run(
                [
                    str(ctx.moge_python),
                    str(ctx.moge_worker),
                    "--request",
                    str(request_path),
                    "--response",
                    str(response_path),
                ],
                cwd=ctx.task_dir,
                timeout_seconds=self.timeout_seconds,
                stdout_path=ctx.task_dir / "logs" / "moge.stdout.log",
                stderr_path=ctx.task_dir / "logs" / "moge.stderr.log",
            )
        except (OSError, SubprocessResultError) as exc:
            return StageResult.failed(self.name, started_at, "MOGE_WORKER_FAILED", str(exc))

        if not response_path.exists():
            return StageResult.failed(
                self.name,
                started_at,
                "MOGE_RESPONSE_MISSING",
                "MoGe worker did not write a response file",
            )

        response = _read_json(response_path)
        if response.get("status") != "completed":
            return StageResult.failed(
                self.name,
                started_at,
                "MOGE_INFERENCE_ERROR",
                str(response.get("error", "MoGe worker failed")),
            )

        output_keys = {
            "pointsPath": "geometry/points.npy",
            "depthPath": "geometry/depth.npy",
            "normalsPath": "geometry/normals.npy",
            "validityPath": "geometry/validity.npy",
            "cameraPath": "geometry/camera.json",
        }
        missing: list[str] = []
        for response_key, final_relative in output_keys.items():
            source = _worker_path(ctx.task_dir, response[response_key])
            target = ctx.task_dir / final_relative
            if not source.exists():
                missing.append(str(source))
                continue
            if source.resolve() != target.resolve():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)

        if missing:
            return StageResult.failed(
                self.name,
                started_at,
                "MOGE_OUTPUT_MISSING",
                f"MoGe outputs are missing: {missing}",
            )

        outputs = {
            "request": "stages/moge_request_attempt_1.json",
            "response": "stages/moge_response_attempt_1.json",
            "points": "geometry/points.npy",
            "depth": "geometry/depth.npy",
            "normals": "geometry/normals.npy",
            "validity": "geometry/validity.npy",
            "camera": "geometry/camera.json",
        }
        if render_depth_preview(ctx.task_dir):
            outputs["depth_preview"] = "visualizations/depth.png"
        if render_normals_preview(ctx.task_dir):
            outputs["normals_preview"] = "visualizations/normals.png"
        if render_validity_preview(ctx.task_dir):
            outputs["validity_preview"] = "visualizations/validity.png"
        if write_scene_pointcloud(ctx.task_dir):
            outputs["pointcloud"] = "pointcloud/scene.ply"

        return StageResult.completed(
            self.name,
            started_at,
            outputs=outputs,
            metrics={
                "duration_ms": int(response.get("durationMs", 0)),
                "peak_gpu_memory_mib": int(response.get("peakGpuMemoryMiB", 0)),
            },
        )
