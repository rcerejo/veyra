import { useEffect, useState } from 'react'
import { KeyRound, Link2, LoaderCircle, Table2 } from 'lucide-react'
import { api } from '../services/api'
import type { SchemaTable } from '../types/api'

export function SchemaExplorer() {
  const [tables, setTables] = useState<SchemaTable[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => { api.schema().then(result => setTables(result.tables)).catch(cause => setError(cause instanceof Error ? cause.message : 'Unable to inspect schema')).finally(() => setLoading(false)) }, [])
  return <main className="mx-auto max-w-6xl px-6 py-10 lg:px-10"><div className="mb-8"><div className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">Database intelligence</div><h1 className="mt-3 text-3xl font-semibold tracking-tight">Schema Explorer</h1><p className="mt-3 text-sm text-slate-400">Discovered structure, explicit relationships, and bounded categorical samples from the active database.</p></div>
    {loading ? <div className="flex items-center gap-2 text-sm text-slate-500"><LoaderCircle className="animate-spin" size={17}/>Inspecting schema…</div> : error ? <div className="rounded-xl border border-red-400/20 bg-red-400/[0.06] p-4 text-sm text-red-200">{error}</div> : <div className="grid gap-4 lg:grid-cols-2">{tables.map(table => <section key={table.name} className="rounded-2xl border border-white/10 bg-panel p-5"><div className="mb-4 flex items-center gap-2"><Table2 size={17} className="text-accent"/><h2 className="font-mono text-sm font-medium text-slate-100">{table.name}</h2><span className="ml-auto text-xs text-slate-600">{table.columns.length} columns</span></div><div className="space-y-2">{table.columns.map(column => <div key={column.name} className="rounded-lg bg-white/[0.025] px-3 py-2"><div className="flex items-center gap-2 text-xs"><span className="font-mono text-slate-200">{column.name}</span>{column.primary_key && <KeyRound size={12} className="text-amber-400"/>}<span className="ml-auto font-mono text-slate-600">{column.data_type || 'UNKNOWN'}</span></div>{table.sample_values[column.name] && <div className="mt-2 flex flex-wrap gap-1.5">{table.sample_values[column.name].map(value => <span key={String(value)} className="rounded bg-accent/[0.08] px-2 py-1 font-mono text-[10px] text-accent">{String(value)}</span>)}</div>}</div>)}</div>{table.foreign_keys.length > 0 && <div className="mt-4 border-t border-white/[0.07] pt-3">{table.foreign_keys.map(key => <div key={`${key.column}-${key.target_table}`} className="flex items-center gap-2 text-xs text-slate-500"><Link2 size={12}/><span className="font-mono">{key.column} → {key.target_table}.{key.target_column}</span></div>)}</div>}</section>)}</div>}
  </main>
}
