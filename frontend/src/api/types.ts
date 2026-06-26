export interface CreateTaskResponse {
  taskId: string
  status: string
  taskDir: string
}

export interface TaskStatusResponse {
  taskId: string
  status: string
  currentStage: string | null
  domain: string
  inputImagePath: string
  createdAt: string
  updatedAt: string
  errorCode?: string | null
  errorMessage?: string | null
}

export interface SemanticImportResponse {
  taskId: string
  status: string
  validation: Record<string, unknown>
}

export interface ArtifactItem {
  id: number
  stageName: string
  artifactType: string
  relativePath: string
  mimeType?: string | null
  sizeBytes?: number | null
  createdAt: string
}

export interface ArtifactListResponse {
  taskId: string
  artifacts: ArtifactItem[]
}

export interface StageResult {
  stage: string
  status: string
  started_at?: string
  finished_at?: string
  duration_ms?: number
  outputs?: Record<string, string>
  metrics?: Record<string, number | string>
  warnings?: string[]
  error?: {
    code: string
    message: string
    traceback_path?: string | null
  } | null
}

export type CorrectionType = 'ground-points' | 'scale-anchor' | 'object-transform'

export type ArtifactPreviewKind = 'empty' | 'image' | 'json' | 'text' | 'binary' | 'directory' | 'error'

export interface ArtifactPreview {
  kind: ArtifactPreviewKind
  title: string
  content?: string
  objectUrl?: string
  error?: string
}
