# UI-LIVE-B2 — Live workspace layout

Completed 2026-10-31 (D06). Incremental UI follow-up; product counts stay
237 Completed / 43 Pending. B1 remains Completed. B3 needs actual REF-00-03
settings; next independent batch is B4. Formal sessions remain zero.

The Live workspace now puts the existing Renko renderer and overlays in the
larger left column, with open paper P&L, direction/strength and Today summaries
on the right. Active positions span the full width below both columns. Last
closed trade, signals and alerts follow as activity panels. Below 1050px the
chart and summaries stack; below 760px the summary/activity cards stack into
one column. Position tables scroll locally and keep the page within the viewport.
Named chart, summary, positions and activity landmarks clarify navigation.

B1's aggregate moved into the right summary; the table and aggregate reuse
the same positions query/cache, server MTM and exact decimal helper. Missing,
stale, before-cost and last-price/liquidation distinctions remain explicit.
No calculations, API contracts, backend or close execution behavior changed in B2.
Chart source/revision identity, overlay controls and quote-only/missing-history
guidance remain in the existing renderer. No chart settings or anchor were guessed.

## Verification

From `D:\WorkSpace\AUREVON\frontend`:

```powershell
npm.cmd run test
npm.cmd run build
npm.cmd run lint
npx.cmd playwright test --config playwright.release.config.ts tests/live.spec.ts tests/unavailable-source.spec.ts --reporter=json
```

- **37 frontend tests PASS**, production build/TypeScript and ESLint PASS.
- **13 final built HTTPS browser checks PASS**, zero skipped, unexpected or flaky.
  Receipt: [UI-LIVE-B2-browser-checks.json](UI-LIVE-B2-browser-checks.json).
  Coverage includes desktop chart/summary proportions and alignment, positions
  below both columns, activity order, 1024/768/390px stacking without page
  overflow, B1 positive/negative/empty/missing/stale MTM, guarded duplicate close
  and final settlement, stored synthetic chart history/overlays/paging, incremental
  ticks, source revision changes, quote-only transition, missing history and
  genuine server-error visibility.
- Initial 13-check green receipt retained as
  [UI-LIVE-B2-initial-browser-checks.json](UI-LIVE-B2-initial-browser-checks.json).
  Screenshot review then caught global navigation `aside` styling narrowing the
  summary. Corrected the summary container while preserving its complementary
  landmark; added a right-edge/full-column assertion. Rebuilt and repeated all
  13 checks successfully. Final desktop and mobile screenshots visually inspected:
  [desktop](UI-LIVE-B2-desktop.png), [mobile](UI-LIVE-B2-mobile.png).
- The browser server runs on isolated 5174 with temporary synthetic replay state;
  screenshots and fixture quotes/trades do not establish live/reference acceptance.
- Read-only `python -m app.tools.local_ui_readiness` from backend:
  **BLOCKED**, `paper_trading_ready=false`, runtime `NOT_CHECKED`.
  BE-08-14, QA-09-19/20 and QA-11-15/16 remain pending reference/paper gates.
  No new backend suite was necessary for this frontend-only layout change;
  prior B1's 75 backend tests remain separately recorded.

Existing 5173/8000 owners, operator DB/config, original Pine and feed untouched.
Refresh existing Vite at https://localhost:5173/dashboard/; B2 needs no backend
restart. If B1's backend projection restart has never been applied, its safe
restart guidance still applies after observation/feed-stop/flat checks.

README, D06 daily log and NEXT_SESSION updated together. Usage, cash/headroom
and renewal remain Unknown; extra paid usage INR 0. No purchase or trade created
in operator state; UI completion does not enable paper entries.
