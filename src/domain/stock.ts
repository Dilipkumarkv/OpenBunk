/**
 * Tank book-stock projection (mirrors backend stock_movements ledger).
 * Authoritative stock comes from movements; this is the same math for UI/tests.
 */

export interface StockMovementLike {
  kind: 'opening' | 'receipt' | 'sale' | 'adjustment'
  delta_litres: number
}

export function projectBookStock(opening: number, movements: StockMovementLike[]): number {
  const base = safeNum(opening)
  const delta = movements.reduce((sum, m) => sum + safeNum(m.delta_litres), 0)
  return base + delta
}

/** Sum a movement ledger alone (useful when opening is already a movement). */
export function sumMovements(movements: StockMovementLike[]): number {
  return movements.reduce((sum, m) => sum + safeNum(m.delta_litres), 0)
}

/** Dip variance: physical − book. Positive means tank holds more than booked. */
export function dipVariance(physical: number, book: number): number {
  return safeNum(physical) - safeNum(book)
}

function safeNum(value: number): number {
  return Number.isFinite(value) ? value : 0
}
