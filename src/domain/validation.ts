/**
 * Strict validation of a shift draft. Mirrors the fields the operator types
 * (raw strings), so it can distinguish "empty" from "zero" and report real issues.
 */

import { parseMeterReading } from './shift'

export interface ShiftValidationInput {
  petrolOpening: string
  petrolClosing: string
  dieselOpening: string
  dieselClosing: string
  petrolPrice: string
  dieselPrice: string
  cashCollected: string
  upiCollected: string
}

/**
 * Explicit rollover authorization (never inferred). When authorized, a totalizer
 * decreasing through 0 is legitimate and closing<opening is not an error.
 * The rollover value itself must be > the opening reading to be valid.
 */
export interface RolloverAuthorization {
  petrol?: boolean
  diesel?: boolean
  petrolRolloverValue?: number
  dieselRolloverValue?: number
}

export interface ValidationIssue {
  field: keyof ShiftValidationInput
  message: string
}

const LABELS: Record<keyof ShiftValidationInput, string> = {
  petrolOpening: 'Petrol P1 opening',
  petrolClosing: 'Petrol P1 closing',
  dieselOpening: 'Diesel D1 opening',
  dieselClosing: 'Diesel D1 closing',
  petrolPrice: 'Petrol price',
  dieselPrice: 'Diesel price',
  cashCollected: 'Cash collected',
  upiCollected: 'UPI / card collected',
}

function required(
  field: keyof ShiftValidationInput,
  raw: string,
): { issue?: ValidationIssue; value: number | null } {
  const value = parseMeterReading(raw)
  if (value === null) {
    return {
      issue: { field, message: `${LABELS[field]} must be a non-negative number.` },
      value: null,
    }
  }
  return { value }
}

/** Validates a raw shift draft. Empty array means valid. */
export function validateShiftReadings(
  input: ShiftValidationInput,
  rollover: RolloverAuthorization = {},
): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const parsed = {} as Record<keyof ShiftValidationInput, number | null>

  for (const field of Object.keys(LABELS) as (keyof ShiftValidationInput)[]) {
    const { issue, value } = required(field, input[field])
    if (issue) issues.push(issue)
    parsed[field] = value
  }

  if (parsed.petrolPrice !== null && parsed.petrolPrice <= 0) {
    issues.push({ field: 'petrolPrice', message: 'Petrol price must be greater than zero.' })
  }
  if (parsed.dieselPrice !== null && parsed.dieselPrice <= 0) {
    issues.push({ field: 'dieselPrice', message: 'Diesel price must be greater than zero.' })
  }
  if (
    parsed.petrolOpening !== null &&
    parsed.petrolClosing !== null &&
    parsed.petrolClosing < parsed.petrolOpening
  ) {
    if (rollover.petrol) {
      if (
        rollover.petrolRolloverValue === undefined ||
        !Number.isFinite(rollover.petrolRolloverValue) ||
        rollover.petrolRolloverValue <= parsed.petrolOpening
      ) {
        issues.push({
          field: 'petrolClosing',
          message:
            'Authorized petrol rollover needs a rollover value greater than the opening reading.',
        })
      }
    } else {
      issues.push({
        field: 'petrolClosing',
        message:
          'Petrol P1 closing is below opening — check the meter readings (or authorize a rollover).',
      })
    }
  }
  if (
    parsed.dieselOpening !== null &&
    parsed.dieselClosing !== null &&
    parsed.dieselClosing < parsed.dieselOpening
  ) {
    if (rollover.diesel) {
      if (
        rollover.dieselRolloverValue === undefined ||
        !Number.isFinite(rollover.dieselRolloverValue) ||
        rollover.dieselRolloverValue <= parsed.dieselOpening
      ) {
        issues.push({
          field: 'dieselClosing',
          message:
            'Authorized diesel rollover needs a rollover value greater than the opening reading.',
        })
      }
    } else {
      issues.push({
        field: 'dieselClosing',
        message:
          'Diesel D1 closing is below opening — check the meter readings (or authorize a rollover).',
      })
    }
  }

  return issues
}
