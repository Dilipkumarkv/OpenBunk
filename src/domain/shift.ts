/**
 * Domain rules for shift meter readings.
 *
 * Two tiers on purpose:
 * - Computation is lenient (never throws, non-finite/empty sorts to 0) so the UI can
 *   recompute live while the operator types.
 * - Validation (see validation.ts) is strict and reports human-readable issues.
 */

export interface ShiftReadings {
  petrolOpening: number
  petrolClosing: number
  dieselOpening: number
  dieselClosing: number
  petrolPrice: number
  dieselPrice: number
}

export interface ShiftTotals {
  petrolVolume: number
  dieselVolume: number
  petrolValue: number
  dieselValue: number
  totalValue: number
}

function num(value: number): number {
  return Number.isFinite(value) ? value : 0
}

/**
 * Computes volumes (closing − opening totalizers) and values (volume × price).
 * Non-finite inputs are treated as 0. A zero price legitimately yields a zero value.
 */
export function computeShiftTotals(readings: ShiftReadings): ShiftTotals {
  const petrolVolume = num(readings.petrolClosing) - num(readings.petrolOpening)
  const dieselVolume = num(readings.dieselClosing) - num(readings.dieselOpening)
  // `+ 0` normalizes negative zero (e.g. -500 * 0) to +0
  const petrolValue = petrolVolume * num(readings.petrolPrice) + 0
  const dieselValue = dieselVolume * num(readings.dieselPrice) + 0
  return {
    petrolVolume,
    dieselVolume,
    petrolValue,
    dieselValue,
    totalValue: petrolValue + dieselValue,
  }
}

/**
 * Parses a raw operator input field. Returns null for empty or invalid input
 * (non-numeric, non-finite, or negative). Never throws.
 */
export function parseMeterReading(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') return null
  const value = Number(trimmed)
  if (!Number.isFinite(value) || value < 0) return null
  return value
}

/** Lenient parse for live calculations: invalid input counts as 0. */
export function parseMeterReadingOrZero(raw: string): number {
  return parseMeterReading(raw) ?? 0
}
