/**
 * Credit account status from balance vs limit (mirrors server rule in API).
 */

export type CreditLimitStatus = 'over_limit' | 'near_limit' | 'active'

export const NEAR_LIMIT_RATIO = 0.8

export function creditLimitStatus(
  balance: number,
  creditLimit: number,
  nearLimitRatio = NEAR_LIMIT_RATIO,
): CreditLimitStatus {
  const safeBalance = Number.isFinite(balance) ? balance : 0
  const safeLimit = Number.isFinite(creditLimit) ? creditLimit : 0
  if (safeLimit <= 0) return safeBalance > 0 ? 'over_limit' : 'active'
  if (safeBalance > safeLimit) return 'over_limit'
  if (safeBalance >= safeLimit * nearLimitRatio) return 'near_limit'
  return 'active'
}

export const CREDIT_STATUS_LABEL: Record<CreditLimitStatus, string> = {
  over_limit: 'Over limit',
  near_limit: 'Near limit',
  active: 'Active',
}

export const CREDIT_STATUS_TONE: Record<CreditLimitStatus, 'red' | 'amber' | 'green'> = {
  over_limit: 'red',
  near_limit: 'amber',
  active: 'green',
}
