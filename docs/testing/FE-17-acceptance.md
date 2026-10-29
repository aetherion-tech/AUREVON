# FE-17 Wallet acceptance

Accepted 2026-10-29, D04: FE-17-01 through FE-17-08. Synthetic isolated
acceptance only; no operator wallet, local DB, original Pine, market observation,
backend process, billing or broker account was changed.

| ID | Delivered behavior |
| --- | --- |
| 01 | PAPER total/free/blocked capital cards use exact server amounts. Paper funds, broker funds and project budget are explicitly distinct. Missing/uninitialized/foreign-mode wallets remain unavailable. |
| 02 | Wallet deposit and top-bar quick-add share one dialog; exact positive INR, two decimal places, storage/balance limit and server errors. |
| 03 | Withdrawal displays free cash and rejects excess amounts using integer paise; the server rechecks funds atomically. |
| 04 | Reset permits a nonnegative target including zero, requires explicit confirmation and sends the exact API confirmation phrase. Reservations disable the action; the server rejects any active/pending exposure. Trades, ledger and risk locks/counters survive. |
| 05 | Conditional requirement resolved: no deletion API exists. A disabled history-deletion control explains unavailability. No destructive request or invented backend support. |
| 06 | Ledger uses explicit PAPER scope, 25-entry offset pages and server sequence/running balance/reserved amounts. INITIAL, DEPOSIT, WITHDRAW, RESET, RESERVE, RELEASE, REALISED_GROSS and COSTS retain their canonical names. Exact paise, IST timestamps and references are visible. |
| 07 | Effective owner auto-top-up setting/status is read-only. Explains simulated funding ceiling versus actual free cash and cash-flow exclusion from profit/returns. Editing remains in FE-18's versioned settings workflow. |
| 08 | All wallet pages/top-bar balances refresh after mutations and accepted trade/position events. Frozen body and stable idempotency key survive dialog close/reload; in-flight clicks cannot create duplicates. Insufficient funds, exposure rejection, mode separation and mobile layout verified. |

Verification:

- Frontend unit/component suite: **27 passed**, including six new wallet cases.
- Full HTTPS Chromium regression: **25 passed**; subsequent focused Wallet suite:
  **6 passed**, including the added settled-trade event case (26 distinct flows
  across the two runs). Desktop/mobile screenshots generated; mobile inspected.
- Targeted backend wallet/domain API regressions: **100 passed**, one existing
  Starlette/httpx deprecation warning. Prior full backend result remains 780;
  no backend code or API/schema change in this batch.
- Production build/strict TypeScript and ESLint pass.
- Browser harness uses temporary SQLite and TLS, disables dotenv/feed, and
  runs on 5174/18765. New tests assert the isolated base URL. Financial mutations
  in those tests affect only the temporary synthetic wallet. Operator 5173/8000
  and existing observation state are untouched.

Commands from frontend: `npm.cmd test`, `npm.cmd run test:browser`,
`npm.cmd run build`, `npm.cmd run lint`. Backend regressions:
`.\.venv\Scripts\python.exe -m pytest tests/test_wallet.py tests/test_domain_api.py -q`.

Reset and withdrawal lost-response retries retain the original action even if
free cash changed after commit. Rejected keys retain the server outcome; the
operator must review ledger/positions before discarding a pending request.
Ledger data is append-only under these operations, so offset pages remain stable.
All loaded ledger pages invalidate through the shared wallet cache prefix.

The initial browser-test edit was rejected by automatic review because it was
interpreted as operator-wallet mutation. Existing harness isolation was verified
and made explicit in the test file; the isolated version was accepted and ran.
No approval remains blocked and no operator mutation was attempted.

Totals: 214 Completed / 66 Pending of 280; frontend 46 Completed / 11 Pending.
Next: FE-18-01 Settings loading, edits, validation, unsaved-change guard and save
results. Actual runtime/reference/G1/G2/G3 and observation gates remain Pending;
formal qualifying sessions remain 0. Usage/spend/renewal/headroom Unknown;
extra paid usage INR 0. No purchase or recharge.
