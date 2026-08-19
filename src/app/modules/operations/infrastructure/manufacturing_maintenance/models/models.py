from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base
from app.core.sqlalchemy_types import UTCDateTime
from app.modules.operations.domain.manufacturing_maintenance.entities import (
    Asset,
    Site,
    SparePart,
    WorkOrder,
    WorkOrderSparePart,
)

def utc_now() -> datetime:
    return datetime.now(UTC)


class SiteRecord(Base):
    __tablename__ = "sites"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plant_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manufacturing")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    assets: Mapped[list[AssetRecord]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    work_orders: Mapped[list[WorkOrderRecord]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    spare_parts: Mapped[list[SparePartRecord]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )

    @classmethod
    def from_entity(cls, site: Site) -> SiteRecord:
        return cls(
            id=site.id,
            code=site.code,
            name=site.name,
            plant_type=site.plant_type,
            active=site.active,
            created_at=site.created_at,
            updated_at=site.updated_at,
        )

    def to_entity(self) -> Site:
        return Site(
            id=self.id,
            code=self.code,
            name=self.name,
            plant_type=self.plant_type,
            active=self.active,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class AssetRecord(Base):
    __tablename__ = "assets"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sites.id"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="machine")
    criticality: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    site: Mapped[SiteRecord] = relationship(back_populates="assets")
    work_orders: Mapped[list[WorkOrderRecord]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )

    @classmethod
    def from_entity(cls, asset: Asset) -> AssetRecord:
        return cls(
            id=asset.id,
            site_id=asset.site_id,
            code=asset.code,
            name=asset.name,
            category=asset.category,
            criticality=asset.criticality,
            status=asset.status,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
        )

    def to_entity(self) -> Asset:
        return Asset(
            id=self.id,
            site_id=self.site_id,
            code=self.code,
            name=self.name,
            category=self.category,
            criticality=self.criticality,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class WorkOrderRecord(Base):
    __tablename__ = "work_orders"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sites.id"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    work_type: Mapped[str] = mapped_column(String(100), nullable=False, default="maintenance")
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    site: Mapped[SiteRecord] = relationship(back_populates="work_orders")
    asset: Mapped[AssetRecord] = relationship(back_populates="work_orders")
    spare_parts: Mapped[list[WorkOrderSparePartRecord]] = relationship(
        back_populates="work_order",
        cascade="all, delete-orphan",
    )

    @classmethod
    def from_entity(cls, work_order: WorkOrder) -> WorkOrderRecord:
        return cls(
            id=work_order.id,
            site_id=work_order.site_id,
            asset_id=work_order.asset_id,
            code=work_order.code,
            title=work_order.title,
            description=work_order.description,
            priority=work_order.priority,
            status=work_order.status,
            work_type=work_order.work_type,
            due_at=work_order.due_at,
            created_at=work_order.created_at,
            updated_at=work_order.updated_at,
        )

    def to_entity(self) -> WorkOrder:
        return WorkOrder(
            id=self.id,
            site_id=self.site_id,
            asset_id=self.asset_id,
            code=self.code,
            title=self.title,
            description=self.description,
            priority=self.priority,
            status=self.status,
            work_type=self.work_type,
            due_at=self.due_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class SparePartRecord(Base):
    __tablename__ = "spare_parts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sites.id"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    uom: Mapped[str] = mapped_column(String(50), nullable=False, default="pcs")
    on_hand_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reorder_point: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    site: Mapped[SiteRecord] = relationship(back_populates="spare_parts")
    work_order_items: Mapped[list[WorkOrderSparePartRecord]] = relationship(
        back_populates="spare_part",
        cascade="all, delete-orphan",
    )

    @classmethod
    def from_entity(cls, spare_part: SparePart) -> SparePartRecord:
        return cls(
            id=spare_part.id,
            site_id=spare_part.site_id,
            code=spare_part.code,
            name=spare_part.name,
            uom=spare_part.uom,
            on_hand_qty=spare_part.on_hand_qty,
            reorder_point=spare_part.reorder_point,
            critical=spare_part.critical,
            created_at=spare_part.created_at,
            updated_at=spare_part.updated_at,
        )

    def to_entity(self) -> SparePart:
        return SparePart(
            id=self.id,
            site_id=self.site_id,
            code=self.code,
            name=self.name,
            uom=self.uom,
            on_hand_qty=self.on_hand_qty,
            reorder_point=self.reorder_point,
            critical=self.critical,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class WorkOrderSparePartRecord(Base):
    __tablename__ = "work_order_spare_parts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    work_order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("work_orders.id"),
        nullable=False,
        index=True,
    )
    spare_part_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("spare_parts.id"),
        nullable=False,
        index=True,
    )
    required_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    work_order: Mapped[WorkOrderRecord] = relationship(back_populates="spare_parts")
    spare_part: Mapped[SparePartRecord] = relationship(back_populates="work_order_items")

    @classmethod
    def from_entity(cls, item: WorkOrderSparePart) -> WorkOrderSparePartRecord:
        return cls(
            id=item.id,
            work_order_id=item.work_order_id,
            spare_part_id=item.spare_part_id,
            required_qty=item.required_qty,
            consumed_qty=item.consumed_qty,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def to_entity(self) -> WorkOrderSparePart:
        return WorkOrderSparePart(
            id=self.id,
            work_order_id=self.work_order_id,
            spare_part_id=self.spare_part_id,
            required_qty=self.required_qty,
            consumed_qty=self.consumed_qty,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )