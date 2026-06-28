from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scene_spatial.domain.enums import Category, ObjectMode


SCENE_TYPES = (
    "wastewater_treatment_plant",
    "industrial_park",
    "warehouse_yard",
    "urban_road",
    "unknown",
)

IMAGE_TYPES = (
    "oblique_aerial_view",
    "top_down_aerial_view",
    "ground_level_photo",
    "editor_render",
    "architectural_render",
    "site_plan",
    "unknown",
)

EXPECTED_SCALES = ("small", "medium", "large", "unknown")
PATTERN_TYPES = ("grid", "row", "along_path", "cluster", "symmetric", "repeated", "unknown")

INSTANCE_CATEGORIES = {
    Category.BUILDING,
    Category.RECTANGULAR_TREATMENT_POOL,
    Category.TREE,
    Category.STREET_LIGHT,
}
REGION_CATEGORIES = {
    Category.GROUND,
    Category.ROAD,
    Category.WATER,
    Category.VEGETATION_REGION,
}


class SceneInfo(BaseModel):
    sceneType: Literal[
        "wastewater_treatment_plant",
        "industrial_park",
        "warehouse_yard",
        "urban_road",
        "unknown",
    ]
    imageType: Literal[
        "oblique_aerial_view",
        "top_down_aerial_view",
        "ground_level_photo",
        "editor_render",
        "architectural_render",
        "site_plan",
        "unknown",
    ]
    supportedDomain: bool
    semanticConfidence: float = Field(ge=0, le=1)


class CategoryProposal(BaseModel):
    category: Category
    objectMode: ObjectMode
    semanticConfidence: float = Field(ge=0, le=1)
    promptHints: list[str] = Field(default_factory=list)
    expectedScale: Literal["small", "medium", "large", "unknown"]
    visibleEvidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def category_mode_must_match(self) -> "CategoryProposal":
        if self.category in INSTANCE_CATEGORIES and self.objectMode != ObjectMode.INSTANCE:
            raise ValueError(f"{self.category.value} must use objectMode=instance")
        if self.category in REGION_CATEGORIES and self.objectMode != ObjectMode.REGION:
            raise ValueError(f"{self.category.value} must use objectMode=region")
        return self


class PatternHint(BaseModel):
    category: Category
    patternType: Literal["grid", "row", "along_path", "cluster", "symmetric", "repeated", "unknown"]
    semanticConfidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def pattern_category_must_be_instance(self) -> "PatternHint":
        if self.category not in INSTANCE_CATEGORIES:
            raise ValueError("patternHints only support instance categories")
        return self


class SemanticWarning(BaseModel):
    code: str
    message: str


class SceneSemanticProposal(BaseModel):
    schemaVersion: Literal["1.0"]
    scene: SceneInfo
    categoryProposals: list[CategoryProposal]
    patternHints: list[PatternHint] = Field(default_factory=list)
    warnings: list[SemanticWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def proposal_must_be_consistent(self) -> "SceneSemanticProposal":
        seen: set[Category] = set()
        for proposal in self.categoryProposals:
            if proposal.category in seen:
                raise ValueError(f"duplicated category: {proposal.category.value}")
            seen.add(proposal.category)

        for hint in self.patternHints:
            if hint.category not in seen:
                raise ValueError(
                    f"patternHints category must appear in categoryProposals: {hint.category.value}"
                )
        return self


class SemanticImportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    status: str
    validation: dict[str, object]

