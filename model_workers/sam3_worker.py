from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image

from sam3.model.sam3_image_processor import Sam3Processor
from sam3.model_builder import build_sam3_image_model


DEFAULT_CHECKPOINT = (
    "/home/ai3d/models/scene-spatial/sam3/sam3.pt"
)
DEFAULT_BPE_PATH = (
    "/home/ai3d/src/sam3/sam3/assets/"
    "bpe_simple_vocab_16e6.txt.gz"
)


def resolve_path(request_path: Path, value: str) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    candidates = [
        request_path.parent / path,
        request_path.parent.parent / path,
        Path.cwd() / path,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return (request_path.parent.parent / path).resolve()


def safe_name(value: str) -> str:
    value = value.strip().lower().replace(" ", "_")
    value = re.sub(r"[^a-z0-9_-]+", "_", value)
    value = value.strip("_")
    return value or "object"


def read_tasks(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw_tasks = payload
    elif isinstance(payload, dict):
        raw_tasks = (
            payload.get("tasks")
            or payload.get("samTasks")
            or payload.get("items")
            or []
        )
    else:
        raw_tasks = []

    return [
        task for task in raw_tasks
        if isinstance(task, dict)
    ]


def read_prompts(task: dict[str, Any]) -> list[str]:
    prompts: list[str] = []

    for key in ("prompt", "textPrompt", "query"):
        value = task.get(key)
        if isinstance(value, str) and value.strip():
            prompts.append(value.strip())

    for key in (
        "prompts",
        "promptHints",
        "conceptPrompts",
        "textPrompts",
        "queries",
    ):
        value = task.get(key)

        if isinstance(value, list):
            prompts.extend(
                item.strip()
                for item in value
                if isinstance(item, str) and item.strip()
            )

    category = str(
        task.get("category")
        or task.get("label")
        or task.get("className")
        or "object"
    )

    if not prompts:
        prompts.append(category.replace("_", " "))

    # 保持顺序去重
    return list(dict.fromkeys(prompts))


def box_iou(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))

    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)

    area_a = max(0.0, float(a[2] - a[0])) * max(
        0.0,
        float(a[3] - a[1]),
    )
    area_b = max(0.0, float(b[2] - b[0])) * max(
        0.0,
        float(b[3] - b[1]),
    )

    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def nms_candidates(
    candidates: list[dict[str, Any]],
    threshold: float = 0.7,
) -> list[dict[str, Any]]:
    ordered = sorted(
        candidates,
        key=lambda item: float(item["score"]),
        reverse=True,
    )

    kept: list[dict[str, Any]] = []

    for candidate in ordered:
        if all(
            box_iou(candidate["bbox"], existing["bbox"])
            < threshold
            for existing in kept
        ):
            kept.append(candidate)

    return kept


def mask_bbox(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(mask)

    if len(xs) == 0:
        return np.array([0, 0, 0, 0], dtype=np.float32)

    return np.array(
        [
            float(xs.min()),
            float(ys.min()),
            float(xs.max() + 1),
            float(ys.max() + 1),
        ],
        dtype=np.float32,
    )


def run_fake(request_path: Path, response_path: Path) -> None:
    from PIL import ImageDraw

    request = json.loads(
        request_path.read_text(encoding="utf-8")
    )

    output_dir = resolve_path(
        request_path,
        request["outputDir"],
    )
    mask_dir = output_dir / "masks"
    mask_dir.mkdir(parents=True, exist_ok=True)

    image_path = resolve_path(
        request_path,
        request["imagePath"],
    )

    with Image.open(image_path) as image:
        width, height = image.size

    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)

    bbox = [
        int(width * 0.3),
        int(height * 0.3),
        int(width * 0.7),
        int(height * 0.7),
    ]

    draw.rectangle(bbox, fill=255)

    mask_path = mask_dir / "building_001.png"
    mask.save(mask_path)

    detections_path = output_dir / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "model": "fake_sam3",
                "detections": [
                    {
                        "id": "building_001",
                        "category": "building",
                        "bbox": bbox,
                        "score": 0.9,
                        "maskPath": str(mask_path),
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "model": "fake_sam3",
                "detectionsPath": str(detections_path),
                "maskDir": str(mask_dir),
                "durationMs": 0,
                "peakGpuMemoryMiB": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def run_real(request_path: Path, response_path: Path) -> None:
    started = time.perf_counter()

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

    request = json.loads(
        request_path.read_text(encoding="utf-8")
    )

    image_path = resolve_path(
        request_path,
        request["imagePath"],
    )
    tasks_path = resolve_path(
        request_path,
        request["tasksPath"],
    )
    output_dir = resolve_path(
        request_path,
        request["outputDir"],
    )

    mask_dir = output_dir / "masks"
    mask_dir.mkdir(parents=True, exist_ok=True)

    checkpoint = Path(
        os.environ.get(
            "SCENE_SAM_CHECKPOINT",
            DEFAULT_CHECKPOINT,
        )
    )
    bpe_path = Path(
        os.environ.get(
            "SCENE_SAM_BPE_PATH",
            DEFAULT_BPE_PATH,
        )
    )

    if not image_path.is_file():
        raise FileNotFoundError(f"图片不存在：{image_path}")

    if not tasks_path.is_file():
        raise FileNotFoundError(
            f"SAM tasks 不存在：{tasks_path}"
        )

    if not checkpoint.is_file():
        raise FileNotFoundError(
            f"SAM checkpoint 不存在：{checkpoint}"
        )

    if not bpe_path.is_file():
        raise FileNotFoundError(
            f"SAM BPE 不存在：{bpe_path}"
        )

    device = str(request.get("device") or "cuda:0")
    build_device = "cuda" if device.startswith("cuda") else device

    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA 不可用")

    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()

    task_payload = json.loads(
        tasks_path.read_text(encoding="utf-8")
    )
    tasks = read_tasks(task_payload)

    if not tasks:
        raise ValueError(
            f"sam_tasks.json 中没有可执行任务：{tasks_path}"
        )

    image = Image.open(image_path).convert("RGB")
    width, height = image.size

    model = build_sam3_image_model(
        bpe_path=str(bpe_path),
        checkpoint_path=str(checkpoint),
        load_from_HF=False,
        device=build_device,
        eval_mode=True,
        enable_segmentation=True,
        enable_inst_interactivity=False,
        compile=False,
    )

    # 显式保证所有模型权重进入请求指定的 GPU。
    model = model.to(device).eval()

    processor = Sam3Processor(
        model,
        confidence_threshold=0.20,
    )

    detections: list[dict[str, Any]] = []

    with torch.inference_mode(), torch.autocast(
        device_type="cuda",
        dtype=torch.bfloat16,
        enabled=device.startswith("cuda"),
    ):
        state = processor.set_image(image)

        for task in tasks:
            category = str(
                task.get("category")
                or task.get("label")
                or task.get("className")
                or "object"
            )

            mode = str(
                task.get("mode")
                or task.get("objectMode")
                or "instance"
            ).lower()

            threshold = float(
                task.get("confidenceThreshold")
                or task.get("minScore")
                or task.get("threshold")
                or 0.25
            )

            max_instances = int(
                task.get("maxInstances")
                or task.get("maxDetections")
                or 50
            )

            candidates: list[dict[str, Any]] = []

            for prompt in read_prompts(task):
                output = processor.set_text_prompt(
                    state=state,
                    prompt=prompt,
                )

                masks = (
                    output["masks"]
                    .detach()
                    .float()
                    .cpu()
                    .numpy()
                )
                boxes = (
                    output["boxes"]
                    .detach()
                    .float()
                    .cpu()
                    .numpy()
                    .reshape(-1, 4)
                )
                scores = (
                    output["scores"]
                    .detach()
                    .float()
                    .cpu()
                    .numpy()
                    .reshape(-1)
                )

                if masks.ndim == 4 and masks.shape[1] == 1:
                    masks = masks[:, 0]
                elif masks.ndim == 2:
                    masks = masks[None, ...]

                count = min(
                    len(masks),
                    len(boxes),
                    len(scores),
                )

                for index in range(count):
                    score = float(scores[index])

                    if score < threshold:
                        continue

                    mask = np.asarray(masks[index]) > 0.5

                    if mask.shape != (height, width):
                        raise ValueError(
                            "SAM Mask 尺寸与输入图片不一致："
                            f"{mask.shape} != {(height, width)}"
                        )

                    if not mask.any():
                        continue

                    bbox = np.asarray(
                        boxes[index],
                        dtype=np.float32,
                    )

                    bbox[0::2] = np.clip(
                        bbox[0::2],
                        0,
                        width,
                    )
                    bbox[1::2] = np.clip(
                        bbox[1::2],
                        0,
                        height,
                    )

                    candidates.append(
                        {
                            "category": category,
                            "prompt": prompt,
                            "score": score,
                            "bbox": bbox,
                            "mask": mask,
                        }
                    )

            if mode in {"region", "semantic", "stuff"}:
                if candidates:
                    merged_mask = np.logical_or.reduce(
                        [
                            candidate["mask"]
                            for candidate in candidates
                        ]
                    )

                    candidates = [
                        {
                            "category": category,
                            "prompt": " | ".join(
                                read_prompts(task)
                            ),
                            "score": max(
                                float(item["score"])
                                for item in candidates
                            ),
                            "bbox": mask_bbox(merged_mask),
                            "mask": merged_mask,
                        }
                    ]
            else:
                candidates = nms_candidates(
                    candidates,
                    threshold=0.70,
                )[:max_instances]

            category_name = safe_name(category)

            for candidate in candidates:
                object_index = 1 + sum(
                    item["category"] == category
                    for item in detections
                )

                detection_id = (
                    f"{category_name}_{object_index:03d}"
                )
                mask_path = mask_dir / f"{detection_id}.png"

                Image.fromarray(
                    candidate["mask"].astype(np.uint8) * 255,
                    mode="L",
                ).save(mask_path)

                detections.append(
                    {
                        "id": detection_id,
                        "category": category,
                        "prompt": candidate["prompt"],
                        "bbox": [
                            float(value)
                            for value in candidate["bbox"].tolist()
                        ],
                        "score": float(candidate["score"]),
                        "maskPath": str(mask_path),
                    }
                )

    detections_path = output_dir / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "model": "sam3",
                "imagePath": str(image_path),
                "imageSize": {
                    "width": width,
                    "height": height,
                },
                "detections": detections,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    peak_memory_mib = 0

    if device.startswith("cuda"):
        peak_memory_mib = int(
            torch.cuda.max_memory_allocated()
            / 1024
            / 1024
        )

    duration_ms = int(
        (time.perf_counter() - started) * 1000
    )

    response_path.parent.mkdir(parents=True, exist_ok=True)
    response_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "model": "sam3",
                "detectionsPath": str(detections_path),
                "maskDir": str(mask_dir),
                "durationMs": duration_ms,
                "peakGpuMemoryMiB": peak_memory_mib,
                "detectionCount": len(detections),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    parser.add_argument("--fake", action="store_true")
    args = parser.parse_args()

    request_path = Path(args.request).resolve()
    response_path = Path(args.response).resolve()

    if args.fake:
        run_fake(request_path, response_path)
    else:
        run_real(request_path, response_path)


if __name__ == "__main__":
    main()
