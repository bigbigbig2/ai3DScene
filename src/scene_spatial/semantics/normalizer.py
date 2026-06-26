from __future__ import annotations

from scene_spatial.domain.semantic import SceneSemanticProposal


class SemanticProposalNormalizer:
    def normalize(self, proposal: SceneSemanticProposal) -> SceneSemanticProposal:
        data = proposal.model_dump(mode="json")
        for item in data.get("categoryProposals", []):
            item["promptHints"] = self._dedupe_strings(item.get("promptHints", []))
            item["visibleEvidence"] = self._dedupe_strings(item.get("visibleEvidence", []))
        return SceneSemanticProposal.model_validate(data)

    @staticmethod
    def _dedupe_strings(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))
