# API contract v1.0 (BE-13-01)

Canonical models: `backend/app/api/schemas.py`. Existing routes use shared response
models and publish them in `/openapi.json`. API version is independent of the
application release version; every HTTP response carries
`X-AUREVON-API-Version: 1.0` and a server-generated `X-Request-ID`.

## Existing surface

| Route | Response |
| --- | --- |
| `GET /api/health` | `HealthResponse`; same existing fields, PAPER and live orders false |
| `GET /api/auth/kite/status` | `KiteStatus`; optional expiry serializes in aware IST |
| `GET /api/auth/kite/login` | Existing 303 redirect, now correctly documented as a redirect |
| `GET /api/auth/kite/callback` | Existing 303 callback redirect, excluded from public schema |
| `GET /api/market/instruments/status` | `InstrumentStatus` / per-exchange snapshots |
| `POST /api/market/instruments/refresh` | `InstrumentStatus` |
| `GET /api/market/nifty?expiry=YYYY-MM-DD` | `NiftyResponse`, including shared instrument views |

Existing success bodies remain unwrapped. `KiteStatus` and `InstrumentView` remain
importable from their former broker modules through explicit re-exports. No new
worker controls, wallet operations, dashboard login or WebSocket was activated.

## Dates and exact numbers

- `ISTTimestamp` requires an aware datetime or ISO timestamp with explicit offset;
  JSON output normalizes to Asia/Kolkata (`+05:30`). Naive values and numeric epochs
  are rejected. UTC database storage is unchanged.
- `ExchangeDate` accepts a date or exactly `YYYY-MM-DD`, interpreted as an exchange
  calendar date. Timestamp-to-date truncation is rejected. `DateRangeRequest`
  requires start <= end; dates are inclusive. Future queries should translate
  that to the appropriate half-open IST interval, then UTC for database access.
- `RupeeAmount` is a finite exact decimal, up to 18 digits including at most two
  fractional places. JSON input must be a string; Python Decimal is also accepted.
  Floats, integers, booleans, nonfinite values and fractional paise are rejected.
  JSON output is a string with two decimal places, e.g. `"-125.50"`. There is no
  automatic rounding or conversion to paise, and no binary floating-point step.
- Instrument strikes/tick sizes use a separate finite exact decimal type, preserving
  source precision instead of applying money formatting. They serialize as strings.
  DTO examples are wire examples, not account balances, receipts or trade evidence.

## Errors

All domain, validation, HTTP and unexpected failures share:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "request_id": "server-generated-id",
    "details": [
      {"location": ["query", "expiry"], "code": "value_error", "message": "Invalid value"}
    ]
  }
}
```

The body request ID matches its response header. Existing broker error codes and
safe fixed business messages are preserved. Validation responses omit raw input,
exception messages/context and unknown field names. HTTP errors use a standard
status phrase (or a fixed fallback); unexpected errors use a fixed 500 message.
Query values, tokens and exception details are not reflected or logged by request
middleware. Standard response headers retain no-store/no-referrer behavior.

This establishes the first formal error contract: framework `detail` bodies for
404/405/422 and unhandled failures are intentionally normalized to the shared
shape. Clients should inspect `error.code`, not framework-specific raw bodies.

## Pagination and typed events

`PaginationRequest` defines limit 1?200 (default 50), offset 0?1,000,000 (default 0).
Integer query strings are accepted; booleans/floats are rejected. `Page[T]` contains
`items` and `pagination` (limit, offset, nullable total and nullable next_offset).
Unknown total is null, never inferred as zero. Returned items cannot exceed limit
or a known total. A next offset must equal the end of a full returned page and
must precede any known total. An empty page beyond a known total is allowed.
Query owners must use deterministic ordering with a unique tie-breaker; these
models do not implement database paging or cursor isolation.

`EventEnvelope[T]` defines `api_version`, public run_id (32 lowercase hex digits),
1-based sequence, known kind, aware IST `at`, and a concrete typed payload. Sequence
is scoped to a run; clients must resnapshot after run changes or sequence gaps.
Kinds cover the existing internal market producers plus planned tick/brick/signal/
trade/position/status/alert messages. This envelope is a reusable schema; wrapping
raw market events into the public WebSocket belongs to BE-13-16, not this task.
Pagination/event models can publish their own concrete Pydantic JSON schemas;
unused future routes are not invented in the current OpenAPI document.

## Compatibility policy

Dashboard authentication (BE-13-02, 2026-10-27) adds GET
`/api/auth/dashboard/status` and POST `/api/auth/dashboard/login` / `logout`.
Login accepts only a JSON `password`; all three return `configured` and
`authenticated` booleans. Password/token/hash values never appear in response
JSON. The dashboard Secure HttpOnly SameSite=Strict cookie is distinct from Kite
login state. Session setup, expiry/revocation and pending BE-13-03 protection are
documented in [acceptance evidence](../testing/BE-13-02-acceptance.md).
Subsequent D02 work completed BE-13-03/04/05/15/16/17/18/19 and added versioned
REST/WS schemas and generated TypeScript for available routes. See
[dashboard operations](dashboard-operations.md) for CSRF headers, lockout/audit,
exact origins, snapshot/event recovery and replay restrictions, and the
[BE-13 matrix](../testing/BE-13-acceptance.md) for domain APIs still Pending.

Keep existing paths and field meanings within major version 1. New endpoints,
optional fields and optional request parameters may be additive. Consumers should
ignore unknown response fields; server request DTOs reject unknown inputs. Removing
or renaming fields, changing units/types, tightening existing accepted values or
changing enum meanings requires an explicit major contract migration and versioned
route/negotiation plan. Do not silently reinterpret a rupee string as paise or a
calendar date as UTC midnight. Future public payloads must bind a concrete generic
payload model instead of accepting arbitrary dictionary output. Generated frontend
contracts/OpenAPI artifacts now exist in `openapi.v1.json` and `api-v1.d.ts`.
BE-13-20 remains Pending until missing domain actions and frontend integration
are verified. Regenerate/check using the locked `tools/api-contracts` workflow.

Validation: 20 new contract cases in `test_api_contracts.py`; all 328 backend tests,
Ruff lint/format and strict mypy passed on 2026-10-26. One existing dependency
httpx/Starlette deprecation warning remains. No migration, account connection,
real market observation, paper execution or purchase was required.
