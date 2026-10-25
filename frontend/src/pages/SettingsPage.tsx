import { useEffect, useRef, useState } from 'react'
import { Check, Database, HardDriveUpload, LoaderCircle } from 'lucide-react'
import { api } from '../services/api'
import type { DatabaseInfo } from '../types/api'

interface Props { onDatabaseChanged: () => void }

export function SettingsPage({ onDatabaseChanged }: Props) {
  const [databases, setDatabases] = useState<DatabaseInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const input = useRef<HTMLInputElement>(null)

  async function refresh() {
    setLoading(true)
    try { setDatabases((await api.databases()).databases); setError('') }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load databases') }
    finally { setLoading(false) }
  }

  useEffect(() => { void refresh() }, [])

  async function activate(name: string) {
    setBusy(name); setError('')
    try { await api.activateDatabase(name); await refresh(); onDatabaseChanged() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to activate database') }
    finally { setBusy('') }
  }

  async function upload(file?: File) {
    if (!file) return
    setBusy('upload'); setError('')
    try { await api.uploadDatabase(file); await refresh(); onDatabaseChanged() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to upload database') }
    finally { setBusy(''); if (input.current) input.current.value = '' }
  }

  return <main className="mx-auto max-w-5xl px-6 py-10 lg:px-10">
    <div className="mb-8"><div className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">Workspace settings</div><h1 className="mt-3 text-3xl font-semibold tracking-tight">Connected database</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">Upload or switch between local SQLite databases. Files are validated and stored inside VEYRA’s local datasets directory.</p></div>
    <section className="rounded-2xl border border-white/10 bg-panel p-5">
      <div className="flex items-center justify-between gap-4"><div><h2 className="font-medium">SQLite sources</h2><p className="mt-1 text-xs text-slate-500">Maximum upload size: 100 MB</p></div><button onClick={() => input.current?.click()} disabled={Boolean(busy)} className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-ink disabled:opacity-40"><HardDriveUpload size={16}/>{busy === 'upload' ? 'Uploading…' : 'Upload database'}</button><input ref={input} className="hidden" type="file" accept=".db,.sqlite,.sqlite3" onChange={event => void upload(event.target.files?.[0])}/></div>
      {error && <div role="alert" className="mt-4 rounded-lg border border-red-400/20 bg-red-400/[0.06] p-3 text-sm text-red-200">{error}</div>}
      <div className="mt-5 divide-y divide-white/[0.07] rounded-xl border border-white/[0.08]">
        {loading ? <div className="flex items-center gap-2 p-4 text-sm text-slate-500"><LoaderCircle className="animate-spin" size={16}/>Loading databases…</div> : databases.length === 0 ? <div className="p-5 text-sm text-slate-500">No SQLite databases found.</div> : databases.map(database => <div key={database.name} className="flex items-center justify-between gap-4 p-4"><div className="flex min-w-0 items-center gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white/[0.04] text-accent"><Database size={17}/></span><div className="min-w-0"><div className="truncate text-sm text-slate-200">{database.name}</div><div className="mt-0.5 text-xs text-slate-600">{formatBytes(database.size_bytes)}</div></div></div>{database.active ? <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400"><Check size={14}/>Connected</span> : <button onClick={() => void activate(database.name)} disabled={Boolean(busy)} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/[0.04] disabled:opacity-40">{busy === database.name ? 'Connecting…' : 'Connect'}</button>}</div>)}
      </div>
    </section>
  </main>
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
