from decimal import Decimal

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import audit, get_current_employee, get_db_dep, paginate
from ..errors import ApiError
from ..models import Employee, FuelProduct, Nozzle, StockMovement, Tank
from ..schemas import (
    FuelProductCreate,
    FuelProductOut,
    NozzleCreate,
    NozzleOut,
    TankCreate,
    TankOut,
    TankStockOut,
)

router = APIRouter(tags=["catalog"])


@router.get("/fuel-products", response_model=list[FuelProductOut])
def list_products(
    employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)
):
    return db.query(FuelProduct).filter(FuelProduct.station_id == employee.station_id).order_by(FuelProduct.name).all()


@router.post("/fuel-products", response_model=FuelProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: FuelProductCreate, employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    existing = db.query(FuelProduct).filter(FuelProduct.station_id == employee.station_id, FuelProduct.code == payload.code).first()
    if existing is not None:
        raise ApiError(409, "Product code already exists")
    product = FuelProduct(station_id=employee.station_id, **payload.model_dump())
    db.add(product)
    audit(db, station_id=employee.station_id, action="catalog.product_created", entity_type="fuel_product", entity_id=payload.code, actor=employee.id)
    db.commit()
    db.refresh(product)
    return product


@router.get("/tanks", response_model=list[TankOut])
def list_tanks(employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    return db.query(Tank).filter(Tank.station_id == employee.station_id).order_by(Tank.label).all()


@router.post("/tanks", response_model=TankOut, status_code=status.HTTP_201_CREATED)
def create_tank(payload: TankCreate, employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    product = db.get(FuelProduct, payload.product_id)
    if product is None or product.station_id != employee.station_id:
        raise ApiError(404, "Fuel product not found")
    existing = db.query(Tank).filter(Tank.station_id == employee.station_id, Tank.label == payload.label).first()
    if existing is not None:
        raise ApiError(409, "Tank label already exists")
    tank = Tank(station_id=employee.station_id, **payload.model_dump())
    db.add(tank)
    db.flush()
    # opening balance becomes the first ledger entry so stock is always derived from movements
    db.add(
        StockMovement(
            station_id=employee.station_id,
            tank_id=tank.id,
            kind="opening",
            delta_litres=payload.opening_book_litres,
            source_type="tank_setup",
            source_id=str(tank.id),
        )
    )
    audit(db, station_id=employee.station_id, action="catalog.tank_created", entity_type="tank", entity_id=tank.id, actor=employee.id)
    db.commit()
    db.refresh(tank)
    return tank


@router.get("/nozzles", response_model=list[NozzleOut])
def list_nozzles(employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    return db.query(Nozzle).filter(Nozzle.station_id == employee.station_id).order_by(Nozzle.label).all()


@router.post("/nozzles", response_model=NozzleOut, status_code=status.HTTP_201_CREATED)
def create_nozzle(payload: NozzleCreate, employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    tank = db.get(Tank, payload.tank_id)
    if tank is None or tank.station_id != employee.station_id:
        raise ApiError(404, "Tank not found")
    product = db.get(FuelProduct, payload.product_id)
    if product is None or product.station_id != employee.station_id:
        raise ApiError(404, "Fuel product not found")
    existing = db.query(Nozzle).filter(Nozzle.station_id == employee.station_id, Nozzle.label == payload.label).first()
    if existing is not None:
        raise ApiError(409, "Nozzle label already exists")
    nozzle = Nozzle(station_id=employee.station_id, **payload.model_dump())
    db.add(nozzle)
    audit(db, station_id=employee.station_id, action="catalog.nozzle_created", entity_type="nozzle", entity_id=nozzle.id, actor=employee.id)
    db.commit()
    db.refresh(nozzle)
    return nozzle


@router.get("/tanks/{tank_id}/stock", response_model=TankStockOut)
def tank_stock(tank_id: UUID, employee: Employee = Depends(get_current_employee), db: Session = Depends(get_db_dep)):
    tank = db.get(Tank, tank_id)
    if tank is None or tank.station_id != employee.station_id:
        raise ApiError(404, "Tank not found")
    total = db.query(func.coalesce(func.sum(StockMovement.delta_litres), Decimal("0"))).filter(
        StockMovement.tank_id == tank.id
    ).scalar()
    return TankStockOut(tank_id=tank.id, label=tank.label, book_stock_litres=total)
