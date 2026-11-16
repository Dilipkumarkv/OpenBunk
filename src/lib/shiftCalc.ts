export interface ShiftReadings {
  petrolOpening: number
  petrolClosing: number
  dieselOpening: number
  dieselClosing: number
  petrolPrice: number
  dieselPrice: number
}

export interface ShiftTotals {
  petrolVolume: number
  dieselVolume: number
  petrolValue: number
  dieselValue: number
}

function num(value: number): number {
  return Number.isFinite(value) ? value : 0
}

/**
 * Computes volumes (closing − opening totalizers) and values (volume × price).
 * Non-finite inputs are treated as 0, matching the prototype's `(+v || 0)` behaviour.
 */
export function computeShiftTotals(readings: ShiftReadings): ShiftTotals {
  const petrolVolume = num(readings.petrolClosing) - num(readings.petrolOpening)
  const dieselVolume = num(readings.dieselClosing) - num(readings.dieselOpening)
  return {
    petrolVolume,
    dieselVolume,
    // `+ 0` normalizes negative zero (e.g. -500 * 0) to +0
    petrolValue: petrolVolume * num(readings.petrolPrice) + 0,
    dieselValue: dieselVolume * num(readings.dieselPrice) + 0,
  }
}
