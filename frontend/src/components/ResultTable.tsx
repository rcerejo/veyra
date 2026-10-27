interface Props { columns: string[]; rows: Record<string, unknown>[] }

export function ResultTable({ columns, rows }: Props) {
  function download() {
    const escape = (value: unknown) => {
      let text=String(value ?? '')
      if (/^[=+@\-\t\r]/.test(text)) text="'"+text
      return '"'+text.replaceAll('"','""')+'"'
    }
    const csv=[columns.map(escape).join(','),...rows.map(row=>columns.map(column=>escape(row[column])).join(','))].join('\r\n')
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}))
    const link=document.createElement('a');link.href=url;link.download='veyra-results.csv';link.click();URL.revokeObjectURL(url)
  }
  return <div className="overflow-hidden rounded-xl border border-white/10">
    <div className="flex justify-end bg-white/[0.02] p-2"><button onClick={download} className="rounded border border-white/10 px-3 py-1 text-xs text-slate-400">Download CSV</button></div>
    <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <thead className="bg-white/[0.04] text-[11px] uppercase tracking-[0.12em] text-slate-400"><tr>
        {columns.map(column => <th className="px-4 py-3 font-medium" key={column}>{column.replaceAll('_', ' ')}</th>)}
      </tr></thead>
      <tbody className="divide-y divide-white/[0.06]">{rows.length === 0 && <tr><td colSpan={Math.max(columns.length, 1)} className="px-4 py-6 text-sm text-slate-400">No rows matched this query. Check the filters and date window; this is not a connection error.</td></tr>}{rows.map((row, index) => <tr className="text-slate-200 transition hover:bg-white/[0.025]" key={index}>
        {columns.map(column => <td className="whitespace-nowrap px-4 py-3 font-mono text-xs" key={column}>{typeof row[column] === 'number' ? new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(row[column] as number) : String(row[column] ?? '—')}</td>)}
      </tr>)}</tbody>
    </table></div>
  </div>
}

