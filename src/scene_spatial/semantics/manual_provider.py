from __future__ import annotations

import json
from pathlib import Path

from scene_spatial.domain.semantic import SceneSemanticProposal


class ManualSemanticProposalProvider:
    def load(self, path: Path) -> SceneSemanticProposal:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SceneSemanticProposal.model_validate(payload)
