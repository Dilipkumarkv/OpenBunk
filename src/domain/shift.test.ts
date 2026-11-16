import { describe, expect, it } from 'vitest'
import { computeShiftTotals, parseMeterReading, parseMeterReadingOrZero } from './shift'

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
