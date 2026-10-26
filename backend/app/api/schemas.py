"""Shared API v1 contracts. Wire decimals are strings; timestamps are aware IST."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar
from zoneinfo import ZoneInfo

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    field_validator,
    model_validator,
)

API_VERSION: Literal["1.0"] = "1.0"
IST = ZoneInfo("Asia/Kolkata")


def _timestamp(value: object) -> object:
    if not isinstance(value, (str, datetime)):
        raise ValueError("Use an ISO timestamp with an explicit timezone")
    return value


def _date(value: object) -> date:
    if isinstance(value, datetime):
        raise ValueError("Use a calendar date, not a timestamp")
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) == 10:
        return date.fromisoformat(value)
    raise ValueError("Use YYYY-MM-DD")


def _decimal(value: object) -> object:
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int)):
        raise ValueError("Use an exact decimal string")
    return value


def _money(value: object) -> object:
    if not isinstance(value, (str, Decimal)):
        raise ValueError("INR amounts require an exact decimal string")
    return value


ISTTimestamp = Annotated[
    AwareDatetime,
    BeforeValidator(_timestamp),
    AfterValidator(lambda value: value.astimezone(IST)),
]
ExchangeDate = Annotated[date, BeforeValidator(_date)]
DecimalValue = Annotated[
    Decimal,
    BeforeValidator(_decimal),
    Field(allow_inf_nan=False),
    WithJsonSchema(
        {"anyOf": [{"type": "string", "format": "decimal"}, {"type": "integer"}]},
        mode="validation",
    ),
]

RupeeAmount = Annotated[
    Decimal,
    BeforeValidator(_money),
    Field(max_digits=18, decimal_places=2, allow_inf_nan=False),
    WithJsonSchema(
        {
            "type": "string",
            "description": "Exact INR string: up to 18 digits and 2 decimal places.",
        },
        mode="validation",
    ),
    PlainSerializer(
        lambda value: format(value, ".2f"), return_type=str, when_used="json"
    ),
    WithJsonSchema(
        {"type": "string", "pattern": r"^-?[0-9]+\.[0-9]{2}$"}, mode="serialization"
    ),
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)


class HealthResponse(Contract):
    status: Literal["ok"] = "ok"
    application: str
    mode: Literal["PAPER"] = "PAPER"
    live_orders_enabled: Literal[False] = False


class KiteStatus(Contract):
    configured: bool
    authenticated: bool = False
    user_id: str | None = None
    expires_at: ISTTimestamp | None = None
    message: str


class InstrumentView(Contract):
    exchange: str
    tradingsymbol: str
    instrument_token: int = Field(gt=0)
    name: str
    expiry: ExchangeDate | None
    strike: DecimalValue = Field(ge=0)
    tick_size: DecimalValue = Field(ge=0)
    lot_size: int = Field(ge=0)
    instrument_type: str
    segment: str


class ExchangeSnapshot(Contract):
    count: int = Field(ge=0)
    loaded_at: ISTTimestamp
    current: bool


class InstrumentStatus(Contract):
    ready: bool
    exchanges: dict[str, ExchangeSnapshot]
    message: str


class NiftyResponse(Contract):
    as_of: ExchangeDate
    spot: InstrumentView
    future: InstrumentView
    option_expiries: list[ExchangeDate]
    selected_expiry: ExchangeDate
    options: list[InstrumentView]
    message: str


class ErrorDetail(Contract):
    location: list[str | int]
    code: str
    message: str = "Invalid value"


class APIError(Contract):
    code: str
    message: str
    request_id: str | None = None
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorEnvelope(Contract):
    error: APIError


class DateRangeRequest(Contract):
    start: ExchangeDate
    end: ExchangeDate

    @model_validator(mode="after")
    def chronological(self) -> "DateRangeRequest":
        if self.start > self.end:
            raise ValueError("Start must be on or before end")
        return self


class PaginationRequest(Contract):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0, le=1_000_000)

    @field_validator("limit", "offset", mode="before")
    @classmethod
    def integer_values(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError("Pagination requires integer values")
        if isinstance(value, str):
            if not value.isascii() or not value.lstrip("-").isdigit():
                raise ValueError("Pagination requires integer values")
            return int(value)
        return value


class Pagination(PaginationRequest):
    total: int | None = Field(default=None, ge=0, strict=True)
    next_offset: int | None = Field(default=None, ge=0, strict=True)


T = TypeVar("T")


class Page(Contract, Generic[T]):
    items: list[T]
    pagination: Pagination

    @model_validator(mode="after")
    def consistent(self) -> "Page[T]":
        page = self.pagination
        if len(self.items) > page.limit:
            raise ValueError("Returned items exceed requested limit")
        end = page.offset + len(self.items)
        if page.total is not None and self.items and end > page.total:
            raise ValueError("Returned items exceed known total")
        if page.next_offset is not None and (
            not self.items
            or len(self.items) != page.limit
            or page.next_offset != end
            or (page.total is not None and end >= page.total)
        ):
            raise ValueError("Next offset must identify a further full-page boundary")
        return self


EventKind = Literal[
    "tick",
    "brick",
    "signal",
    "trade",
    "position",
    "status",
    "alert",
    "session",
    "contract_selected",
    "service",
    "recovery",
    "quality",
    "context",
]


class EventEnvelope(Contract, Generic[T]):
    api_version: Literal["1.0"] = API_VERSION
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    sequence: int = Field(ge=1)
    kind: EventKind
    at: ISTTimestamp
    payload: T
