/**
 * Offline draft persistence for the shift-closing form.
 * Network interruption must never silently lose an operator's entry (master principle 8).
 * Drafts live in sessionStorage, are scoped per station/employee/date/shift-kind, and are
 * cleared only when the data is safely on the server or the shift is closed.
 */

export interface ShiftDraftInputs {
  [nozzleId: string]: { opening: string; closing: string }
}

export interface ShiftDraftRollover {
  [productCode: string]: { authorized: boolean; value: string }
}

export interface ShiftDraft {
  inputs: ShiftDraftInputs
  collections: Record<string, string>
  rollover: ShiftDraftRollover
  shiftKind?: string
  savedAt: string // ISO
}

const KEY = 'openbunk.draft.shift'

/** Drafts are scoped by station + employee + shift date + kind so operators never share entries. */
function storageKey(scope?: string): string {
  return scope ? `${KEY}:${scope}` : KEY
}

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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function saveShiftDraft(storage: Storage, draft: ShiftDraft, scope?: string): boolean {
  return safeSet(storage, storageKey(scope), JSON.stringify(draft))
}

export function loadShiftDraft(storage: Storage, scope?: string): ShiftDraft | null {
  const raw = safeGet(storage, storageKey(scope))
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!isRecord(parsed)) return null
    if (typeof parsed.savedAt !== 'string') return null
    if (!isRecord(parsed.inputs)) return null
    if (!isRecord(parsed.rollover)) return null
    if (parsed.collections !== undefined && !isRecord(parsed.collections)) return null
    if (parsed.shiftKind !== undefined && typeof parsed.shiftKind !== 'string') return null
    return parsed as unknown as ShiftDraft
  } catch {
    return null
  }
}

export function clearShiftDraft(storage: Storage, scope?: string): void {
  try {
    storage.removeItem(storageKey(scope))
  } catch {
    /* storage unavailable — non-fatal */
  }
}

export const DRAFT_STORAGE_KEY = KEY
