"""Idempotent demo seed: station OB-001, fuel products, tanks, nozzles, demo employees.

Demo credentials (never use in production): Ravi=EMP-01, Kumar=EMP-02,
Manjunath=EMP-03 — PIN 1234 for all three.
"""

from decimal import Decimal

from .db import SessionLocal
from .models import Employee, FuelProduct, Nozzle, Station, Tank
from .security import hash_pin


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

        employees = [
            ("EMP-01", "Ravi", "manager"),
            ("EMP-02", "Kumar", "attendant"),
            ("EMP-03", "Manjunath", "attendant"),
        ]
        for code, name, role in employees:
            exists = db.query(Employee).filter(Employee.station_id == station.id, Employee.code == code).first()
            if exists is None:
                db.add(Employee(station_id=station.id, code=code, name=name, role=role, pin_hash=hash_pin("1234")))

        db.commit()
    print("Seed complete: station OB-001, products/tanks/nozzles/employees (demo PIN 1234).")


if __name__ == "__main__":
    seed()
