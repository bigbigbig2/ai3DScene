from __future__ import annotations

from pydantic import ValidationError

from scene_spatial.domain.semantic import SceneSemanticProposal


class SemanticValidationResult(dict):
    pass


class SemanticProposalValidator:
    def validate_payload(self, payload: dict[str, object]) -> tuple[SceneSemanticProposal | None, dict[str, object]]:
        try:
            proposal = SceneSemanticProposal.model_validate(payload)
        except ValidationError as exc:
            return None, {"valid": False, "errors": exc.errors()}
        return proposal, {"valid": True, "warnings": [w.model_dump() for w in proposal.warnings]}
