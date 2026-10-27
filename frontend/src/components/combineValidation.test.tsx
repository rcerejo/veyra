import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { validateCombination } from './combineValidation'
import { CombineDatabasesPanel } from './CombineDatabasesPanel'
import type { CombineRequest, SourceSchema } from '../types/api'

const column = (name: string) => ({ name, data_type: 'INTEGER', nullable: true, primary_key: false })
const schemas: Record<string, SourceSchema> = {
  crm: { name: 'crm.db', ignored_objects: [], note: '', tables: [{ name: 'people', columns: [column('id'), column('namespace')], foreign_keys: [], sample_values: {}, unique_keys: [['id'], ['namespace', 'id']] }] },
  product: { name: 'product.db', ignored_objects: [], note: '', tables: [{ name: 'events', columns: [column('actor_id'), column('namespace')], foreign_keys: [], sample_values: {}, unique_keys: [] }] },
}
const request = (): CombineRequest => ({ name: 'demo', sources: [{ name: 'crm.db', alias: 'crm' }, { name: 'product.db', alias: 'product' }], relationships: [{ child_source: 'product', child_table: 'events', child_columns: ['actor_id'], parent_source: 'crm', parent_table: 'people', parent_columns: ['id'] }] })

describe('combine workflow validation', () => {
  it('accepts an explicit many-to-one mapping', () => expect(validateCombination(request(), schemas)).toEqual([]))
  it('requires loaded schemas and at least two sources', () => {
    expect(validateCombination(request(), {}).length).toBeGreaterThan(0)
    const r = request(); r.sources.pop()
    expect(validateCombination(r, schemas)).toContain('Choose 2–5 sources.')
  })
  it('rejects unselected or same-source table references', () => {
    const r = request(); r.relationships[0].child_source = 'unknown'
    expect(validateCombination(r, schemas).join(' ')).toContain('different selected sources')
    r.relationships[0].child_source = 'crm'; r.relationships[0].child_table = 'people'
    expect(validateCombination(r, schemas).join(' ')).toContain('different selected sources')
  })
  it('requires declared parent uniqueness and aligned composite key order', () => {
    const r = request(); r.relationships[0].parent_columns = ['namespace']
    expect(validateCombination(r, schemas).join(' ')).toContain('primary/unique')
    r.relationships[0].child_columns = ['namespace', 'actor_id']; r.relationships[0].parent_columns = ['namespace', 'id']
    expect(validateCombination(r, schemas)).toEqual([])
    r.relationships[0].parent_columns.reverse()
    expect(validateCombination(r, schemas).join(' ')).toContain('key order')
  })
  it('rejects missing and repeated key columns', () => {
    const r = request(); r.relationships[0].child_columns = ['missing']
    expect(validateCombination(r, schemas).join(' ')).toContain('aligned column pairs')
    r.relationships[0].child_columns = ['actor_id', 'actor_id']; r.relationships[0].parent_columns = ['namespace', 'id']
    expect(validateCombination(r, schemas).join(' ')).toContain('distinct')
  })
  it('rejects duplicate aliases, source paths, links and invalid names', () => {
    const r = request(); r.sources[1].alias = 'crm'; r.sources[1].name = 'crm.db'; r.name = '../unsafe'
    expect(validateCombination(r, schemas).join(' ')).toContain('unique')
    expect(validateCombination(r, schemas).join(' ')).toContain('different source')
    expect(validateCombination(r, schemas).join(' ')).toContain('1–40')
    const duplicate = request(); duplicate.relationships.push(structuredClone(duplicate.relationships[0]))
    expect(validateCombination(duplicate, schemas).join(' ')).toContain('duplicates')
  })
  it('requires every selected source to be connected', () => {
    const r = request(); r.sources.push({ name: 'third.db', alias: 'third' })
    expect(validateCombination(r, { ...schemas, third: { ...schemas.crm, name: 'third.db' } }).join(' ')).toContain('Connect every')
  })
  it('starts with no approved mappings and discloses snapshot limitations', () => {
    const html = renderToStaticMarkup(<CombineDatabasesPanel databases={[]} disabled={false} onCreated={async () => {}} onActivate={async () => {}} />)
    expect(html).toContain('Combine uploaded databases')
    expect(html).toContain('not a live connection')
    expect(html).toContain('Originals stay unchanged')
    expect(html).not.toContain('checked=""')
    expect(html).toMatch(/disabled=""[^>]*>Create combined dataset/)
  })
})
