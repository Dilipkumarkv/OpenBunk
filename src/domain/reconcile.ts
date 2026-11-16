/**
 * Reconciliation: compares collections taken during a shift against the expected
 * sales value computed from meter readings.
 */

import { round2 } from './money'

export type ReconciliationStatus = 'balanced' | 'over' | 'short'

export interface ReconciliationResult {
  expected: number
  collected: number
  /** collected − expected; positive means more cash was taken than fuel sold. */
  variance: number
  status: ReconciliationStatus
}

/**
 * @param expectedValue total sales value from meter readings (petrol + diesel)
 * @param collections   actual collections grouped by mode (cash, UPI/card, …)
 * @param tolerance     absolute rupee tolerance for float/rounding drift (default ₹1)
 */
export function reconcileCollections(
  expectedValue: number,
  collections: number[],
  tolerance = 1,
): ReconciliationResult {
  const collectedRaw = collections.reduce(
    (sum, value) => sum + (Number.isFinite(value) ? value : 0),
    0,
  )
  const expected = round2(Number.isFinite(expectedValue) ? expectedValue : 0)
  const collected = round2(collectedRaw)
  const variance = round2(collected - expected) // round2 also normalizes -0

  let status: ReconciliationStatus = 'balanced'
  if (variance > tolerance) status = 'over'
  else if (variance < -tolerance) status = 'short'

  return { expected, collected, variance, status }
}
