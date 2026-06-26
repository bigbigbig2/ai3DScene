import { http } from './http'

export async function pingHealth(): Promise<unknown> {
  const response = await http.get('/health')
  return response.data
}

export async function pingReady(): Promise<unknown> {
  const response = await http.get('/ready')
  return response.data
}
