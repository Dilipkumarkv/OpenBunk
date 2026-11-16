import { describe, expect, it } from 'vitest'
import { round2 } from './money'

describe('round2', () => {
  it('rounds half up at .5 paise boundaries', () => {
    expect(round2(1.005)).toBe(1.01)
    expect(round2(2.675)).toBe(2.68) // classic binary float trap
    expect(round2(10.125)).toBe(10.13)
  })

  it('rounds negative values half-up away from zero', () => {
    expect(round2(-1.005)).toBe(-1.01)
    expect(round2(-2.675)).toBe(-2.68)
  })

  it('handles exact values and zero', () => {
    expect(round2(33825)).toBe(33825)
    expect(round2(0)).toBe(0)
    expect(round2(-0)).toBe(0)
  })

  it('coerces non-finite input to 0', () => {
    expect(round2(Number.NaN)).toBe(0)
    expect(round2(Number.POSITIVE_INFINITY)).toBe(0)
  })
})
