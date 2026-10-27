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

export interface CombinedSource { name: string; alias: string }
export interface CombinedRelationship {
  child_source: string; child_table: string; child_columns: string[]
  parent_source: string; parent_table: string; parent_columns: string[]
}
export interface CombineRequest { name: string; sources: CombinedSource[]; relationships: CombinedRelationship[] }
export interface SourceSchema { name: string; tables: (SchemaTable & { unique_keys: string[][] })[]; ignored_objects: string[]; note: string }
export interface SnapshotProvenance {
  version: number; mode: 'combined_snapshot'; name: string; created_utc: string; dataset_sha256: string
  sources: { alias: string; name: string; snapshot_sha256: string; captured_utc: string; ignored_objects: string[] }[]
  table_mapping: { source: string; table: string; combined_table: string }[]
  relationships: CombinedRelationship[]; row_counts: Record<string, number>; limitations: string[]
}
export interface CombinedDatabase { database: DatabaseInfo; provenance: SnapshotProvenance; provenance_sha256: string }

export interface SchemaColumn {
  name: string
  data_type: string
  nullable: boolean
  primary_key: boolean
}

export interface SchemaTable {
  name: string
  columns: SchemaColumn[]
  foreign_keys: { column: string; target_table: string; target_column: string | null; constraint_id?: number; sequence?: number }[]
  sample_values: Record<string, unknown[]>
}

export interface SchemaResponse { tables: SchemaTable[] }

export interface PlanField { table: string; column: string }
export interface CompositionalPlan {
  version: 1
  entity: string
  measure: { function: 'count' | 'sum' | 'average'; field: PlanField | null; distinct: boolean } | null
  filters: { field: PlanField; operator: string; value: string | number | null }[]
  groupings: { field: PlanField; grain: 'day' | 'week' | null }[]
  dates: { field: PlanField; start: string | null; end: string | null; start_inclusive?: boolean; end_inclusive?: boolean; normalized?: boolean; resolution?: string | null }[]
  joins: { left_table: string; right_table: string; equalities: [PlanField, PlanField][]; constraint_id: number }[]
  existence?: { entity: string; correlations: [PlanField, PlanField][]; joins: CompositionalPlan['joins']; filters: CompositionalPlan['filters']; negated: boolean; dates?: CompositionalPlan['dates']; timestamps?: { left: PlanField; right: PlanField; operator: string; null_policy: 'exclude_missing_anchors' }[] }[]
  activity?: { source: string; identity: PlanField; entity_table: string; definition: string; timezone: 'UTC' } | null
  distinct: boolean
  ranking: { field: PlanField | null; descending: boolean }[]
  limit: number
  requested_operations: string[]
  unresolved_operations: string[]
}

export interface QueryResult {
  question: string
  plan: { intent: string; metric: string | null; dimensions: string[]; filters: Record<string, string | number | boolean>; time_range: string | null; relevant_tables: string[]; composition?: CompositionalPlan | null }
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

export interface ActivityPoint { period: string; active_users: number }

export interface ActivityMetrics {
  start: string
  end: string
  data_start: string
  data_through: string
  timezone: string
  daily: ActivityPoint[]
  weekly: ActivityPoint[]
  monthly: ActivityPoint[]
  summary: {
    latest_dau: number
    latest_wau: number
    latest_mau: number
    dau_mau_ratio: number | null
    sessions_per_user: number | null
    average_session_duration_seconds: number | null
  }
}

export interface MetricDefinition {
  key: string
  name: string
  description: string
  formula: string
  required_fields: string[]
}

