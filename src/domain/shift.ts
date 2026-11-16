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
