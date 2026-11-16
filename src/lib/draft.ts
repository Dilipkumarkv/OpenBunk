/**
 * Offline draft persistence for the shift-closing form.
 * Network interruption must never silently lose an operator's entry (master principle 8).
 * Drafts live in sessionStorage; clearing happens on successful sync or explicit shift close.
 */

export interface ShiftDraft {
  inputs: Record<string, string>
  rollover: { petrol: boolean; diesel: boolean; petrolValue: string; dieselValue: string }
  savedAt: string // ISO
}

const KEY = 'openbunk.draft.shift'

function safeGet(storage: Storage, key: string): string | null {
  try {
    return storage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(storage: Storage, key: string, value: string): boolean {
  try {
    storage.setItem(key, value)
    return true
  } catch {
    return false
  }
}

export function saveShiftDraft(storage: Storage, draft: ShiftDraft): boolean {
  return safeSet(storage, KEY, JSON.stringify(draft))
}

export function loadShiftDraft(storage: Storage): ShiftDraft | null {
  const raw = safeGet(storage, KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as ShiftDraft
    if (typeof parsed !== 'object' || parsed === null) return null
    if (typeof parsed.savedAt !== 'string') return null
    if (typeof parsed.inputs !== 'object' || parsed.inputs === null) return null
    if (typeof parsed.rollover !== 'object' || parsed.rollover === null) return null
    return parsed
  } catch {
    return null
  }
}

export function clearShiftDraft(storage: Storage): void {
  try {
    storage.removeItem(KEY)
  } catch {
    /* storage unavailable — non-fatal */
  }
}

export const DRAFT_STORAGE_KEY = KEY
