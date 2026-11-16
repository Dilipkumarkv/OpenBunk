import { describe, expect, it } from 'vitest'
import { dipVariance, projectBookStock, sumMovements } from './stock'

describe('projectBookStock', () => {
  it('applies receipts and sales to opening', () => {
    const stock = projectBookStock(8420, [
      { kind: 'receipt', delta_litres: 6000 },
      { kind: 'sale', delta_litres: -330 },
      { kind: 'sale', delta_litres: -420 },
    ])
    expect(stock).toBe(13670)
  })

  it('handles tank closure scenario: seed opening minus one shift', () => {
    // matches the E2E-verified numbers: 8420 − 330 = 8090 and 11280 − 420 = 10860
    expect(projectBookStock(8420, [{ kind: 'sale', delta_litres: -330 }])).toBe(8090)
    expect(projectBookStock(11280, [{ kind: 'sale', delta_litres: -420 }])).toBe(10860)
  })

  it('treats non-finite inputs as 0', () => {
    expect(projectBookStock(Number.NaN, [{ kind: 'sale', delta_litres: Number.NaN }])).toBe(0)
  })
})

describe('sumMovements', () => {
  it('sums signed deltas', () => {
    expect(
      sumMovements([
        { kind: 'opening', delta_litres: 8000 },
        { kind: 'receipt', delta_litres: 6000 },
        { kind: 'sale', delta_litres: -5580 },
      ]),
    ).toBe(8420)
  })
})

describe('dipVariance', () => {
  it('returns negative when physical is below book (short)', () => {
    expect(dipVariance(8402, 8420)).toBe(-18)
  })

  it('returns positive when physical exceeds book (over)', () => {
    expect(dipVariance(11295, 11280)).toBe(15)
  })

  it('coerces non-finite values to 0', () => {
    expect(dipVariance(Number.NaN, 100)).toBe(-100)
  })
})
