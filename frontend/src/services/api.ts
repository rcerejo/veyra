import type { ActivityMetrics, Clarification, CombinedDatabase, CombineRequest, DatabaseInfo, Health, MetricDefinition, QueryResult, SchemaResponse, SnapshotProvenance, SourceSchema } from '../types/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(path, init) }
  catch { throw new Error('Cannot reach VEYRA. Keep the launcher terminal open, check your connection, then try again.') }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    const fallback = response.status >= 500 ? 'The server could not complete this request. Check the launcher terminal and try again.' : 'Invalid request. Check the selected sources and relationship fields, question length, or date inputs.'
    throw new Error(typeof body?.detail === 'string' && body.detail ? body.detail : fallback)
  }
  try { return await response.json() as T }
  catch { throw new Error('VEYRA returned an unreadable response. Check that the frontend is connected to the VEYRA backend, then retry.') }
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
  sourceSchema: (name: string) => request<SourceSchema>(`/api/databases/schema?${new URLSearchParams({ name })}`),
  combineDatabases: (configuration: CombineRequest) => request<CombinedDatabase>('/api/databases/combine', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(configuration),
  }),
  snapshotProvenance: (name: string) => request<{ provenance: SnapshotProvenance; provenance_sha256: string }>(`/api/databases/provenance?${new URLSearchParams({ name })}`),
  activateDatabase: (name: string) => request<DatabaseInfo>('/api/databases/activate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
  }),
  uploadDatabase: async (file: File): Promise<DatabaseInfo> => {
    return request<DatabaseInfo>(`/api/databases/upload?filename=${encodeURIComponent(file.name)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file,
    })
  },
  ask: (question: string) => request<QueryResult | Clarification>('/api/query', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }),
  }),
}

