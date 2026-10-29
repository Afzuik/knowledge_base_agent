export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api${path}`, { signal })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json() as Promise<T>
}

import type { HealthResponse } from '../types'

export function getHealth(signal?: AbortSignal) {
  return getJson<HealthResponse>('/health', signal)
}
