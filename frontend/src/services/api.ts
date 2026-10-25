import type { ActivityMetrics, Clarification, DatabaseInfo, Health, MetricDefinition, QueryResult, SchemaResponse } from '../types/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? 'The request failed')
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/api/health'),
  schema: () => request<SchemaResponse>('/api/schema'),
  activityMetrics: (start?: string, end?: string) => {
    const params = new URLSearchParams()
    if (start) params.set('start', start)
    if (end) params.set('end', end)
    const suffix = params.size ? `?${params}` : ''
    return request<ActivityMetrics>(`/api/metrics/activity${suffix}`)
  },
  metricDefinitions: () => request<MetricDefinition[]>('/api/metrics/definitions'),
  databases: () => request<{ databases: DatabaseInfo[] }>('/api/databases'),
  activateDatabase: (name: string) => request<DatabaseInfo>('/api/databases/activate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
  }),
  uploadDatabase: async (file: File): Promise<DatabaseInfo> => {
    const response = await fetch(`/api/databases/upload?filename=${encodeURIComponent(file.name)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file,
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(body.detail ?? 'Database upload failed')
    }
    return response.json() as Promise<DatabaseInfo>
  },
  ask: (question: string) => request<QueryResult | Clarification>('/api/query', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }),
  }),
}

