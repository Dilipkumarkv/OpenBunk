import { describe, expect, it } from 'vitest'
import { clearShiftDraft, loadShiftDraft, saveShiftDraft, DRAFT_STORAGE_KEY } from './draft'

const SAMPLE = {
  inputs: { 'nozzle-p1': { opening: '1', closing: '2' } },
  collections: { cash: '10', upi: '0' },
  rollover: { petrol: { authorized: false, value: '100000' } },
  shiftKind: 'afternoon',
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

  it('scopes drafts per station/employee/date/shift kind', () => {
    const storage = memoryStorage()
    saveShiftDraft(storage, SAMPLE, 'OB-001:EMP-00:2026-11-16:afternoon')

    expect(loadShiftDraft(storage, 'OB-001:EMP-00:2026-11-16:afternoon')).toEqual(SAMPLE)
    expect(loadShiftDraft(storage, 'OB-001:EMP-01:2026-11-16:afternoon')).toBeNull()
    expect(loadShiftDraft(storage, 'OB-001:EMP-00:2026-11-16:night')).toBeNull()
    expect(loadShiftDraft(storage)).toBeNull()
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
    storage.setItem(
      DRAFT_STORAGE_KEY,
      '{"inputs":{},"rollover":{},"collections":"nope","savedAt":"2026-01-01"}',
    )
    expect(loadShiftDraft(storage)).toBeNull()
  })

  it('clears the scoped draft only', () => {
    const storage = memoryStorage()
    saveShiftDraft(storage, SAMPLE, 'scope-a')
    saveShiftDraft(storage, SAMPLE, 'scope-b')

    clearShiftDraft(storage, 'scope-a')
    expect(loadShiftDraft(storage, 'scope-a')).toBeNull()
    expect(loadShiftDraft(storage, 'scope-b')).toEqual(SAMPLE)
  })
})
