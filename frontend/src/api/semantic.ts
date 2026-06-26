import { http } from './http'
import type { SemanticImportResponse } from './types'

export async function importSemanticProposal(
  taskId: string,
  proposal: unknown,
): Promise<SemanticImportResponse> {
  const response = await http.post<SemanticImportResponse>(
    `/api/v1/tasks/${taskId}/semantic-proposal`,
    proposal,
  )
  return response.data
}
