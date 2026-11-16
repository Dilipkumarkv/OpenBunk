"""Unit tests for backend domain rules (mirror of src/domain/*.ts)."""

from decimal import Decimal

from app.domain import compute_volume, credit_balance, reconcile, round2


def test_round2_half_up_ties():
    assert round2(Decimal("1.005")) == Decimal("1.01")
    assert round2(Decimal("2.675")) == Decimal("2.68")
    assert round2(Decimal("10.125")) == Decimal("10.13")
    assert round2(Decimal("-1.005")) == Decimal("-1.01")
    assert round2(Decimal("0")) == Decimal("0.00")


def test_compute_volume_normal_and_rollover():
    assert compute_volume(Decimal("12450"), Decimal("12780")) == Decimal("330")
    # authorized rollover: 99990 → 20 through a 100000 totalizer
    assert compute_volume(Decimal("99990"), Decimal("20"), Decimal("100000")) == Decimal("30")


def test_compute_volume_negative_without_rollover():
    assert compute_volume(Decimal("99990"), Decimal("20")) == Decimal("-99970")


def test_credit_balance_mixed_entries():
    entries = [("charge", Decimal("48000")), ("receipt", Decimal("20000")), ("adjustment", Decimal("-2500"))]
    assert credit_balance(entries) == Decimal("25500.00")


def test_credit_balance_zero_when_empty():
    assert credit_balance([]) == Decimal("0.00")


def test_reconcile_balanced_over_short():
    assert reconcile(Decimal("71415.00"), [Decimal("40000"), Decimal("31415.00")])["status"] == "balanced"
    assert reconcile(Decimal("1000"), [Decimal("1500")])["status"] == "over"
    assert reconcile(Decimal("1000"), [Decimal("900")])["status"] == "short"


def test_reconcile_tolerance_boundary_is_inclusive():
    assert reconcile(Decimal("1000.00"), [Decimal("1001.00")], Decimal("1.00"))["status"] == "balanced"
    assert reconcile(Decimal("1000.00"), [Decimal("1001.01")], Decimal("1.00"))["status"] == "over"
    assert reconcile(Decimal("1000.00"), [Decimal("998.99")], Decimal("1.00"))["status"] == "short"
