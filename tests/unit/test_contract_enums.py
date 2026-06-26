from scene_spatial.application.pipeline_definition import PIPELINE
from scene_spatial.domain.enums import PipelineStageName, TaskStatus


def test_task_status_contract_uses_uppercase_values() -> None:
    assert TaskStatus.WAITING_SEMANTIC_PROPOSAL.value == "WAITING_SEMANTIC_PROPOSAL"
    assert TaskStatus.SEMANTIC_READY.value == "SEMANTIC_READY"
    assert TaskStatus.COMPLETED.value == "COMPLETED"


def test_pipeline_contract_order() -> None:
    assert PIPELINE == [
        PipelineStageName.BUILD_SAM_TASKS.value,
        PipelineStageName.SAM_SEGMENT.value,
        PipelineStageName.MASK_POSTPROCESS.value,
        PipelineStageName.MOGE_ESTIMATE.value,
        PipelineStageName.PIXEL_ALIGN.value,
        PipelineStageName.GROUND_SOLVE.value,
        PipelineStageName.OBJECT_SOLVE.value,
        PipelineStageName.GROUP_SOLVE.value,
        PipelineStageName.EXPORT.value,
        PipelineStageName.EVALUATE.value,
    ]
