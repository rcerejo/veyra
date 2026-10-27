import type { CombineRequest, SourceSchema } from '../types/api'

export function validateCombination(request: CombineRequest, schemas: Record<string, SourceSchema>): string[] {
  const errors: string[] = []
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,39}$/.test(request.name)) errors.push('Name: use 1–40 letters, numbers, hyphens or underscores.')
  if (request.sources.length < 2 || request.sources.length > 5) errors.push('Choose 2–5 sources.')
  if (new Set(request.sources.map(s => s.alias)).size !== request.sources.length) errors.push('Source aliases must be unique.')
  if (new Set(request.sources.map(s => s.name)).size !== request.sources.length) errors.push('Choose different source databases.')
  for (const source of request.sources) {
    if (!/^[a-z][a-z0-9_]{0,23}$/.test(source.alias)) errors.push('Aliases: use lowercase letters/numbers/underscores, starting with a letter, up to 24 characters.')
    if (!schemas[source.alias]) errors.push(`Wait for a supported schema for ${source.alias || source.name}.`)
  }
  if (!request.relationships.length || request.relationships.length > 32) errors.push('Add 1–32 explicit cross-source relationships.')
  const edges = new Map(request.sources.map(s => [s.alias, new Set<string>()]))
  const seenLinks = new Set<string>()
  for (const [index, link] of request.relationships.entries()) {
    const child = schemas[link.child_source]?.tables.find(t => t.name === link.child_table)
    const parent = schemas[link.parent_source]?.tables.find(t => t.name === link.parent_table)
    const label = `Relationship ${index + 1}: `
    if (!child || !parent || !edges.has(link.child_source) || !edges.has(link.parent_source) || link.child_source === link.parent_source) {
      errors.push(label + 'choose tables from two different selected sources.'); continue
    }
    if (!link.child_columns.length || link.child_columns.length > 4 || link.child_columns.length !== link.parent_columns.length
      || new Set(link.child_columns).size !== link.child_columns.length || new Set(link.parent_columns).size !== link.parent_columns.length
      || link.child_columns.some(c => !child.columns.some(col => col.name === c))
      || link.parent_columns.some(c => !parent.columns.some(col => col.name === c))) errors.push(label + 'choose 1–4 distinct, aligned column pairs.')
    if (!parent.unique_keys.some(key => JSON.stringify(key) === JSON.stringify(link.parent_columns))) errors.push(label + 'parent columns must match a declared primary/unique key in its key order.')
    const identity = JSON.stringify(link)
    if (seenLinks.has(identity)) errors.push(label + 'duplicates another mapping.')
    seenLinks.add(identity)
    edges.get(link.child_source)?.add(link.parent_source)
    edges.get(link.parent_source)?.add(link.child_source)
  }
  const visited = new Set<string>()
  const pending = request.sources[0] ? [request.sources[0].alias] : []
  while (pending.length) {
    const alias = pending.pop()!
    if (!visited.has(alias)) { visited.add(alias); pending.push(...(edges.get(alias) ?? [])) }
  }
  if (visited.size !== request.sources.length) errors.push('Connect every selected source through the relationship mappings.')
  return [...new Set(errors)]
}
