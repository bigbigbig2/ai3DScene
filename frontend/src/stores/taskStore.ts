import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getArtifactBlob, getArtifactText, getResult, listArtifacts } from '../api/artifacts'
import { submitCorrection as postCorrection } from '../api/corrections'
import { importSemanticProposal as postSemanticProposal } from '../api/semantic'
import { createTask as postTask, getTask, rerunTask, runTask } from '../api/tasks'
import type {
  ArtifactItem,
  ArtifactPreview,
  CorrectionType,
  StageResult,
  TaskStatusResponse,
} from '../api/types'
import { RUNNING_TASK_STATUSES, stageResultPath } from '../constants/pipeline'
import { defaultSemanticProposalText } from '../constants/semanticTemplates'

const RECENT_TASKS_KEY = 'scene-spatial-debug-recent-tasks'

function loadRecentTasks(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_TASKS_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function rememberTask(taskId: string, recentTaskIds: string[]) {
  const next = [taskId, ...recentTaskIds.filter((value) => value !== taskId)].slice(0, 10)
  localStorage.setItem(RECENT_TASKS_KEY, JSON.stringify(next))
  return next
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

async function blobToPreview(artifact: ArtifactItem, blob: Blob): Promise<ArtifactPreview> {
  const title = artifact.relativePath
  if (artifact.artifactType === 'MASK' && !artifact.mimeType) {
    return { kind: 'directory', title, content: '这是目录型阶段产物，当前前端不直接展开目录。可在服务器任务目录中查看具体 mask 文件。' }
  }
  if (artifact.mimeType?.startsWith('image/')) {
    return { kind: 'image', title, objectUrl: URL.createObjectURL(blob) }
  }
  if (artifact.mimeType === 'application/json' || artifact.relativePath.endsWith('.json')) {
    const text = await blob.text()
    try {
      return { kind: 'json', title, content: prettyJson(JSON.parse(text)) }
    } catch {
      return { kind: 'text', title, content: text }
    }
  }
  if (artifact.mimeType?.startsWith('text/') || artifact.relativePath.endsWith('.log')) {
    return { kind: 'text', title, content: await blob.text() }
  }
  return {
    kind: 'binary',
    title,
    content: `二进制阶段产物（${artifact.artifactType}）。当前前端暂不解析，可在服务器上进一步查看。`,
  }
}

export const useTaskStore = defineStore('task', () => {
  const currentTaskId = ref<string>('')
  const taskStatus = ref<TaskStatusResponse | null>(null)
  const artifacts = ref<ArtifactItem[]>([])
  const selectedArtifactId = ref<number | null>(null)
  const selectedStage = ref<string>('build_sam_tasks')
  const selectedArtifactPreview = ref<ArtifactPreview>({ kind: 'empty', title: '未选择阶段产物' })
  const semanticProposalDraft = ref(defaultSemanticProposalText())
  const correctionPayloadDraft = ref('{\n  "note": "debug correction payload"\n}')
  const resultJson = ref<string>('')
  const stageResultJson = ref<string>('')
  const recentTaskIds = ref<string[]>(loadRecentTasks())
  const autoRefresh = ref(true)
  const loading = ref(false)
  const artifactLoading = ref(false)
  const error = ref<string | null>(null)
  const message = ref<string | null>(null)

  let taskPollTimer: ReturnType<typeof window.setInterval> | null = null
  let artifactPollTimer: ReturnType<typeof window.setInterval> | null = null

  const isTaskActive = computed(() => {
    return taskStatus.value ? RUNNING_TASK_STATUSES.has(taskStatus.value.status) : false
  })

  const selectedArtifact = computed(() => {
    return artifacts.value.find((artifact) => artifact.id === selectedArtifactId.value) ?? null
  })

  const artifactGroups = computed(() => {
    return {
      all: artifacts.value,
      input: artifacts.value.filter((item) => item.relativePath.startsWith('input/')),
      semantic: artifacts.value.filter((item) => item.relativePath.startsWith('semantic/')),
      detection: artifacts.value.filter((item) => item.relativePath.startsWith('detection/')),
      geometry: artifacts.value.filter((item) => item.relativePath.startsWith('geometry/')),
      spatial: artifacts.value.filter((item) => item.relativePath.startsWith('spatial/')),
      evaluation: artifacts.value.filter((item) => item.relativePath.startsWith('evaluation/')),
      logs: artifacts.value.filter((item) => item.relativePath.startsWith('logs/')),
    }
  })

  function setError(caught: unknown) {
    error.value = caught instanceof Error ? caught.message : String(caught)
  }

  function clearNotices() {
    error.value = null
    message.value = null
  }

  function setCurrentTaskId(taskId: string) {
    currentTaskId.value = taskId.trim()
    if (currentTaskId.value) {
      recentTaskIds.value = rememberTask(currentTaskId.value, recentTaskIds.value)
    }
  }

  async function create(file: File, domain: string, semanticMode: string) {
    clearNotices()
    loading.value = true
    try {
      const response = await postTask(file, domain, semanticMode)
      setCurrentTaskId(response.taskId)
      taskStatus.value = {
        taskId: response.taskId,
        status: response.status,
        currentStage: null,
        domain,
        inputImagePath: '',
        createdAt: '',
        updatedAt: '',
      }
      message.value = `已创建任务 ${response.taskId}`
      await refreshAll()
      ensurePolling()
    } catch (caught) {
      setError(caught)
    } finally {
      loading.value = false
    }
  }

  async function loadTask(taskId = currentTaskId.value) {
    if (!taskId) return
    clearNotices()
    try {
      setCurrentTaskId(taskId)
      taskStatus.value = await getTask(currentTaskId.value)
    } catch (caught) {
      setError(caught)
    }
  }

  async function loadArtifacts() {
    if (!currentTaskId.value) return
    try {
      artifacts.value = (await listArtifacts(currentTaskId.value)).artifacts
    } catch (caught) {
      setError(caught)
    }
  }

  async function refreshAll() {
    await loadTask()
    await loadArtifacts()
    await loadSelectedStageResult()
  }

  async function runCurrentTask() {
    if (!currentTaskId.value) return
    clearNotices()
    loading.value = true
    try {
      taskStatus.value = await runTask(currentTaskId.value)
      message.value = '任务已入队，等待 Worker 执行'
      ensurePolling()
    } catch (caught) {
      setError(caught)
    } finally {
      loading.value = false
    }
  }

  async function rerunFrom(stage: string) {
    if (!currentTaskId.value) return
    clearNotices()
    loading.value = true
    try {
      taskStatus.value = await rerunTask(currentTaskId.value, stage)
      selectedStage.value = stage
      message.value = `已从 ${stage} 阶段重新入队`
      ensurePolling()
    } catch (caught) {
      setError(caught)
    } finally {
      loading.value = false
    }
  }

  async function importSemanticDraft() {
    if (!currentTaskId.value) return
    clearNotices()
    loading.value = true
    try {
      const proposal = JSON.parse(semanticProposalDraft.value)
      const response = await postSemanticProposal(currentTaskId.value, proposal)
      message.value = `语义提案已导入：${response.status}`
      await refreshAll()
    } catch (caught) {
      setError(caught)
    } finally {
      loading.value = false
    }
  }

  async function previewArtifact(artifact: ArtifactItem) {
    if (!currentTaskId.value) return
    selectedArtifactId.value = artifact.id
    artifactLoading.value = true
    if (selectedArtifactPreview.value.objectUrl) {
      URL.revokeObjectURL(selectedArtifactPreview.value.objectUrl)
    }
    selectedArtifactPreview.value = { kind: 'empty', title: artifact.relativePath }
    try {
      const blob = await getArtifactBlob(currentTaskId.value, artifact.id)
      selectedArtifactPreview.value = await blobToPreview(artifact, blob)
    } catch (caught) {
      selectedArtifactPreview.value = {
        kind: 'error',
        title: artifact.relativePath,
        error: caught instanceof Error ? caught.message : String(caught),
      }
    } finally {
      artifactLoading.value = false
    }
  }

  async function loadSelectedStageResult() {
    stageResultJson.value = ''
    if (!currentTaskId.value || !selectedStage.value) return
    const artifact = artifacts.value.find(
      (item) => item.relativePath === stageResultPath(selectedStage.value),
    )
    if (!artifact) return
    try {
      const text = await getArtifactText(currentTaskId.value, artifact.id)
      const parsed = JSON.parse(text) as StageResult
      stageResultJson.value = prettyJson(parsed)
    } catch (caught) {
      stageResultJson.value = caught instanceof Error ? caught.message : String(caught)
    }
  }

  async function loadResult() {
    if (!currentTaskId.value) return
    clearNotices()
    try {
      resultJson.value = prettyJson(await getResult(currentTaskId.value))
      message.value = '最终结果已读取'
      return
    } catch (caught) {
      const resultArtifact = artifacts.value.find(
        (artifact) => artifact.relativePath === 'spatial/spatial_scene_observation.json',
      )
      if (!resultArtifact) {
        resultJson.value = ''
        setError(caught)
        return
      }
      try {
        const text = await getArtifactText(currentTaskId.value, resultArtifact.id)
        resultJson.value = prettyJson(JSON.parse(text))
        message.value = '最终结果已从阶段产物读取'
      } catch {
        resultJson.value = ''
        setError(caught)
      }
    }
  }

  async function submitCorrection(type: CorrectionType) {
    if (!currentTaskId.value) return
    clearNotices()
    loading.value = true
    try {
      const payload = JSON.parse(correctionPayloadDraft.value)
      await postCorrection(currentTaskId.value, type, payload)
      message.value = `人工修正已提交：${type}`
      await refreshAll()
    } catch (caught) {
      setError(caught)
    } finally {
      loading.value = false
    }
  }

  function setSelectedStage(stage: string) {
    selectedStage.value = stage
    void loadSelectedStageResult()
  }

  function setSemanticTemplate() {
    semanticProposalDraft.value = defaultSemanticProposalText()
  }

  function ensurePolling() {
    stopPolling()
    if (!autoRefresh.value) return
    taskPollTimer = window.setInterval(() => {
      if (!currentTaskId.value) return
      void loadTask().then(() => {
        if (!isTaskActive.value) stopPolling()
      })
    }, 2000)
    artifactPollTimer = window.setInterval(() => {
      if (!currentTaskId.value) return
      void loadArtifacts().then(() => loadSelectedStageResult())
    }, 4000)
  }

  function stopPolling() {
    if (taskPollTimer) window.clearInterval(taskPollTimer)
    if (artifactPollTimer) window.clearInterval(artifactPollTimer)
    taskPollTimer = null
    artifactPollTimer = null
  }

  return {
    currentTaskId,
    taskStatus,
    artifacts,
    selectedArtifactId,
    selectedArtifact,
    selectedStage,
    selectedArtifactPreview,
    semanticProposalDraft,
    correctionPayloadDraft,
    resultJson,
    stageResultJson,
    recentTaskIds,
    autoRefresh,
    loading,
    artifactLoading,
    error,
    message,
    isTaskActive,
    artifactGroups,
    create,
    loadTask,
    loadArtifacts,
    refreshAll,
    runCurrentTask,
    rerunFrom,
    importSemanticDraft,
    previewArtifact,
    loadSelectedStageResult,
    loadResult,
    submitCorrection,
    setCurrentTaskId,
    setSelectedStage,
    setSemanticTemplate,
    ensurePolling,
    stopPolling,
  }
})
