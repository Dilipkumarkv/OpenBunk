import { describe, expect, it } from 'vitest'
import { reconcileCollections } from './reconcile'

describe('reconcileCollections', () => {
  it('is balanced when collections match expected sales within tolerance', () => {
    const result = reconcileCollections(71415, [40000, 31415])
    expect(result.collected).toBe(71415)
    expect(result.variance).toBe(0)
    expect(result.status).toBe('balanced')
  })

  it('treats sub-tolerance drift as balanced', () => {
    expect(reconcileCollections(71415, [71415.5]).status).toBe('balanced')
  })

  it('flags collections above sales as over', () => {
    const result = reconcileCollections(1000, [1500])
    expect(result.variance).toBe(500)
    expect(result.status).toBe('over')
  })

  it('flags collections below sales as short', () => {
    const result = reconcileCollections(1000, [900])
    expect(result.variance).toBe(-100)
    expect(result.status).toBe('short')
  })

  it('honours a custom tolerance', () => {
    expect(reconcileCollections(1000, [1050], 100).status).toBe('balanced')
    expect(reconcileCollections(1000, [1101], 100).status).toBe('over')
  })

  it('ignores non-finite collection entries and expected values', () => {
    const result = reconcileCollections(Number.NaN, [100, Number.NaN, 100])
    expect(result.expected).toBe(0)
    expect(result.collected).toBe(200)
    expect(result.status).toBe('over')
  })
})
