/**
 * Domain rules for shift meter readings.
 *
 * Two tiers on purpose:
 * - Computation is lenient (never throws, non-finite/empty sorts to 0) so the UI can
 *   recompute live while the operator types.
 * - Validation (see validation.ts) is strict and reports human-readable issues.
 */

import { round2 } from './money'

export interface ShiftReadings {
  petrolOpening: number
  petrolClosing: number
  dieselOpening: number
  dieselClosing: number
  petrolPrice: number
  dieselPrice: number
}

/**
 * Explicit rollover config, per fuel. Never inferred silently:
 * an authorized rollover records the totalizer wrap value (value at which the
 * meter returns to 0). Volume = (rolloverValue − opening) + closing.
 */
export interface RolloverConfig {
  petrolValue?: number
  dieselValue?: number
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
 * Meter volume with explicit rollover handling.
 * - closing >= opening: closing − opening (normal case)
 * - closing < opening and rolloverValue authorised (rolloverValue > opening):
 *   (rolloverValue − opening) + closing
 * - otherwise closing − opening (negative; validation flags it — never silently corrected)
 */
export function computeVolume(opening: number, closing: number, rolloverValue?: number): number {
  const open = num(opening)
  const close = num(closing)
  if (close >= open) return close - open
  if (rolloverValue !== undefined && Number.isFinite(rolloverValue) && rolloverValue > open) {
    return rolloverValue - open + close
  }
  return close - open
}

/**
 * Computes volumes (closing − opening totalizers) and values (volume × price).
 * Non-finite inputs are treated as 0; values are rounded half-up to 2 dp.
 */
export function computeShiftTotals(
  readings: ShiftReadings,
  rollover?: RolloverConfig,
): ShiftTotals {
  const petrolVolume = computeVolume(
    readings.petrolOpening,
    readings.petrolClosing,
    rollover?.petrolValue,
  )
  const dieselVolume = computeVolume(
    readings.dieselOpening,
    readings.dieselClosing,
    rollover?.dieselValue,
  )
  const petrolValue = round2(petrolVolume * num(readings.petrolPrice)) + 0 // +0 normalizes -0
  const dieselValue = round2(dieselVolume * num(readings.dieselPrice)) + 0
  return {
    petrolVolume,
    dieselVolume,
    petrolValue,
    dieselValue,
    totalValue: round2(petrolValue + dieselValue),
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

/**
 * A nozzle row as the shift form holds it: raw operator strings plus the
 * server-configured price. Kept framework-free so it can be unit tested.
 */
export interface NozzleReadingInput {
  nozzleId: string
  label: string
  productCode: string
  productName: string
  opening: string
  closing: string
  /** Server-configured price per litre, as a decimal string. Never operator-editable. */
  unitPrice: string
}

export interface NozzleLineTotal {
  nozzleId: string
  label: string
  productCode: string
  productName: string
  volume: number
  unitPrice: number
  value: number
}

export interface NozzleTotals {
  lines: NozzleLineTotal[]
  totalLitres: number
  totalValue: number
}

/**
 * Computes per-nozzle volume/value for every configured nozzle.
 * `rollover` is keyed by product code (e.g. petrol/diesel) and only applies when
 * an operator has explicitly authorized it for that fuel.
 */
export function computeNozzleTotals(
  readings: NozzleReadingInput[],
  rollover: Record<string, number | undefined> = {},
): NozzleTotals {
  const lines = readings.map((reading): NozzleLineTotal => {
    const volume = computeVolume(
      parseMeterReadingOrZero(reading.opening),
      parseMeterReadingOrZero(reading.closing),
      rollover[reading.productCode],
    )
    const unitPrice = parseMeterReadingOrZero(reading.unitPrice)
    return {
      nozzleId: reading.nozzleId,
      label: reading.label,
      productCode: reading.productCode,
      productName: reading.productName,
      volume,
      unitPrice,
      value: round2(volume * unitPrice) + 0,
    }
  })
  return {
    lines,
    totalLitres: round2(lines.reduce((sum, line) => sum + line.volume, 0)),
    totalValue: round2(lines.reduce((sum, line) => sum + line.value, 0)),
  }
}
