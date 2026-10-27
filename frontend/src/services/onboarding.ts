import type { SchemaTable } from '../types/api'

// Do not turn sampled customer values or arbitrary metadata into prompt text.
export function starterQuestions(tables: SchemaTable[]): string[] {
  return tables.filter(table => /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(table.name))
    .slice(0, 3).map(table => `Count ${table.name}`)
}

export function uploadProblem(file: Pick<File, 'name' | 'size'>): string | null {
  if (!/\.(db|sqlite|sqlite3)$/i.test(file.name)) return 'Choose a SQLite database (.db, .sqlite or .sqlite3), not a CSV or spreadsheet.'
  if (!file.size) return 'This file is empty. Export a populated SQLite database and try again.'
  if (file.size > 100 * 1024 * 1024) return 'This file exceeds the 100 MB upload limit. Use a smaller SQLite export.'
  return null
}
