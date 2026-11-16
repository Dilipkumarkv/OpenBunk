import { describe, expect, it } from 'vitest'
import { computeShiftTotals } from './shiftCalc'

describe('computeShiftTotals', () => {
  it('computes volumes and values from prototype defaults', () => {
    const totals = computeShiftTotals({
      petrolOpening: 12450,
      petrolClosing: 12780,
      dieselOpening: 22500,
      dieselClosing: 22920,
      petrolPrice: 102.5,
      dieselPrice: 89.5,
    })
    expect(totals.petrolVolume).toBe(330)
    expect(totals.dieselVolume).toBe(420)
    expect(totals.petrolValue).toBe(33825)
    expect(totals.dieselValue).toBe(37590)
  })

  it('treats non-finite inputs as 0', () => {
    const totals = computeShiftTotals({
      petrolOpening: Number.NaN,
      petrolClosing: 1000,
      dieselOpening: 500,
      dieselClosing: Number.NaN,
      petrolPrice: 102.5,
      dieselPrice: Number.NaN,
    })
    expect(totals.petrolVolume).toBe(1000)
    expect(totals.dieselVolume).toBe(-500)
    expect(totals.dieselValue).toBe(0)
  })
})
