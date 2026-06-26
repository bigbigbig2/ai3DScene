from enum import StrEnum


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    PREPROCESSING = "PREPROCESSING"
    WAITING_SEMANTIC_PROPOSAL = "WAITING_SEMANTIC_PROPOSAL"
    SEMANTIC_VALIDATING = "SEMANTIC_VALIDATING"
    SEMANTIC_READY = "SEMANTIC_READY"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    BUILDING_SAM_TASKS = "BUILDING_SAM_TASKS"
    SEGMENTING = "SEGMENTING"
    MASK_POSTPROCESSING = "MASK_POSTPROCESSING"
    GEOMETRY_ESTIMATING = "GEOMETRY_ESTIMATING"
    PIXEL_ALIGNING = "PIXEL_ALIGNING"
    GROUND_SOLVING = "GROUND_SOLVING"
    OBJECT_SOLVING = "OBJECT_SOLVING"
    GROUP_SOLVING = "GROUP_SOLVING"
    EXPORTING = "EXPORTING"
    EVALUATING = "EVALUATING"
    PREVIEW_READY = "PREVIEW_READY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    WAITING_MANUAL_GROUND = "WAITING_MANUAL_GROUND"
    WAITING_SCALE_ANCHOR = "WAITING_SCALE_ANCHOR"


class StageStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class SemanticMode(StrEnum):
    MANUAL = "manual"


class ObjectMode(StrEnum):
    INSTANCE = "instance"
    REGION = "region"


class Category(StrEnum):
    GROUND = "ground"
    BUILDING = "building"
    RECTANGULAR_TREATMENT_POOL = "rectangular_treatment_pool"
    ROAD = "road"
    WATER = "water"
    VEGETATION_REGION = "vegetation_region"
    STREET_LIGHT = "street_light"


class PipelineStageName(StrEnum):
    PREPROCESS = "preprocess"
    SEMANTIC_IMPORT = "semantic_import"
    BUILD_SAM_TASKS = "build_sam_tasks"
    SAM_SEGMENT = "sam_segment"
    MASK_POSTPROCESS = "mask_postprocess"
    MOGE_ESTIMATE = "moge_estimate"
    PIXEL_ALIGN = "pixel_align"
    GROUND_SOLVE = "ground_solve"
    OBJECT_SOLVE = "object_solve"
    GROUP_SOLVE = "group_solve"
    EXPORT = "export"
    EVALUATE = "evaluate"


class ArtifactType(StrEnum):
    IMAGE = "image"
    JSON = "json"
    MASK = "mask"
    NUMPY = "numpy"
    POINT_CLOUD = "point_cloud"
    LOG = "log"
    VISUALIZATION = "visualization"
    REPORT = "report"
