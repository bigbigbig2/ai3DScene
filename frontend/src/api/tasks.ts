import { http } from './http'
import type { CreateTaskResponse, TaskStatusResponse } from './types'

export async function createTask(
  file: File,
  domain: string,
  semanticMode: string,
): Promise<CreateTaskResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('domain', domain)
  form.append('semantic_mode', semanticMode)
  const response = await http.post<CreateTaskResponse>('/api/v1/tasks', form)
  return response.data
}

export async function getTask(taskId: string): Promise<TaskStatusResponse> {
  const response = await http.get<TaskStatusResponse>(`/api/v1/tasks/${taskId}`)
  return response.data
}

export async function runTask(taskId: string): Promise<TaskStatusResponse> {
  const response = await http.post<TaskStatusResponse>(`/api/v1/tasks/${taskId}/run`)
  return response.data
}

export async function rerunTask(taskId: string, fromStage: string): Promise<TaskStatusResponse> {
  const response = await http.post<TaskStatusResponse>(`/api/v1/tasks/${taskId}/rerun`, {
    fromStage,
  })
  return response.data
}
