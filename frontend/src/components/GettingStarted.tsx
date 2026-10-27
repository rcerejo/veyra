interface Props { onNavigate: (page: string) => void }

export function GettingStarted({ onNavigate }: Props) {
  return <section aria-labelledby="getting-started" className="mb-6 rounded-2xl border border-accent/20 bg-accent/[0.04] p-5">
    <h2 id="getting-started" className="font-medium text-slate-100">Start with a database, then ask a question</h2>
    <ol className="mt-3 list-inside list-decimal space-y-2 text-sm leading-6 text-slate-400">
      <li>Try the included synthetic demo, or upload a SQLite copy in Settings.</li>
      <li>Review table names, columns and relationships in Schema Explorer.</li>
      <li>Start with a row count. Add a field, filter and explicit date window; review the interpretation and SQL.</li>
    </ol>
    <p className="mt-3 text-xs leading-5 text-slate-400">Custom databases support bounded read-only questions. Retention, funnels and experiments require compatible product tables; unfamiliar business definitions are not inferred automatically. A clarification is not an answer or a zero-result analysis.</p>
    <div className="mt-4 flex flex-wrap gap-3"><button onClick={() => onNavigate('Settings')} className="rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-ink">Connect your data</button><button onClick={() => onNavigate('Schema Explorer')} className="rounded-lg border border-white/15 px-3 py-2 text-xs text-slate-200">Review schema</button></div>
  </section>
}
