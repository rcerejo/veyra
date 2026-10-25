export interface Health {
  status: 'ok' | 'degraded'
  database: { connected: boolean; name: string }
  ollama: { available: boolean; model: string }
}

export interface DatabaseInfo {
  name: string
  size_bytes: number
  active: boolean
}

export interface SchemaColumn {
  name: string
  data_type: string
  nullable: boolean
  primary_key: boolean
}

export interface SchemaTable {
  name: string
  columns: SchemaColumn[]
  foreign_keys: { column: string; target_table: string; target_column: string }[]
  sample_values: Record<string, unknown[]>
}

export interface SchemaResponse { tables: SchemaTable[] }

export interface QueryResult {
  question: string
  plan: { intent: string; metric: string | null; dimensions: string[]; filters: Record<string, string | number | boolean>; time_range: string | null; relevant_tables: string[] }
  sql: string
  columns: string[]
  rows: Record<string, unknown>[]
  metadata: { source: 'deterministic' | 'semantic' | 'ollama'; duration_ms: number; row_count: number; truncated: boolean; model: string | null; correction_attempts: number }
  explanation: string
}

export interface Clarification {
  status: 'clarification_required'
  question: string
  message: string
  suggestions: string[]
}

