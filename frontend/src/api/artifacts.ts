import { http } from './http'
import type { ArtifactListResponse } from './types'

export async function listArtifacts(taskId: string): Promise<ArtifactListResponse> {
  const response = await http.get<ArtifactListResponse>(`/api/v1/tasks/${taskId}/artifacts`)
  return response.data
}

export async function getArtifactBlob(taskId: string, artifactId: number): Promise<Blob> {
  const response = await http.get(`/api/v1/tasks/${taskId}/artifacts/${artifactId}`, {
    responseType: 'blob',
  })
  return response.data
}

export async function getArtifactText(taskId: string, artifactId: number): Promise<string> {
  const blob = await getArtifactBlob(taskId, artifactId)
  return await blob.text()
}

export async function getResult(taskId: string): Promise<unknown> {
  const response = await http.get(`/api/v1/tasks/${taskId}/result`)
  return response.data
}
