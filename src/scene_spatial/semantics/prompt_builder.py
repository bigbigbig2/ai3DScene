from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scene_spatial.domain.semantic import SceneSemanticProposal


class PromptBuilder:
    def __init__(self, categories_config_path: Path) -> None:
        self.categories_config_path = categories_config_path

    def build_sam_tasks(self, proposal: SceneSemanticProposal) -> dict[str, Any]:
        categories_config = yaml.safe_load(
            self.categories_config_path.read_text(encoding="utf-8")
        )
        category_map = categories_config["categories"]
        scene_type = proposal.scene.sceneType
        tasks: list[dict[str, Any]] = []

        for category_proposal in proposal.categoryProposals:
            category_key = category_proposal.category.value
            category_config = category_map[category_key]
            prompts = self._prompts_for_scene(category_config, scene_type)
            prompts.extend(category_proposal.promptHints)
            deduped_prompts = list(dict.fromkeys(prompt.strip() for prompt in prompts if prompt.strip()))

            tasks.append(
                {
                    "category": category_key,
                    "objectMode": category_proposal.objectMode.value,
                    "conceptPrompts": deduped_prompts[:8],
                    "runFullImage": True,
                    "runTiles": bool(category_config.get("allow_tile_inference", False)),
                    "expectedScale": category_proposal.expectedScale,
                }
            )

        return {
            "schemaVersion": "1.0",
            "tasks": tasks,
        }

    @staticmethod
    def _prompts_for_scene(category_config: dict[str, Any], scene_type: str) -> list[str]:
        scene_prompts = category_config.get("scene_prompts", {})
        if isinstance(scene_prompts, dict):
            prompts = scene_prompts.get(scene_type)
            if isinstance(prompts, list) and prompts:
                return list(prompts)
        return list(category_config.get("base_prompts", []))
