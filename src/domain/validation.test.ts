import { describe, expect, it } from 'vitest'
import { validateShiftReadings, type ShiftValidationInput } from './validation'

const VALID: ShiftValidationInput = {
  petrolOpening: '12450',
  petrolClosing: '12780',
  dieselOpening: '22500',
  dieselClosing: '22920',
  petrolPrice: '102.50',
  dieselPrice: '89.50',
  cashCollected: '25000',
  upiCollected: '32000',
}

describe('validateShiftReadings', () => {
  it('accepts the prototype default draft', () => {
    expect(validateShiftReadings(VALID)).toEqual([])
  })

  it('flags empty and negative fields', () => {
    const issues = validateShiftReadings({ ...VALID, petrolClosing: '', dieselPrice: '-1' })
    expect(issues.map((i) => i.field)).toEqual(
      expect.arrayContaining(['petrolClosing', 'dieselPrice']),
    )
  })

  it('flags closing below opening', () => {
    const issues = validateShiftReadings({ ...VALID, petrolClosing: '12000' })
    expect(issues).toHaveLength(1)
    expect(issues[0].field).toBe('petrolClosing')
  })

  it('flags non-positive prices', () => {
    const issues = validateShiftReadings({ ...VALID, petrolPrice: '0', dieselPrice: '0' })
    expect(issues.map((i) => i.field)).toEqual(
      expect.arrayContaining(['petrolPrice', 'dieselPrice']),
    )
  })

  it('reports multiple issues at once', () => {
    const issues = validateShiftReadings({ ...VALID, petrolClosing: '', dieselClosing: '100' })
    expect(issues.length).toBeGreaterThanOrEqual(2)
  })
})
