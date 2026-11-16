import { describe, expect, it } from 'vitest'
import { validateNozzleDraft, validateShiftReadings, type ShiftValidationInput } from './validation'
import type { NozzleReadingInput } from './shift'

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
  it('accepts the default draft', () => {
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

  it('accepts closing below opening when rollover is authorized with a valid rollover value', () => {
    const issues = validateShiftReadings(
      { ...VALID, petrolOpening: '99990', petrolClosing: '20' },
      { petrol: true, petrolRolloverValue: 100000 },
    )
    expect(issues).toEqual([])
  })

  it('rejects an authorized rollover whose value is not above opening', () => {
    const issues = validateShiftReadings(
      { ...VALID, petrolOpening: '99990', petrolClosing: '20' },
      { petrol: true, petrolRolloverValue: 500 },
    )
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

describe('validateNozzleDraft (dynamic nozzles)', () => {
  const rows: NozzleReadingInput[] = [
    {
      nozzleId: 'p1',
      label: 'P1',
      productCode: 'petrol',
      productName: 'Petrol',
      opening: '12450',
      closing: '12780',
      unitPrice: '102.50',
    },
    {
      nozzleId: 'p2',
      label: 'P2',
      productCode: 'petrol',
      productName: 'Petrol',
      opening: '9000',
      closing: '9080',
      unitPrice: '102.50',
    },
    {
      nozzleId: 'd1',
      label: 'D1',
      productCode: 'diesel',
      productName: 'Diesel',
      opening: '22500',
      closing: '22920',
      unitPrice: '89.50',
    },
  ]

  it('accepts complete readings with server prices', () => {
    expect(validateNozzleDraft(rows, {}, { cash: '79615' })).toEqual([])
  })

  it('flags missing readings and missing prices per nozzle', () => {
    const issues = validateNozzleDraft([
      { ...rows[0], opening: '' },
      { ...rows[1], unitPrice: '' },
    ])
    expect(issues.map((issue) => issue.field)).toEqual(
      expect.arrayContaining(['p1:opening', 'p2:price']),
    )
  })

  it('flags closing below opening unless the product rollover is authorized', () => {
    const below = validateNozzleDraft([{ ...rows[0], closing: '12000' }])
    expect(below[0].field).toBe('p1:closing')
    expect(below[0].message).toMatch(/below opening/i)

    const authorized = validateNozzleDraft([{ ...rows[0], opening: '99990', closing: '20' }], {
      petrol: { authorized: true, value: '100000' },
    })
    expect(authorized).toEqual([])
  })

  it('rejects a rollover value that is not above the opening reading', () => {
    const issues = validateNozzleDraft([{ ...rows[0], opening: '99990', closing: '20' }], {
      petrol: { authorized: true, value: '500' },
    })
    expect(issues).toHaveLength(1)
    expect(issues[0].field).toBe('p1:closing')
  })

  it('flags negative or non-numeric collections', () => {
    const issues = validateNozzleDraft(rows, {}, { cash: '-1', upi: 'abc' })
    expect(issues.map((issue) => issue.field)).toEqual(
      expect.arrayContaining(['collection:cash', 'collection:upi']),
    )
  })
})
