from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True, frozen=True)
class Site:
    id: UUID
    code: str
    name: str
    plant_type: str
    active: bool
    created_at: datetime
    updated_at: datetime
    

@dataclass(slots=True, frozen=True)
class Asset:
    id: UUID
    site_id: UUID
    code: str
    name: str
    category: str
    criticality: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class WorkOrder:
    id: UUID
    site_id: UUID
    asset_id: UUID
    code: str
    title: str
    description: str
    priority: str
    status: str
    work_type: str
    due_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class SparePart:
    id: UUID
    site_id: UUID
    code: str
    name: str
    uom: str
    on_hand_qty: int
    reorder_point: int
    critical: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class WorkOrderSparePart:
    id: UUID
    work_order_id: UUID
    spare_part_id: UUID
    required_qty: int
    consumed_qty: int
    created_at: datetime
    updated_at: datetime