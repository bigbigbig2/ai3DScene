import type { ArtifactItem, TaskStatusResponse } from '../api/types'

export const PIPELINE = [
  'build_sam_tasks',
  'sam_segment',
  'mask_postprocess',
  'moge_estimate',
  'pixel_align',
  'ground_solve',
  'object_solve',
  'group_solve',
  'export',
  'evaluate',
] as const

export type PipelineStageName = (typeof PIPELINE)[number]

export type InferredStageStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface StageDisplayMeta {
  title: string
  description: string
}

export const STAGE_DISPLAY: Record<PipelineStageName, StageDisplayMeta> = {
  build_sam_tasks: {
    title: '生成 SAM 分割任务',
    description: '把语义提案转换成 SAM 可执行的分割请求。',
  },
  sam_segment: {
    title: 'SAM 图像分割',
    description: '调用 SAM 产出对象/区域 mask 和 detections。',
  },
  mask_postprocess: {
    title: 'Mask 后处理',
    description: '清理、过滤和整理分割结果，形成标准检测产物。',
  },
  moge_estimate: {
    title: 'MoGe 几何估计',
    description: '从单张图估计深度、点云、法线和相机信息。',
  },
  pixel_align: {
    title: '像素对齐',
    description: '对齐 SAM mask 像素和 MoGe 点云/深度像素。',
  },
  ground_solve: {
    title: '地面平面求解',
    description: '从点云和区域 mask 中拟合地面平面与坐标系。',
  },
  object_solve: {
    title: '对象空间求解',
    description: '估计对象落点、底部中心、尺寸、朝向和置信度。',
  },
  group_solve: {
    title: '阵列/组关系求解',
    description: '识别同类对象的排布、网格、行列或组关系。',
  },
  export: {
    title: '导出最终结果',
    description: '汇总空间结果，生成 SpatialSceneObservation JSON。',
  },
  evaluate: {
    title: '结果评估',
    description: '生成基础质量指标，辅助人工审核和后续调参。',
  },
}

export const STATUS_LABELS: Record<InferredStageStatus, string> = {
  pending: '未开始',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

export const RUNNING_TASK_STATUSES = new Set([
  'QUEUED',
  'RUNNING',
  'BUILDING_SAM_TASKS',
  'SEGMENTING',
  'MASK_POSTPROCESSING',
  'GEOMETRY_ESTIMATING',
  'PIXEL_ALIGNING',
  'GROUND_SOLVING',
  'OBJECT_SOLVING',
  'GROUP_SOLVING',
  'EXPORTING',
  'EVALUATING',
])

export function stageLabel(stage: string): string {
  return stage.replace(/_/g, ' ')
}

export function stageDisplay(stage: string): StageDisplayMeta {
  return STAGE_DISPLAY[stage as PipelineStageName] ?? {
    title: stageLabel(stage),
    description: '后端阶段。',
  }
}

export function stageResultPath(stage: string): string {
  return `stages/${stage}_attempt_1.json`
}

export function inferStageStatus(
  stage: string,
  task: TaskStatusResponse | null,
  artifacts: ArtifactItem[],
): InferredStageStatus {
  if (!task) {
    return 'pending'
  }
  if (task.status === 'COMPLETED') {
    return 'completed'
  }
  if (task.status === 'FAILED' && task.currentStage === stage) {
    return 'failed'
  }
  if (task.currentStage === stage) {
    return 'running'
  }
  if (artifacts.some((artifact) => artifact.relativePath === stageResultPath(stage))) {
    return 'completed'
  }
  return 'pending'
}


