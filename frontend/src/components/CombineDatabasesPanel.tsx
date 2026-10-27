import { useState } from 'react'
import { api } from '../services/api'
import type { CombinedDatabase, CombineRequest, DatabaseInfo, SourceSchema } from '../types/api'
import { validateCombination } from './combineValidation'

interface Source { name: string; alias: string; schema?: SourceSchema; error?: string }
interface Link { child: string; parent: string; pairs: { child: string; parent: string }[] }
interface Props { databases: DatabaseInfo[]; disabled: boolean; onCreated: () => Promise<void>; onActivate: (name: string) => Promise<void>; onWorkingChange?: (working: boolean) => void }
const control = 'w-full rounded-lg border border-white/15 bg-ink px-3 py-2 text-sm text-slate-200 disabled:opacity-40'

export function CombineDatabasesPanel({ databases, disabled, onCreated, onActivate, onWorkingChange }: Props) {
  const [sources, setSources] = useState<Source[]>([])
  const [links, setLinks] = useState<Link[]>([])
  const [name, setName] = useState('combined-workspace')
  const [approved, setApproved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<CombinedDatabase | null>(null)
  const connected = databases.some(database => database.name === result?.database.name && database.active)
  const blocked = disabled || busy
  const schemas = Object.fromEntries(sources.filter(s => s.schema).map(s => [s.alias, s.schema!]))
  const tables = sources.flatMap(s => (s.schema?.tables ?? []).map(t => ({ source: s.alias, table: t.name, columns: t.columns })))
  const decode = (value: string): [string, string] => value ? JSON.parse(value) as [string, string] : ['', '']
  const configuration: CombineRequest = { name, sources: sources.map(s => ({ name: s.name, alias: s.alias })), relationships: links.map(link => {
    const [child_source, child_table] = decode(link.child); const [parent_source, parent_table] = decode(link.parent)
    return { child_source, child_table, child_columns: link.pairs.map(p => p.child), parent_source, parent_table, parent_columns: link.pairs.map(p => p.parent) }
  }) }
  const errors = validateCombination(configuration, schemas)

  function selectSource(database: DatabaseInfo) {
    setApproved(false); setLinks([]); setError('')
    if (sources.some(s => s.name === database.name)) { setSources(sources.filter(s => s.name !== database.name)); return }
    if (sources.length >= 5) return
    const fromName = database.name.split('/').pop()!.replace(/\.(db|sqlite3?)$/i, '').toLowerCase().replace(/[^a-z]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 24)
    const alias = /^[a-z][a-z0-9_]{0,23}$/.test(fromName) && !sources.some(s => s.alias === fromName) ? fromName : ['source_a', 'source_b', 'source_c', 'source_d', 'source_e', 'source_f'].find(value => !sources.some(s => s.alias === value))!
    setSources([...sources, { name: database.name, alias }])
    api.sourceSchema(database.name).then(schema => setSources(current => current.map(s => s.name === database.name ? { ...s, schema } : s)))
      .catch(cause => setSources(current => current.map(s => s.name === database.name ? { ...s, error: cause instanceof Error ? cause.message : 'Unable to inspect source' } : s)))
  }
  function updateLink(index: number, value: Link) { setApproved(false); setLinks(links.map((link, i) => i === index ? value : link)) }
  async function create() {
    if (errors.length || !approved) return
    setBusy(true); onWorkingChange?.(true); setError(''); setResult(null)
    try { const created = await api.combineDatabases(configuration); setResult(created); await onCreated() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to combine databases') }
    finally { setBusy(false); onWorkingChange?.(false) }
  }
  async function connect() {
    if (!result) return
    setBusy(true); onWorkingChange?.(true); setError('')
    try { await onActivate(result.database.name) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to connect snapshot') }
    finally { setBusy(false); onWorkingChange?.(false) }
  }

  return <section className="mt-6 rounded-2xl border border-white/10 bg-panel p-5" aria-labelledby="combine-title">
    <h2 id="combine-title" className="font-medium">Combine uploaded databases</h2>
    <p className="mt-2 text-sm leading-6 text-slate-400">Select 2–5 SQLite sources and define their join keys. VEYRA creates a new, read-only-queryable snapshot. Originals stay unchanged. This is not a live connection: combine again after source updates.</p>
    <fieldset disabled={blocked} className="mt-4 space-y-3">
      <legend className="text-sm text-slate-300">1. Select sources and name their table prefixes</legend>
      <div className="max-h-56 overflow-y-auto rounded-lg border border-white/10 p-3">
        {databases.map(database => <label key={database.name} className="flex items-start gap-2 py-1 text-xs text-slate-300"><input type="checkbox" checked={sources.some(s => s.name === database.name)} disabled={!sources.some(s => s.name === database.name) && sources.length >= 5} onChange={() => selectSource(database)}/><span className="break-all">{database.name}</span></label>)}
      </div>
      {sources.map(source => <div key={source.name} className="rounded-lg bg-white/[0.03] p-3">
        <label className="block text-xs text-slate-400">Prefix for {source.name}<input className={`${control} mt-1`} value={source.alias} maxLength={24} onChange={event => { setApproved(false); setLinks([]); setSources(sources.map(s => s.name === source.name ? { ...s, alias: event.target.value } : s)) }}/></label>
        {source.error ? <p role="alert" className="mt-2 text-xs text-red-300">{source.error}</p> : !source.schema ? <p className="mt-2 text-xs text-slate-500">Inspecting schema…</p> : <>
          <p className="mt-2 text-xs text-slate-500">{source.schema.tables.map(t => `${source.alias}__${t.name}`).join(', ')}</p>
          {source.schema.ignored_objects.length > 0 && <p className="mt-1 text-xs text-amber-200">Views/triggers not copied: {source.schema.ignored_objects.join(', ')}</p>}
        </>}
      </div>)}
      <h3 className="pt-3 text-sm text-slate-300">2. Define child → unique parent relationships</h3>
      <p className="text-xs text-slate-500">Use the fact’s actual identity/workspace key. Similar names are not proof of a relationship. Many-to-many data needs a bridge table, not an invented foreign key.</p>
      {links.map((link, index) => {
        const child = tables.find(t => JSON.stringify([t.source, t.table]) === link.child)
        const parent = tables.find(t => JSON.stringify([t.source, t.table]) === link.parent)
        return <div key={index} className="space-y-3 rounded-xl border border-white/10 p-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {(['child', 'parent'] as const).map(side => <label key={side} className="text-xs text-slate-400">{side === 'child' ? 'Child / many-side table' : 'Parent / one-side table'}<select className={`${control} mt-1`} value={link[side]} onChange={event => updateLink(index, { ...link, [side]: event.target.value, pairs: [{ child: '', parent: '' }] })}><option value="">Choose table</option>{tables.map(t => <option key={JSON.stringify([t.source, t.table])} value={JSON.stringify([t.source, t.table])}>{t.source}__{t.table}</option>)}</select></label>)}
          </div>
          {link.pairs.map((pair, pairIndex) => <div key={pairIndex} className="flex items-center gap-2">
            {(['child', 'parent'] as const).map(side => <select key={side} aria-label={`Relationship ${index + 1} ${side} column ${pairIndex + 1}`} className={control} value={pair[side]} onChange={event => updateLink(index, { ...link, pairs: link.pairs.map((p, i) => i === pairIndex ? { ...p, [side]: event.target.value } : p) })}><option value="">{side} column</option>{(side === 'child' ? child : parent)?.columns.map(c => <option key={c.name} value={c.name}>{c.name} ({c.data_type})</option>)}</select>)}
            {link.pairs.length > 1 && <button type="button" aria-label={`Remove key pair ${pairIndex + 1}`} onClick={() => updateLink(index, { ...link, pairs: link.pairs.filter((_, i) => i !== pairIndex) })}>×</button>}
          </div>)}
          <div className="flex gap-4 text-xs text-accent"><button type="button" disabled={link.pairs.length >= 4} onClick={() => updateLink(index, { ...link, pairs: [...link.pairs, { child: '', parent: '' }] })}>Add composite-key pair</button><button type="button" onClick={() => { setApproved(false); setLinks(links.filter((_, i) => i !== index)) }}>Remove relationship</button></div>
        </div>
      })}
      <button type="button" className="text-sm text-accent disabled:opacity-40" disabled={sources.length < 2 || sources.some(s => !s.schema) || links.length >= 32} onClick={() => { setApproved(false); setLinks([...links, { child: '', parent: '', pairs: [{ child: '', parent: '' }] }]) }}>+ Add cross-source relationship</button>
      <label className="block pt-3 text-xs text-slate-400">3. Snapshot name<input className={`${control} mt-1`} value={name} maxLength={40} onChange={event => { setName(event.target.value); setApproved(false) }}/></label>
      <p className="text-xs text-slate-500">Limits: 100 MB per source, 200 MB source snapshots total, 100 MB output, 60 tables, 500,000 rows, 30-second build budget. Values/PKs/unique keys/FKs are copied; views, triggers, defaults/checks, non-unique indexes and semantic metric definitions are not.</p>
      {sources.length > 0 && errors.length > 0 && <ul className="list-inside list-disc text-xs text-amber-200">{errors.map(message => <li key={message}>{message}</li>)}</ul>}
      <label className="flex items-start gap-2 text-xs leading-5 text-slate-300"><input type="checkbox" className="mt-1" checked={approved} onChange={event => setApproved(event.target.checked)}/>I confirm these key relationships represent my data. This creates a static copy, not a live joined connection or approved business metric definitions.</label>
      <button type="button" disabled={!approved || errors.length > 0} onClick={() => void create()} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-ink disabled:opacity-40">{busy ? 'Working…' : 'Create combined dataset'}</button>
    </fieldset>
    {error && <p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
    {result && <div className="mt-4 rounded-xl border border-emerald-400/20 p-4">
      <h3 className="text-sm text-emerald-300">Snapshot created. Sources unchanged.</h3>
      <p className="mt-1 break-all text-xs text-slate-400">{result.database.name}</p>
      <p className="mt-2 text-xs text-slate-400">{Object.keys(result.provenance.row_counts).length} tables, {Object.values(result.provenance.row_counts).reduce((a, b) => a + b, 0).toLocaleString()} rows. Created {result.provenance.created_utc}.</p>
      <details className="mt-3 text-xs text-slate-400"><summary>Source fingerprints, mappings and snapshot limitations</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all">{JSON.stringify(result.provenance, null, 2)}</pre></details>
      <button type="button" disabled={blocked || connected} onClick={() => void connect()} className="mt-3 rounded-lg border border-emerald-400/30 px-3 py-2 text-sm text-emerald-300 disabled:opacity-40">{connected ? 'Connected—ready in Ask Veyra' : 'Connect combined dataset'}</button>
    </div>}
  </section>
}
