import { describe, expect, it } from 'vitest'
import { clearShiftDraft, loadShiftDraft, saveShiftDraft, DRAFT_STORAGE_KEY } from './draft'

const SAMPLE = {
  inputs: { petrolOpening: '1', petrolClosing: '2' },
  rollover: { petrol: false, diesel: true, petrolValue: '100000', dieselValue: '50000' },
  savedAt: '2026-11-16T10:00:00.000Z',
}

function memoryStorage(): Storage {
  const map = new Map<string, string>()
  return {
    get length() {
      return map.size
    },
    clear: () => map.clear(),
    getItem: (k: string) => map.get(k) ?? null,
    key: (i: number) => [...map.keys()][i] ?? null,
    removeItem: (k: string) => void map.delete(k),
    setItem: (k: string, v: string) => void map.set(k, v),
  }
}

describe('shift draft persistence', () => {
  it('saves and restores a draft round-trip', () => {
    const storage = memoryStorage()
    expect(saveShiftDraft(storage, SAMPLE)).toBe(true)
    expect(loadShiftDraft(storage)).toEqual(SAMPLE)
  })

  it('returns null for missing or corrupt data', () => {
    const storage = memoryStorage()
    expect(loadShiftDraft(storage)).toBeNull()
    storage.setItem(DRAFT_STORAGE_KEY, '{not json')
    expect(loadShiftDraft(storage)).toBeNull()
    storage.setItem(DRAFT_STORAGE_KEY, '"just a string"')
    expect(loadShiftDraft(storage)).toBeNull()
    storage.setItem(DRAFT_STORAGE_KEY, '{"inputs":{}}') // missing rollover/savedAt
    expect(loadShiftDraft(storage)).toBeNull()
  })

  it('clears the draft', () => {
    const storage = memoryStorage()
    saveShiftDraft(storage, SAMPLE)
    clearShiftDraft(storage)
    expect(loadShiftDraft(storage)).toBeNull()
  })
})
