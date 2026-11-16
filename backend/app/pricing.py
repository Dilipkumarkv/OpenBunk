"""Server-authoritative fuel pricing and nozzle/product attribution."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from .errors import ApiError
from .models import FuelPrice, FuelProduct, Nozzle, Tank, utcnow


def current_price(
    db: Session, station_id: UUID, product_id: UUID, at: datetime | None = None
) -> Decimal | None:
    moment = at or utcnow()
    row = (
        db.query(FuelPrice)
        .filter(
            FuelPrice.station_id == station_id,
            FuelPrice.product_id == product_id,
            FuelPrice.effective_from <= moment,
        )
        .order_by(FuelPrice.effective_from.desc())
        .first()
    )
    return row.unit_price if row is not None else None


def require_price(db: Session, station_id: UUID, product_id: UUID) -> Decimal:
    price = current_price(db, station_id, product_id)
    if price is None:
        raise ApiError(
            422,
            "No selling price is configured for this fuel product — set a price before posting",
            details={"product_id": str(product_id)},
        )
    return price


def resolve_nozzle(db: Session, station_id: UUID, nozzle_id: UUID) -> tuple[Nozzle, FuelProduct, Tank]:
    """Load a nozzle and prove nozzle → tank → product all agree and belong to the station."""
    nozzle = db.get(Nozzle, nozzle_id)
    if nozzle is None or nozzle.station_id != station_id:
        raise ApiError(404, "Nozzle not found")
    if not nozzle.active:
        raise ApiError(422, "Nozzle is inactive")
    tank = db.get(Tank, nozzle.tank_id)
    product = db.get(FuelProduct, nozzle.product_id)
    if tank is None or tank.station_id != station_id:
        raise ApiError(422, "Nozzle is not attached to a valid tank")
    if product is None or product.station_id != station_id:
        raise ApiError(422, "Nozzle is not attached to a valid fuel product")
    if not product.active:
        raise ApiError(422, "Fuel product is inactive")
    if tank.product_id != product.id:
        raise ApiError(
            422,
            "Nozzle/tank/product attribution is inconsistent — fix the catalog before posting",
        )
    return nozzle, product, tank
