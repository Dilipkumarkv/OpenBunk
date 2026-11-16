"""Server-side domain rules — mirrors docs/calculations.md (and src/domain/*.ts).

Persisted currency uses Decimal/NUMERIC; never binary floats.
"""

from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")
CENT = Decimal("0.01")


def round2(value: Decimal) -> Decimal:
    """Round half-up to 2 decimals (ties away from zero in magnitude)."""
    if value is None:
        return ZERO
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def compute_volume(opening: Decimal, closing: Decimal, rollover_value: Decimal | None = None) -> Decimal:
    """Meter volume with explicit rollover handling (never inferred)."""
    if closing >= opening:
        return closing - opening
    if rollover_value is not None and rollover_value > opening:
        return (rollover_value - opening) + closing
    return closing - opening  # negative — validation flags it


def credit_balance(entries) -> Decimal:
    """entries: iterable of (type, amount). charge +| receipt -| adjustment signed."""
    total = ZERO
    for entry_type, amount in entries:
        if entry_type == "charge":
            total += amount
        elif entry_type == "receipt":
            total -= amount
        elif entry_type == "adjustment":
            total += amount  # adjustment amount is signed as recorded (+ adds, − subtracts)
    return round2(total)


def reconcile(expected: Decimal, collections: list[Decimal], tolerance: Decimal = Decimal("1.00")) -> dict:
    collected = round2(sum(collections, ZERO))
    expected = round2(expected)
    variance = round2(collected - expected)
    if abs(variance) <= tolerance:
        status = "balanced"
    elif variance > tolerance:
        status = "over"
    else:
        status = "short"
    return {
        "expected": str(expected),
        "collected": str(collected),
        "variance": str(variance),
        "status": status,
    }
