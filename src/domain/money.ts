/**
 * Money rounding policy (see docs/calculations.md):
 * - Persisted currency will use integer minor units (paise) / decimal arithmetic.
 * - UI computes in floats but rounds half-up to 2 dp at value boundaries,
 *   so no fractional-paise drift surfaces in the UI.
 */

/**
 * Round half-up to 2 decimals (ties away from zero in magnitude), safe against the
 * classic float traps: 1.005 → 1.01, 2.675 → 2.68, 10.125 → 10.13.
 * Works on milli-scale to recover sub-cent remainder that binary floats smear.
 */
export function round2(value: number): number {
  if (!Number.isFinite(value)) return 0
  const sign = value < 0 || Object.is(value, -0) ? -1 : 1
  const milli = Math.abs(value) * 1000
  let cents = Math.floor(milli / 10)
  const remainder = Math.round(milli - cents * 10)
  if (remainder >= 5) cents += 1
  return (sign * cents) / 100 + 0 // +0 normalizes -0
}
