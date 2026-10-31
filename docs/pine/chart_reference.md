# TradingView reference settings - REF-00-03

Status: Completed 2026-10-31 (D06) for REF-00-03 chart-settings intake.
All fields listed in the master task are evidenced by retained actual screenshots.
Reference exports, seed/range, remaining indicator inputs and parity remain downstream work.
Original Pine: `renko_indicator.pine` (unchanged).
Screenshot retained: [chart-reference-2026-10-31.png](chart-reference-2026-10-31.png).
User also pasted the indicator source in chat as implementation context.

| Actual chart field | Evidence / remaining confirmation |
| --- | --- |
| Exchange and symbol | Screenshot: NSE, NIFTY / Nifty 50 Index. Exact canonical ticker ID not shown in a settings dialog. |
| Chart resolution / underlying interval | Screenshot header and selected toolbar: 5 minutes. |
| Renko method | Screenshot header: Traditional. |
| Renko box size | Screenshot header: 50 points. Supplied Pine default boxSize=50. |
| Price source (for example Close) | Confirmed in actual Symbol settings screenshot: Close. |
| Wicks enabled/disabled | Confirmed in actual Symbol settings screenshot: Wick checked (enabled). |
| Chart timezone | Actual Symbol settings: (UTC+5:30) Kolk...; footer UTC+5:30. Consistent with Kolkata / Asia/Kolkata. |
| Completed brick close AND timestamp for anchor | Historical brick close 22700 at 2026-10-27 13:25:00 +05:30 (Asia/Kolkata), directly visible together in crosshair screenshots received 2026-10-31. Reference grid anchor evidence accepted; runtime configuration not changed. |
| Reference date range / loaded history start | Pending. Visible axis spans labels 21 through 30 and Nov; earliest loaded history/session start not established. |
| Indicator input changes from source defaults | Supplied Pine declares defaults; actual saved chart overrides still unconfirmed. Source defaults are already represented by backend/app/indicator/inputs.json. |
| Settings evidence supplied by user / date | Screenshot and pasted source supplied 2026-10-31; remaining actual settings question sent. |

## Source context established

User-supplied source identifies RenkoEntrySignal, ATR length 10, factor 2.5,
boxSize 50, RSI 14, Moderate and above, targets 2.5% / 4%, opposite-brick exit 1,
Target-2 exit enabled, optional safety exit disabled, futures NSE:NIFTY1!,
flow timeframe 5, flow/OI enabled and useClock=true with Asia/Kolkata.
These are source declarations, not verified chart input overrides. The separate
RSI pane visible in the screenshot is not proof of the indicator's saved inputs.
The original source and existing generated debug copy remain preserved.

## Remaining B3 work

Collect only missing price source, wicks, completed-brick close/timestamp,
loaded-history start/date range and saved input override/default confirmation.
Then reconcile the reference's 5-minute interval with the application's
minute_close construction before any parity claim. flowTf=5 governs futures
flow requests; it does not configure the underlying Renko chart interval.
Use an isolated source/configuration for validation; never relabel existing
minute-close checkpoints or overwrite operator history. Genuine feed update
acceptance remains separate from replay/UI tests and reference G1/G2 gates.

REF-00-03 chart-settings intake is Completed; UI-LIVE-B3 remains Pending for
construction/reference/feed acceptance. No entry-gate bypass or parity claim.

## Additional tooltip screenshot - 2026-10-31

[Retained tooltip screenshot](chart-tooltip-2026-10-31.png) shows
DIV-SELL-ENTRY [Z2SPL], entry 23000, T1 22425 (-2.5%), T2 22080 (-4%),
next opposite closed-brick exit or T2, Strong / Medium risk, direction score -6,
RSI 57 and flow -1. This supports the displayed trade-plan behavior; it does not
verify every saved input or independent indicator parity.

The OHLC header separately reads O=22950, H=23000, L=22852.80, C=23000.
Its low extends below the open/close body, providing evidence of a wick in the
reported chart OHLC. The actual wick settings toggle and construction source
remain unseen. Do not strip this low to force a body-only reference match.
The tooltip and header are not proven to identify the same brick; no exact
brick date/time is visible. Neither the 23000 entry nor header close is an
accepted timestamped anchor. Visible axis range is not loaded-history start.

## Actual indicator Inputs panel - 2026-10-31

[Retained Inputs screenshot](chart-inputs-trade-plan-2026-10-31.png) directly
shows tgt1Pct=2.5, tgt2Pct=4, exitOppN=1, exitAtT2=true,
exitOnStop=false, stopCapBx=6, showAdds=false and showPlan=true.
RSI Length 14 is visible at the lower edge. These visible settings match the
source defaults; the rest of the saved Inputs panel remains unobserved.
This is the RenkoEntrySignal indicator dialog, not the chart's Renko construction
settings. It does not establish price source, wick toggle or a brick timestamp.

## Actual Renko Symbol settings received - 2026-10-31

[Settings including timezone](chart-renko-settings-1-2026-10-31.png) and
[Renko settings](chart-renko-settings-2-2026-10-31.png) confirm Source=Close,
Wick enabled, Traditional box50 and regular-trading session selection (label
truncated). Timezone dropdown reads (UTC+5:30) Kolk... . These supersede earlier
missing source/wick observations. No need to request these fields again.

Remaining: completed-brick close AND timestamp, loaded-history start/range,
other saved indicator inputs; reconcile 5-minute construction and wick-bearing
reference with current minute-close/body-only implementation. No settings changed
and no reference/feed parity or B3 completion established by these images alone.

## Timestamped historical anchor received - 2026-10-31

[Crosshair screenshot 1](chart-anchor-1-2026-10-31.png),
[screenshot 2](chart-anchor-2-2026-10-31.png) and
[screenshot 3](chart-anchor-3-2026-10-31.png) identify the historical brick at
Tue 27 Oct '26 13:25, chart UTC+05:30. Header O=22750, H=22804.85,
L=22700, C=22700. Reference close/time recorded as 22700 and
2026-10-27T13:25:00+05:30. Later historical bricks are visible to its right.
The horizontal crosshair cursor prices (22752.55, 22696.55, 22798.85) are
not brick closes. Do not confuse them with the header's C=22700.

This supersedes earlier missing timestamp/anchor notes. No further anchor
screenshot is needed. This is grid alignment evidence, not the initial seed,
loaded-history start or proof of a matching brick sequence. Construction
reconciliation (5-minute Close with wicks versus minute-close/body-only),
remaining saved indicator inputs and real feed-update acceptance remain.

## REF-00-03 acceptance scope - D06 audit

The master row requires symbol, chart resolution, Traditional box, Close source,
wick setting, timezone and grid anchor. All are now documented from actual
screenshots: NSE:NIFTY / NSE Nifty 50, 5 minutes, Traditional50, Close,
Wick enabled, Asia/Kolkata and historical close22700 at
2026-10-27T13:25:00+05:30. REF-00-03 is accepted for this chart configuration
intake only. Missing reference seed/date range and remaining saved indicator
inputs stay explicit downstream prerequisites; they do not erase the collected
chart settings or justify a G1/G2/B3 completion. No application setting changed.
