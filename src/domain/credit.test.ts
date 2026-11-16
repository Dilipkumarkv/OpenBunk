import { describe, expect, it } from 'vitest'
import { creditLimitStatus } from './credit'

describe('creditLimitStatus', () => {
  it('flags over limit strictly above the limit', () => {
    expect(creditLimitStatus(28400, 25000)).toBe('over_limit')
    expect(creditLimitStatus(25000, 25000)).toBe('near_limit') // exactly at limit is not over
  })

  it('flags near limit at >= 80% of the limit', () => {
    expect(creditLimitStatus(48000, 50000)).toBe('near_limit')
    expect(creditLimitStatus(40000, 50000)).toBe('near_limit')
    expect(creditLimitStatus(39999, 50000)).toBe('active')
  })

  it('is active for normal balances', () => {
    expect(creditLimitStatus(18200, 75000)).toBe('active')
    expect(creditLimitStatus(0, 50000)).toBe('active')
  })

  it('handles zero/negative limits safely', () => {
    expect(creditLimitStatus(100, 0)).toBe('over_limit')
    expect(creditLimitStatus(0, 0)).toBe('active')
  })

  it('coerces non-finite values to 0', () => {
    expect(creditLimitStatus(Number.NaN, 50000)).toBe('active')
    expect(creditLimitStatus(Number.NaN, Number.NaN)).toBe('active')
  })
})
