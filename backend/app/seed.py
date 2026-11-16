"""Idempotent demo seed: station OB-001, fuel products, tanks, nozzles, demo employees.

Demo PINs: from OPENBUNK_SEED_PIN, defaulting to 1234 — only outside production.
In ENVIRONMENT=production, seeding is skipped unless OPENBUNK_SEED_PIN is set explicitly.

Demo logins: EMP-00 Deep (owner) · EMP-01 Ravi (manager) · EMP-02 Kumar (cashier)
             EMP-03 Manjunath (accountant) · EMP-04 Audit (auditor)
"""

import os
from decimal import Decimal

from .config import get_settings
from .db import SessionLocal
from .models import Employee, FuelProduct, Nozzle, Station, Tank
from .security import hash_pin

DEMO_PIN_FALLBACK = "1234"


def _seed_pin() -> str | None:
    settings = get_settings()
    pin = os.environ.get("OPENBUNK_SEED_PIN")
    if settings.is_production:
        if not pin:
            print("ENVIRONMENT=production and OPENBUNK_SEED_PIN unset — skipping employee seeding.")
            return None
        return pin
    return pin or DEMO_PIN_FALLBACK


def seed() -> None:
    with SessionLocal() as db:
        station = db.query(Station).filter(Station.code == "OB-001").first()
        if station is None:
            station = Station(code="OB-001", name="OpenBunk Demo Station", address="Melkote, Karnataka")
            db.add(station)
            db.flush()

        products: dict[str, FuelProduct] = {}
        for code, name in [("petrol", "Petrol"), ("diesel", "Diesel")]:
            product = db.query(FuelProduct).filter(
                FuelProduct.station_id == station.id, FuelProduct.code == code
            ).first()
            if product is None:
                product = FuelProduct(station_id=station.id, code=code, name=name)
                db.add(product)
                db.flush()
            products[code] = product

        tanks: dict[str, Tank] = {}
        for label, product_code, capacity, opening in [
            ("T-01", "petrol", Decimal("15000"), Decimal("8420")),
            ("T-02", "diesel", Decimal("20000"), Decimal("11280")),
        ]:
            tank = db.query(Tank).filter(Tank.station_id == station.id, Tank.label == label).first()
            if tank is None:
                from .models import StockMovement

                tank = Tank(
                    station_id=station.id,
                    label=label,
                    product_id=products[product_code].id,
                    capacity_litres=capacity,
                    opening_book_litres=opening,
                )
                db.add(tank)
                db.flush()
                db.add(
                    StockMovement(
                        station_id=station.id,
                        tank_id=tank.id,
                        kind="opening",
                        delta_litres=opening,
                        source_type="seed",
                        source_id="seed",
                    )
                )
            tanks[label] = tank

        nozzles = {"P1": ("T-01", "petrol"), "P2": ("T-01", "petrol"), "D1": ("T-02", "diesel")}
        for label, (tank_label, product_code) in nozzles.items():
            exists = db.query(Nozzle).filter(Nozzle.station_id == station.id, Nozzle.label == label).first()
            if exists is None:
                db.add(
                    Nozzle(
                        station_id=station.id,
                        label=label,
                        tank_id=tanks[tank_label].id,
                        product_id=products[product_code].id,
                    )
                )

        pin = _seed_pin()
        if pin is not None:
            employees = [
                ("EMP-00", "Deep", "owner"),
                ("EMP-01", "Ravi", "manager"),
                ("EMP-02", "Kumar", "cashier"),
                ("EMP-03", "Manjunath", "accountant"),
                ("EMP-04", "Audit", "auditor"),
            ]
            for code, name, role in employees:
                exists = db.query(Employee).filter(
                    Employee.station_id == station.id, Employee.code == code
                ).first()
                if exists is None:
                    db.add(Employee(station_id=station.id, code=code, name=name, role=role, pin_hash=hash_pin(pin)))

        db.commit()
    print("Seed complete: station OB-001 (demo employees EMP-00..EMP-04; PIN from OPENBUNK_SEED_PIN or 1234).")


if __name__ == "__main__":
    seed()
