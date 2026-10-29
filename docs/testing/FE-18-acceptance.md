# FE-18 Settings acceptance

Accepted 2026-10-29 (D04, early D38-D40): FE-18-01 through FE-18-11.
All evidence uses synthetic/replay state, not real-session paper acceptance.

| IDs | Delivered and checked |
| --- | --- |
| FE-18-01 | Settings/defaults/schema loading and recoverable errors; local drafts, field errors, save results, SPA/back/reload unsaved guards and stale-revision protection. Frozen request bodies and stable keys survive lost replies and reload; repeated clicks do not create another version. |
| FE-18-02/03 | Every original Pine input appears in its original group with exact defaults, bounds, options and tooltips. Dependency-disabled controls retain values. Supertrend, direction, trade plan, divergence, extra signals, flow and outlook are covered. Original Pine is read only. |
| FE-18-04/05 | Backend-derived strategy, fixed/risk sizing, strikes, hedge modes/premium, expiry, liquidity/margin, risk windows/limits/square-off and paper fill/slippage/cost forms. Exact decimal strings, safe integers, percentage bounds, ordered local IST windows and mutually exclusive cost schedules are validated. |
| FE-18-06 | Tick/minute-close, box, nullable anchor and lookback. Pine/data box edits stay synchronized. Grid/Pine saves require separate rebuild acknowledgement. Saved revision, rebuild requirement and owner activation state are shown. No rebuild-progress endpoint exists: the UI explicitly reports that no rebuild has started rather than inventing progress or activating an owner. |
| FE-18-07 | Persisted browser chart layers shared with Live; alternate blue/orange palette; saved theme; optional sounds enabled by a user gesture and browser notifications requested only on click. Event notifications run only in the signed-in open dashboard; no unattended delivery. |
| FE-18-08 | Restore defaults locally, size-limited file/text JSON import with version/type/unknown-field validation, staged review and canonical server export. Import/defaults never save implicitly. |
| FE-18-09 | Read-only canonical strike preview using saved strategy. Shows rejection reasons/attempts/candidates or expiry, short/hedge contracts, quantities, prices, margin, credit, loss and quote times. Unsaved settings block preview; changed inputs cancel/clear prior results. Assumed capital is distinct from wallet/project cash. Real fixture rejection and explicitly mocked accepted economics are tested; the mock is not an executable trade. |
| FE-18-10 | Explicit confirmation with individual old/new field values; separate rebuild acknowledgement. Existing server auth/CSRF/idempotency/exposure gates and audit are retained. Integration test correlates both successful and stale-rejected settings saves with audit action, actor, status and response request ID. No live-enable control exists. |
| FE-18-11 | Generated backend/Pine manifest parity, malformed imports, exact values, dependencies, stale drafts, tooltips, keyboard editing/modal dismissal/focus restoration, desktop and mobile acceptance. |

Implementation: `frontend/src/SettingsPage.tsx`, `settings-data.ts`,
`settings-manifest.json`, `StrikePreview.tsx`, `preferences.tsx`; shared router,
chart preferences and accepted socket events integrate the screen.
`frontend/tools/export_settings.py --check` verifies the generated contract against
backend models and the preserved original Pine source without opening the app/DB.

Verification:

- `npm.cmd test`: 35 passed, including 8 Settings contract/validation cases.
- `npm.cmd run build`: strict TypeScript and production Vite build pass.
- `npm.cmd run lint`: pass.
- `npm.cmd run test:browser`: 35 passed, including 9 Settings flows.
- Final `npm.cmd run test:browser -- tests/settings.spec.ts`: 10 passed,
  including the added keyboard/exact-review check (36 distinct browser flows
  across both runs). Mobile and desktop screenshots are in ignored test-results.
- Backend `pytest tests/test_domain_api.py tests/test_wallet.py -q`: 100 passed.
  Added focused audit test: 1 passed (52 deselected). Total 101 distinct targeted
  backend cases; existing FastAPI/Starlette httpx deprecation warning remains.
  Prior full backend result remains 780; no new full-suite claim.
- Ruff lint/format pass for the changed domain test and manifest generator.
- Manifest generation `--check`: pass.

The first browser attempt timed out during fixture startup before running tests.
Direct execution confirmed the synthetic chart publisher starts successfully.
Harness startup allowance is now 180 seconds for Windows fixture preparation;
test assertions/timeouts and the 655-brick fixture remain intact. Both subsequent
runs passed.

Tests use a temporary SQLite database, dummy wallet and temporary TLS on ports
5174/18765 only. No operator process on 5173/8000 was started/stopped, no migration
was applied to the operator DB, and no observation, funds or original Pine changed.
Backend/API/schema implementation is unchanged; only a backend acceptance test
was added. No restart is needed for this batch's backend changes.

Settings persist desired versions only. Existing migration/owner rebind, managed
indicator/strategy/runtime, real reference/G1/G2/G3, shadow comparison and qualifying
session gates remain separate. Zero qualifying formal sessions evidenced.
Next task: OPS-19-01. Actual usage, spend, headroom and renewal remain Unknown;
extra paid usage INR 0; no purchase/recharge authorized.
