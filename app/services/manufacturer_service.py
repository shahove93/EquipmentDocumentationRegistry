from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.manufacturers.schemas import ManufacturerCreate, ManufacturerUpdate
from app.models.manufacturer import Manufacturer

DEFAULT_LIMIT = 50


class ManufacturerService:
    """Business logic for manufacturers.

    Sessions are passed in by the caller (see `app.database.connection.get_db`),
    so the service never opens or closes connections on its own.

    Transaction boundaries: this service commits its own writes, exactly once
    per operation. `create` and `update` therefore persist immediately, and a
    caller that needs to group several service calls into one unit of work
    should manage that transaction itself.
    """

    @staticmethod
    def create(db: Session, data: ManufacturerCreate) -> Manufacturer:
        """Create and persist a manufacturer, returning the stored row."""
        manufacturer = Manufacturer(**data.model_dump())
        db.add(manufacturer)
        db.commit()
        db.refresh(manufacturer)
        return manufacturer

    @staticmethod
    def get_by_id(db: Session, manufacturer_id: int) -> Manufacturer | None:
        """Return the manufacturer or None when no such row exists."""
        return db.get(Manufacturer, manufacturer_id)

    @staticmethod
    def list(
        db: Session, limit: int = DEFAULT_LIMIT, offset: int = 0
    ) -> list[Manufacturer]:
        """Return manufacturers ordered by ascending id."""
        statement = (
            select(Manufacturer)
            .order_by(Manufacturer.id)
            .limit(limit)
            .offset(offset)
        )
        return list(db.scalars(statement))

    @staticmethod
    def update(
        db: Session, manufacturer_id: int, data: ManufacturerUpdate
    ) -> Manufacturer | None:
        """Apply a partial update, returning None when no such row exists.

        Fields absent from the payload are left untouched. An empty payload
        changes nothing and therefore commits nothing.
        """
        manufacturer = db.get(Manufacturer, manufacturer_id)
        if manufacturer is None:
            return None

        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return manufacturer

        for field, value in changes.items():
            setattr(manufacturer, field, value)

        db.commit()
        db.refresh(manufacturer)
        return manufacturer