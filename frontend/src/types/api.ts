export interface Health {
  status: 'ok' | 'degraded'
  database: { connected: boolean; name: string }
  ollama: { available: boolean; model: string }
}

export interface QueryResult {
  question: string
  plan: { intent: string; metric: string | null; dimensions: string[]; relevant_tables: string[] }
  sql: string
  columns: string[]
  rows: Record<string, unknown>[]
  metadata: { source: 'deterministic' | 'ollama'; duration_ms: number; row_count: number; truncated: boolean; model: string | null }
  explanation: string
}

export interface Clarification {
  status: 'clarification_required'
  question: string
  message: string
  suggestions: string[]
}

