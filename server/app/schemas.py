"""Request/response models. JSON uses camelCase field names exactly as in D2 §3.C."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class EventType(str, Enum):
    RATE_DROP = "RATE_DROP"
    REJECT = "REJECT"
    BAHAN_BAKU_HABIS = "BAHAN_BAKU_HABIS"
    ALAT_BERHENTI = "ALAT_BERHENTI"


class EventSource(str, Enum):
    SENSOR = "SENSOR"
    AI = "AI"
    OPERATOR = "OPERATOR"


class InspectionStatus(str, Enum):
    PASSED = "PASSED"
    HOLD = "HOLD"


class BatchState(str, Enum):
    BERJALAN = "BERJALAN"
    DITUTUP = "DITUTUP"


class Result(str, Enum):
    OK = "OK"
    NG = "NG"


# ---- Auth (added beyond D2) ------------------------------------------------ #
class LoginRequest(ApiModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserOut(ApiModel):
    id: int
    username: str
    nama: str | None = None


class LoginResponse(ApiModel):
    token: str
    expires_at: datetime
    user: UserOut


# ---- Products (added beyond D2) -------------------------------------------- #
class ProductIn(ApiModel):
    sku: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=150)
    unit_price: float = Field(ge=0)


class ProductUpdate(ApiModel):
    name: str = Field(min_length=1, max_length=150)
    unit_price: float = Field(ge=0)


class ProductOut(ApiModel):
    sku: str
    name: str
    unit_price: float
    model_version: str | None = None
    threshold: float | None = None
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, protected_namespaces=())


# ---- Batches (added beyond D2) --------------------------------------------- #
class BatchIn(ApiModel):
    batch_code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    sku: str


class BatchOut(ApiModel):
    batch_code: str
    sku: str
    product_name: str
    batch_status: BatchState
    inspection_status: InspectionStatus
    started_at: datetime
    ended_at: datetime | None = None
    total_output: int
    total: int
    ok: int
    ng: int


# ---- 1. POST /production/outputs ------------------------------------------- #
class OutputIn(ApiModel):
    batch_code: str
    quantity: int = Field(gt=0)
    timestamp: datetime


class OutputOut(ApiModel):
    status: str = "recorded"
    batch_code: str
    total_output: int


# ---- 2. POST /production/events -------------------------------------------- #
class EventIn(ApiModel):
    batch_code: str
    event_type: EventType
    source: EventSource
    timestamp: datetime
    note: str | None = Field(default=None, max_length=500)


class EventCreated(ApiModel):
    status: str = "recorded"
    event_id: int


class EventOut(ApiModel):
    event_id: int
    batch_code: str
    event_type: EventType
    source: EventSource
    timestamp: datetime
    note: str | None = None
    inspection_id: int | None = None


# ---- 3. GET /products/{sku}/availability ----------------------------------- #
class AvailabilityOut(ApiModel):
    sku: str
    date: date
    available_qty: int
    updated_at: datetime | None


# ---- 4. GET /production/reports -------------------------------------------- #
class BatchReportRow(ApiModel):
    batch_code: str
    total_output: int
    ok: int
    ng: int
    events: int


class ProductionReport(ApiModel):
    date: date
    batches: list[BatchReportRow]


# ---- 5. POST /inspections -------------------------------------------------- #
class InspectionResult(ApiModel):
    inspection_id: int
    result: Result
    anomaly_score: float
    threshold: float
    reject: bool


# ---- 6. GET /inspections/alerts -------------------------------------------- #
class AlertOut(ApiModel):
    inspection_id: int
    batch_code: str
    anomaly_score: float
    image_url: str
    timestamp: datetime


# ---- 7. GET /inspections/reports/{batchCode} ------------------------------- #
class BatchInspectionReport(ApiModel):
    batch_code: str
    total: int
    ok: int
    ng: int
    ng_per_hour: dict[str, int]
    estimated_loss: float
    # Additive fields (not in D2, do not break its contract)
    sku: str
    unit_price: float
    ng_percent: float
    inspection_status: InspectionStatus
    batch_status: BatchState


# ---- 8. GET /batches/inspection-status ------------------------------------- #
class BatchStatusRow(ApiModel):
    batch_code: str
    sku: str
    status: InspectionStatus
    ok_qty: int


class BatchStatusList(ApiModel):
    batches: list[BatchStatusRow]


# ---- 9. GET /batches/{batchCode}/inspections ------------------------------ #
class InspectionRow(ApiModel):
    inspection_id: int
    result: Result
    anomaly_score: float
    timestamp: datetime


class InspectionHistory(ApiModel):
    batch_code: str
    total: int
    ng: int
    inspections: list[InspectionRow]


class HealthOut(ApiModel):
    status: str
    model_backend: str
    device: str
    models: dict[str, dict]
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, protected_namespaces=())
