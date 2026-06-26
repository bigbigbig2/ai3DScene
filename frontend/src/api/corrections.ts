import { http } from './http'
import type { CorrectionType } from './types'

export async function submitCorrection(
  taskId: string,
  type: CorrectionType,
  payload: unknown,
): Promise<unknown> {
  const response = await http.post(`/api/v1/tasks/${taskId}/corrections/${type}`, payload)
  return response.data
}
