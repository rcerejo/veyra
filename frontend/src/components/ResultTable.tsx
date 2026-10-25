interface Props { columns: string[]; rows: Record<string, unknown>[] }

export function ResultTable({ columns, rows }: Props) {
  return <div className="overflow-hidden rounded-xl border border-white/10">
    <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <thead className="bg-white/[0.04] text-[11px] uppercase tracking-[0.12em] text-slate-400"><tr>
        {columns.map(column => <th className="px-4 py-3 font-medium" key={column}>{column.replaceAll('_', ' ')}</th>)}
      </tr></thead>
      <tbody className="divide-y divide-white/[0.06]">{rows.map((row, index) => <tr className="text-slate-200 transition hover:bg-white/[0.025]" key={index}>
        {columns.map(column => <td className="whitespace-nowrap px-4 py-3 font-mono text-xs" key={column}>{String(row[column] ?? '—')}</td>)}
      </tr>)}</tbody>
    </table></div>
  </div>
}

