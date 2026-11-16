import { describe, expect, it } from 'vitest'
import {
  computeNozzleTotals,
  computeShiftTotals,
  computeVolume,
  parseMeterReading,
  parseMeterReadingOrZero,
} from './shift'

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
    expect(totals.totalValue).toBe(71415)
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

describe('computeVolume (rollover)', () => {
  it('handles a 5-digit totalizer wraparound when authorized', () => {
    // 99990 → 00020 through a 100000 rollover value
    expect(computeVolume(99990, 20, 100000)).toBe(30)
  })

  it('returns a negative volume when unauthorized — never silently corrected', () => {
    expect(computeVolume(99990, 20)).toBe(-99970)
  })

  it('ignores a rollover value that is not above the opening reading', () => {
    expect(computeVolume(99990, 20, 500)).toBe(-99970)
  })

  it('computes values with rollover via computeShiftTotals', () => {
    const totals = computeShiftTotals(
      {
        petrolOpening: 99990,
        petrolClosing: 20,
        dieselOpening: 500,
        dieselClosing: 800,
        petrolPrice: 100,
        dieselPrice: 90,
      },
      { petrolValue: 100000 },
    )
    expect(totals.petrolVolume).toBe(30)
    expect(totals.petrolValue).toBe(3000)
    expect(totals.totalValue).toBe(3000 + 300 * 90)
  })
})

describe('rounding policy', () => {
  it('rounds values half-up to 2 decimals', () => {
    const totals = computeShiftTotals({
      petrolOpening: 0,
      petrolClosing: 1,
      dieselOpening: 0,
      dieselClosing: 0,
      petrolPrice: 102.555, // would expose float artifacts without explicit rounding
      dieselPrice: 89.5,
    })
    expect(totals.petrolValue).toBe(102.56)
  })
})

describe('parseMeterReading', () => {
  it('parses plain numbers', () => {
    expect(parseMeterReading('12780')).toBe(12780)
    expect(parseMeterReading('102.5')).toBe(102.5)
    expect(parseMeterReading(' 330 ')).toBe(330)
  })

  it('accepts zero', () => {
    expect(parseMeterReading('0')).toBe(0)
  })

  it('rejects empty and whitespace', () => {
    expect(parseMeterReading('')).toBeNull()
    expect(parseMeterReading('   ')).toBeNull()
  })

  it('rejects non-numeric, non-finite and negative input', () => {
    expect(parseMeterReading('abc')).toBeNull()
    expect(parseMeterReading('Infinity')).toBeNull()
    expect(parseMeterReading('NaN')).toBeNull()
    expect(parseMeterReading('-1')).toBeNull()
  })
})

describe('parseMeterReadingOrZero', () => {
  it('falls back to 0 for invalid input', () => {
    expect(parseMeterReadingOrZero('')).toBe(0)
    expect(parseMeterReadingOrZero('bad')).toBe(0)
    expect(parseMeterReadingOrZero('420')).toBe(420)
  })
})

describe('computeNozzleTotals (dynamic nozzles)', () => {
  const rows = [
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

  it('sums every nozzle with its own server price', () => {
    const totals = computeNozzleTotals(rows)
    expect(totals.lines.map((line) => line.volume)).toEqual([330, 80, 420])
    expect(totals.totalLitres).toBe(830)
    expect(totals.totalValue).toBe(79615)
  })

  it('applies a rollover only to the authorized product code', () => {
    const totals = computeNozzleTotals(
      [
        {
          nozzleId: 'p1',
          label: 'P1',
          productCode: 'petrol',
          productName: 'Petrol',
          opening: '99990',
          closing: '20',
          unitPrice: '100',
        },
        {
          nozzleId: 'd1',
          label: 'D1',
          productCode: 'diesel',
          productName: 'Diesel',
          opening: '500',
          closing: '800',
          unitPrice: '90',
        },
      ],
      { petrol: 100000 },
    )
    expect(totals.lines[0].volume).toBe(30)
    expect(totals.lines[1].volume).toBe(300)
    expect(totals.totalValue).toBe(30 * 100 + 300 * 90)
  })
})
