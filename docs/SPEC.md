# Original project specification

Extracted from Aurevon.docx. Paragraph text is preserved; Word diagrams and table layout are not reproduced.

Renko Auto-Trader - Full Project Specification

Project or Application Name would be - AUREVON

Oct 23, 2026 · @ST

1. Project goal and scope

Build a Python service that rebuilds your TradingView Renko indicator exactly, watches it live on Zerodha Kite data, and turns each ENTRY/EXIT signal into an option-selling trade (paper or live), shown on a web dashboard.

What v1 delivers

A Python engine that reproduces the Pine Script (Supertrend, RSI divergence, CORE / DIV / HDIV / PB / BRK / TRAP / ORB / SRG signals, direction score, trade plan, ENTRY and EXIT) with the same results as TradingView.

A live feed from Kite Connect that builds Renko bricks the same way TradingView does.

A strategy layer that converts a BUY or SELL signal into an option-selling position (strike, hedge, stop-loss, target, quantity).

An execution layer with two modes, Paper and Live, that share one position model so both always show the same position.

A web dashboard with Live tab, History tab, Wallet (dummy money) and Settings.

A database that stores every signal, order, trade and daily/weekly/monthly P&L.

Out of scope for v1 (planned for later)

Multi-user logins with separate broker accounts (design allows it, UI does not).

Mobile app, Telegram bot (alerts are planned in phase 7).

Backtesting UI (a command-line replay tool is included for testing).

Multiple underlyings running at the same time (v1 runs one at a time, config-driven).

Success criteria

Every ENTRY and EXIT the Python engine produces matches TradingView on the same Renko data, same bar, same code (CO/DIV/OT, BUY/SELL).

Paper and Live use the same code path up to the final order call.

No live order is possible unless Live mode is armed, daily loss limit is not hit and the kill switch is off.

2. Decisions needed and assumptions made

Eleven decisions shape the build. Each row has a default I used throughout this document; change any of them and the affected sections update.

#

Decision

Default used in this document

Why

D1

Underlying

NIFTY (box size 50 from the Pine default)

BankNifty is a config switch later

D2

Price source for Renko

NIFTY futures for flow only; Renko price = NIFTY 50 spot index

Futures carry volume and OI, which the flow engine still needs. Your chart uses the spot index, so Renko is built from index ticks and the futures feed serves only the flow engine

D3

Renko type

Traditional, fixed box 50, built from close

Must match the TradingView chart setting exactly

D4

Option strategy

Defined-risk credit spread: bullish signal = sell PE + buy lower PE; bearish signal = sell CE + buy higher CE

Hedge cuts margin and caps loss; naked selling is a config flag, off by default

D5

Expiry and strike

Nearest weekly expiry, short strike = 1 strike OTM from spot, hedge = 4 strikes further

Read from the Kite instruments file, never hard-coded

D6

Exit

Indicator EXIT (opposite brick or Target 2) + premium stop-loss + 15:15 IST square-off

Follows your Pine logic, plus a safety net

D7

Paper fills

Last price plus configurable slippage (default 0.5 points per leg)

Realistic enough to judge the strategy

D8

Database

SQLite in v1, PostgreSQL by changing one setting

Same code (SQLAlchemy + Alembic), no migration pain

D9

Where it runs

Your Windows PC in v1; a small cloud VM with a static IP before real money

Live orders need a registered static IP (see below)

D10

Daily Kite login

One-click login button in the dashboard each morning

Kite tokens expire daily; auto-login scripts risk breaking broker terms

D11

Quantity

Lots set in Settings (default 1 lot); lot size is read from the instruments file

NSE changes lot sizes; never hard-code

Broker facts that change the plan (checked 23 Oct 2026)

Live prices over WebSocket and historical candles need the paid Kite Connect plan at ₹500 per month per app; the free Personal plan has no market data (Zerodha support). Paper trading also needs live data, so you need the paid plan from day one.

Order APIs need a static IP registered for your app (Kite forum). Home broadband often has no static IP, so plan a cloud VM or a static-IP service before going live.

Own algos stay unregistered with the exchange while under 10 orders per second; Kite allows up to 10 per account (Kite API FAQ). This app sends a few orders a day.

From October 2026, paying users with ₹2,000 or more brokerage in a month get ₹500 in credits that renew the next month's plan (same Zerodha page as above).

Assumptions

One trader account today; every table carries a user_id so two or more users can be added later without a redesign.

Instrument is index options on NSE (NFO); intraday only, no overnight positions.

Exchange and SEBI rules change often; check Zerodha's current algo notices before each live-trading change.

Your TradingView indicator is the source of truth; the Python port must agree with it, not improve on it.

3. What your Pine Script does (analysis for the port)

The script is a Renko-chart indicator that scores market direction from ten factors, detects eight signal types, grades each one, and runs a simple one-position trade engine with targets and an opposite-brick exit. A large part of the code is explanation text for hover tooltips; the trading logic itself is much smaller.

3.1 Processing order on every new brick

Compute Supertrend (ATR 10, factor 2.5), RSI 14, brick colour, run length, trend age.

Track swing tops (green→red turn) and bottoms (red→green turn) with their RSI; run the divergence engine.

Pull daily context (previous close, day open, previous-day and today high/low) and the 5-minute futures flow (VWAP, volume ratio, OI change).

Compute the 10-factor direction score and the bias (bullish / bearish / sideways).

Evaluate the 8 raw signal conditions, pick one per direction by priority, apply cooldown, grade it, filter by minimum grade.

Trade engine: check EXIT first (only on a closed brick after the entry brick), then ENTRY.

Update statistics, then draw (the port replaces drawing with data sent to the dashboard).

3.2 The eight signal types

Code

Name

Fires when

Family in alerts

CORE

Trend Start

Supertrend flips and the first brick of the new colour appears within 3 bricks; once per flip

CO

DIV

Reversal

Two swing tops (or bottoms) at equal/higher (lower) price but RSI weaker by at least 0.5; first RSI at least 50 (top) or at most 50 (bottom)

DIV

HDIV

Trend Continues

Hidden divergence in the direction of the trend

DIV

PB

Pullback

One counter-colour brick, then trend colour resumes; trend at least 3 bricks old

OT

BRK

Breakout

Close crosses the last swing top/bottom, swing at most 40 bricks old

OT

TRAP

Failed breakout

A BRK fails within 6 bricks and price closes back inside

OT

ORB

Opening breakout

First close outside the 09:15–09:30 IST range, until 11:30, range at least 2 boxes

OT

SRG

Flow surge

Flow score at least 4 and volume spike, within 2 bricks of the surge starting

OT

Priority when several fire together (per direction): DIV, CORE, ORB, BRK, TRAP, HDIV, SRG, PB. CORE and DIV ignore the 3-brick cooldown; the others respect it.

3.3 Grading (strength 1 to 3)

DIV and TRAP: count five pieces of evidence (flow agrees, price vs VWAP agrees, stretched from Supertrend, near support/resistance, RSI turning). 3 or more = Strong, 2 = Moderate, else Weak.

All other types: direction score times side, minus 2 if a late-entry warning applies. 5 or more = Strong, 2 to 4 = Moderate, else Weak.

Default filter "Moderate and above" drops Weak signals, so your entries are Moderate or Strong only.

3.4 The ten direction factors (max score ±14)

Factor

Range

Rule

Supertrend

±2

Up = +2, down = −2

Run

±1

Two or more bricks of the same colour

RSI

±1

At least 55 = +1, at most 45 = −1

Flow

±2

From flow score (see 3.6)

Structure

±2

Higher high / higher low = +1 each; lower = −1 each

Divergence

±2

Fresh divergence within 8 bricks, or ±1 if one is forming

Hidden divergence

±1

Fresh hidden divergence

Swing break

±1

Price above last swing top / below last swing bottom

Odds

±1

History of what followed bricks like this one (needs 20 samples)

Day

±1

Above both yesterday's close and today's open, or below both

Bias becomes bullish at +4 or more, bearish at −4 or less, and returns to sideways at +1 / −1 (hysteresis). Strong means absolute score 8 or more.

3.5 Trade engine rules (this is what your app copies)

Entry at the close of the signal brick. One trade at a time; a new signal in the same direction while in a trade is ignored.

Target 1 = entry ±2.5%, Target 2 = entry ±4% of the index price (about 600 and 960 points at 24,000; these are large for Renko box 50).

EXIT on the first closed brick of the opposite colour, or on Target 2. The safety-stop exit is off by default.

Exit is evaluated before entry on the same brick, so an opposite signal first closes the old trade, then opens the new one.

Statistics are tracked per family and direction (CO/DIV/OT × BUY/SELL).

3.6 Flow engine (needs futures data)

On the 5-minute futures chart: price change over 3 bars, OI change over 3 bars, VWAP side, volume spike (previous bar volume at least 1.5× its 20-bar average) and day change. Build-up classification: price up + OI up = long build-up (+2); price up + OI down = short covering (+1); price down + OI up = short build-up (−2); price down + OI down = long unwinding (−1). Flow score = window build-up + VWAP + volume + day, range −5 to +5.

3.7 Port hazards (things that will break parity if ignored)

Renko bricks. TradingView builds bricks from its own data and rules (box size, source price, wick handling). The Python Renko must produce the same brick list. Section 9 covers how to prove it.

Indicator maths. Pine's RSI and ATR use Wilder smoothing (RMA); Supertrend must use the same ATR on brick high/low/close. Use hand-written functions, not a library with different seeding.

Persistent state. Pine var variables survive across bricks and are rolled back on realtime ticks. In Python, process each brick exactly once, in order, from one state object.

Open interest. The script reads TradingView's _OI series. Kite gives OI in futures ticks and historical candles; values and timing can differ from TradingView.

Daily VWAP and volume. ta.vwap resets daily; build the same session reset from Kite 5-minute candles.

Clock. Renko brick timestamps are unreliable, so the script uses timenow in IST. The Python engine uses the tick's exchange timestamp in IST.

Intrabar vs closed. Signals and exits only act on closed bricks; Renko bricks are closed the moment they form, so the engine acts only when a new brick is produced.

4. System architecture and data flow

One Python process receives Kite ticks, builds Renko bricks, runs the indicator, turns signals into option spreads and sends orders to either the paper broker or the live broker; the dashboard sees everything over one WebSocket.



architecture · one backend process, two brokers

Read top to bottom: ticks enter at the top, orders leave through one of two brokers, and the database and dashboard hang off the position manager and the API. The red box is the only place real money moves; TradingView stays outside as a comparison, never as a trigger.

From tick to trade (normal path)

A futures tick arrives; the ticker handler puts it on a queue and returns immediately.

The Renko builder consumes the queue; when a brick closes, the indicator engine runs exactly once for that brick.

The engine returns an IndicatorResult with any ENTRY or EXIT event; every result is stored and pushed to the dashboard.

An ENTRY event goes to the strategy layer, which builds a trade plan; the risk gate accepts it or rejects it with a stored reason.

The order manager sends the plan to the active broker (hedge leg first), polls fills, and the position manager starts streaming live profit and loss.

An EXIT event, a premium stop, the 15:15 square-off or the kill switch closes both legs; the result goes to history, daily P&L and the wallet.

Process model in v1: one asyncio event loop with five tasks (ticker, brick and indicator consumer, position monitor, scheduler, API server). Heavy work never runs inside the tick handler. Scaling later means moving the first three tasks into their own process; the interfaces in section 6 already allow it.

5. Technology stack

Python (FastAPI) for the backend and React + TypeScript for the frontend, because that pair gives a professional dashboard, live streaming, and room to grow without a rewrite.

Layer

Choice

Why

Alternative if you prefer

Language

Python 3.12

Your choice; best library support for trading

—

Web framework

FastAPI + Uvicorn

Async, built-in WebSocket, automatic API docs at /docs

Flask (weaker for live streams)

Broker SDK

kiteconnect (official pykiteconnect)

Official REST + WebSocket ticker

Raw REST calls

Data maths

numpy, pandas (for tests and replay only)

Live path uses plain Python on single bricks for speed and exact control

—

Config

pydantic-settings + .env

Typed settings, secrets outside code

—

Database

SQLAlchemy 2 + Alembic; SQLite (v1) → PostgreSQL

Same code on both; migrations tracked

Raw SQL

Scheduler

APScheduler

08:45 pre-checks, 15:15 square-off, 15:35 daily report

Windows Task Scheduler

Internal events

asyncio queues in one process

Simple, fast; swap for Redis Streams when scaling

Redis from day one

Logging

structlog (JSON lines) to rotating files

Easy audit of every decision

loguru

Tests

pytest, hypothesis for Renko rules

Parity and edge-case coverage

—

Quality

ruff (lint + format), mypy

Catches mistakes before money is involved

—

Frontend

React 18 + TypeScript + Vite

Fast dev loop, no server rendering needed for a private dashboard

Next.js

UI kit

Tailwind CSS + shadcn/ui

Clean, professional, dark mode

Ant Design

Data fetching

TanStack Query + one WebSocket hook

Cache for REST, push for live

—

Charts

TradingView Lightweight Charts

Free, fast, candlestick series shows Renko bricks natively with markers for ENTRY/EXIT

ECharts

Tables

TanStack Table (history)

Sorting, filters, export

AG Grid

P&L charts

Recharts

Daily/weekly/monthly bars

—

Process manager (Windows)

NSSM or Task Scheduler (v1), Docker later

Keeps backend running

pm2

Why not Streamlit or Dash: they redraw the page on updates and struggle with a tick-driven chart plus two action buttons; a React front end avoids that and scales to more users.

Why not run the indicator on TradingView: TradingView cannot call your app directly except through alert webhooks, which fire only at bar close and cannot provide the full hover details. You will still use TradingView as a shadow check: set the same alerts there, point them at a webhook in the backend, and compare with the Python engine (section 18).

Scaling path (no rewrite needed)

v1: one process on your PC, SQLite.

v2: same code on a cloud VM, PostgreSQL, Docker Compose, static IP.

v3: split the market-data worker from the API (Redis Streams in between), add user accounts and one broker connection per user.

6. Repository and folder structure

One Git repository (monorepo) with backend, frontend and docs side by side; the module names below are the ones used in every later section and in the Codex prompts.

renko-trader/├─ README.md├─ .env.example                  # KITE_API_KEY, KITE_API_SECRET, DB_URL, TZ=Asia/Kolkata ...├─ docs/│  ├─ SPEC.md                    # this document, exported│  └─ pine/renko_indicator.pine  # your original script (read-only reference)├─ scripts/                      # Windows PowerShell helpers (setup, run, backup)├─ backend/│  ├─ pyproject.toml             # dependencies (managed by uv)│  ├─ alembic/                   # database migrations│  ├─ app/│  │  ├─ main.py                 # FastAPI app, startup/shutdown wiring│  │  ├─ config.py               # typed settings (all Pine inputs live here too)│  │  ├─ core/                   # enums, event bus, IST time helpers, logging│  │  ├─ broker/│  │  │  ├─ base.py              # Broker interface (place, modify, cancel, positions)│  │  │  ├─ kite_auth.py         # login URL, request_token → access_token, daily refresh│  │  │  ├─ kite_ticker.py       # WebSocket ticks, reconnect, resubscribe│  │  │  ├─ instruments.py       # daily instruments dump, option-chain lookup│  │  │  ├─ live_broker.py       # real orders via Kite│  │  │  └─ paper_broker.py      # simulated fills, same interface│  │  ├─ market/│  │  │  ├─ renko_builder.py     # ticks → bricks (matches TradingView)│  │  │  ├─ candles_5m.py        # futures 5-minute candles, VWAP, volume, OI│  │  │  └─ session.py           # market hours, holidays, day rollover│  │  ├─ indicator/              # the Pine port, one file per concern│  │  │  ├─ maths.py             # rma, rsi, atr, supertrend, crossover, barssince│  │  │  ├─ state.py             # the 'var' variables as one dataclass│  │  │  ├─ divergence.py        # swing tops/bottoms, DIV, HDIV, forming│  │  │  ├─ flow.py              # build-up, flow score│  │  │  ├─ outlook.py           # run statistics, odds, levels│  │  │  ├─ bias.py              # 10 factors → score → bias│  │  │  ├─ signals.py           # CORE/DIV/HDIV/PB/BRK/TRAP/ORB/SRG + priority + cooldown│  │  │  ├─ grading.py           # strength and risk│  │  │  ├─ trade_plan.py        # entry, targets, EXIT rules, statistics│  │  │  ├─ texts.py             # hover explanations (same wording as Pine)│  │  │  └─ engine.py            # on_new_brick(brick) → IndicatorResult│  │  ├─ strategy/│  │  │  ├─ option_mapper.py     # signal → option legs│  │  │  ├─ strike_selector.py   # expiry, strikes, hedge│  │  │  ├─ sizing.py            # lots, margin check│  │  │  └─ risk.py              # daily loss limit, max trades, kill switch│  │  ├─ execution/│  │  │  ├─ mode.py              # PAPER / LIVE switch and arming│  │  │  ├─ order_manager.py     # one path for both modes│  │  │  ├─ position_manager.py  # open positions, live P&L, exits│  │  │  └─ reconciler.py        # compare our book with Kite's│  │  ├─ wallet/service.py       # dummy money ledger│  │  ├─ db/                     # models.py, session.py, repositories/│  │  ├─ api/                    # routes_live.py, routes_history.py, routes_wallet.py, routes_settings.py, ws.py, schemas.py│  │  ├─ jobs/scheduler.py       # timed jobs│  │  └─ tools/                  # replay.py, parity_check.py, export_instruments.py│  └─ tests/                     # unit/, parity/, integration/, fixtures/└─ frontend/   ├─ package.json   └─ src/      ├─ app/                    # router, layout, theme      ├─ pages/                  # Live.tsx, History.tsx, Wallet.tsx, Settings.tsx      ├─ components/             # RenkoChart, PositionCard, PnlSummary, ModeSwitch, SignalFeed, TradeTable      ├─ hooks/                  # useLiveSocket, useTrades, useWallet      ├─ api/                    # typed client generated from the OpenAPI spec      └─ store/                  # mode, connection status

Rules for the code base

The indicator package never imports from broker, execution or api. It takes a brick in and returns a result, so it can be replayed in tests.

paper_broker and live_broker implement the same Broker interface; everything above them cannot tell which one it uses.

All times inside the backend are timezone-aware IST (Asia/Kolkata); the database stores UTC.

7. Environment setup on Windows, IntelliJ and Codex

You can have an empty but running backend, frontend and database in about two hours by following these steps in order.

7.1 Install the tools (PowerShell, run as normal user)

winget install Git.Gitwinget install Python.Python.3.12winget install astral-sh.uvwinget install OpenJS.NodeJS.LTS# optional later: winget install Docker.DockerDesktop# restart the terminal, then check:git --version ; python --version ; uv --version ; node --version ; npm --version

7.2 Create the project

mkdir C:\work\renko-trader ; cd C:\work\renko-tradergit initmkdir docs\pine, backend, scripts# copy your Pine file to docs\pine\renko_indicator.pinecd backenduv init --package app ; uv add fastapi "uvicorn[standard]" kiteconnect sqlalchemy alembic pydantic-settings apscheduler structlog httpxuv add --dev pytest pytest-asyncio hypothesis ruff mypy pandascd ..npm create vite@latest frontend -- --template react-tscd frontend ; npm install ; npm install @tanstack/react-query @tanstack/react-table zustand lightweight-charts recharts tailwindcss @tailwindcss/vite react-router-dom

7.3 IntelliJ IDEA setup

Use IntelliJ IDEA Ultimate (it includes Python and JavaScript/TypeScript support). On Community Edition you must install the Python Community plugin and edit the frontend in another editor.

Open the renko-trader folder. File → Project Structure → SDKs → add the interpreter backend\.venv\Scripts\python.exe.

Mark backend\app as a sources root and backend\tests as a test root.

Add run configurations: (a) Uvicorn: module uvicorn, parameters app.main:app --reload --port 8000, working directory backend; (b) pytest on backend\tests; (c) npm script dev in frontend.

Turn on ruff as the formatter (Settings → Tools → External Tools, or the Ruff plugin) so Codex output is formatted the same way as yours.

Set the environment variable TZ=Asia/Kolkata in every run configuration.

7.4 Using Codex without losing control

Create AGENTS.md in the repo root with the rules below; Codex reads it before every task.

Give Codex one module per task (section 21 has the prompts), never "build the whole app".

Ask for tests with every module and run pytest yourself before accepting.

Commit after every accepted task so any bad change can be reverted.

Never paste real API keys into a prompt.

Suggested AGENTS.md content:

# Rules for this repository- Python 3.12, type hints everywhere, ruff + mypy clean.- The `indicator` package is pure: no network, no database, no broker imports.- Port Pine logic literally. Do not "improve" it. Name Python variables after the Pine ones.- All times are Asia/Kolkata aware datetimes; the database stores UTC.- Never hard-code lot size, expiry, strike gap or holidays; read them from data.- Any code path that sends a real order must go through execution/order_manager.py and check mode == LIVE and armed == True.- Every module ships with pytest tests; parity tests use fixtures from backend/tests/fixtures.- Secrets only from environment variables; never log tokens.

7.5 Kite developer account

Sign up at the Kite developer portal, choose the paid Connect plan, create an app.

Redirect URL: http://127.0.0.1:8000/api/auth/kite/callback (your backend receives the login result here).

Static IP: enter it in the app settings when you reach live trading (section 17); leave it empty during paper trading.

Put KITE_API_KEY and KITE_API_SECRET in backend\.env; confirm .env is listed in .gitignore before the first commit.

7.6 Windows machine hygiene for a trading process

Set Windows time sync to on and the time zone to India Standard Time.

Power plan: never sleep while plugged in; disable automatic restart for updates during market hours (09:00–15:30 IST).

Run the backend as a service with NSSM so it restarts after a crash, with logs in backend\logs.

Back up the database file and .env (encrypted) every evening to a second drive or cloud folder.

8. Market data layer (Kite Connect)

Every input the Pine script reads must come from Kite, and the indicator must be warmed up with enough history before the first live brick. Limits quoted below are from memory of the Kite docs; verify each against the current Kite Connect documentation before coding.

8.1 What data is needed and where it comes from

Pine input

Kite source

Frequency

Notes

Renko price

NIFTY 50 spot index ticks via WebSocket

Per tick

Backfilled from 1-minute historical candles

Day open, previous close, previous-day high/low, today high/low

Daily historical candles + live tick ohlc

Daily + per tick

Replaces request.security(..., "D")

5-minute futures close, VWAP, volume

Candles built from futures ticks

5 min

VWAP resets each session; volume from cumulative traded volume differences

Futures open interest

Tick field oi in full mode; oi=True in historical calls

5 min

Replaces TradingView's _OI symbol

Option premiums for the legs

Option ticks

Per tick

Only for traded and candidate strikes

Lot size, tick size, expiry list

Instruments dump (NFO)

Daily 08:50

Stored in the instruments table

8.2 Daily login flow (Kite tokens expire every day)

Dashboard shows "Kite: login needed" with a Login button after 06:00 IST.

Button opens the Kite login URL for your API key; you sign in with your password and TOTP.

Kite redirects to /api/auth/kite/callback?request_token=....

The backend exchanges the request token and API secret for an access token, stores it encrypted with its expiry, and starts the market-data worker.

The status chip turns green. A job at 08:45 IST warns you (dashboard banner, later Telegram) if login is still missing.

Automating the password and TOTP step is not recommended: it conflicts with the broker's intended login flow and can put your account at risk.

8.3 Live ticks

Use KiteTicker in full mode for the futures contract (gives price, volume, OI, exchange timestamp); quote or LTP mode for option legs.

Subscribe at start: index token (drives Renko) and futures token (volume, OI, flow). Subscribe to option tokens when a trade is planned and for the candidate strikes shown on the Live tab.

A tick handler must do almost nothing: push the tick onto an asyncio queue and return. The Renko builder and indicator run in a separate consumer task.

On disconnect: reconnect with exponential backoff (1, 2, 4, 8 up to 30 seconds), resubscribe every token, then fetch the missed minute candles from the historical API and replay them through the builder.

8.4 Warm-up and backfill (so Python equals TradingView on day one)

On start, load the last N trading days of 1-minute futures candles (default N = 20; Kite limits minute data to a rolling window per request, so fetch in chunks and stitch).

Feed them through the Renko builder to rebuild the brick list, then run every brick through the full indicator engine with trading disabled. This restores Supertrend, RSI, swing tops/bottoms, divergence state, outlook statistics and the direction bias.

Only after the last historical brick, enable live mode. Entries are blocked for the first minute after warm-up to avoid acting on a half-formed state.

Store the rebuilt bricks in the bricks table; later restarts load them from the database and only backfill the gap.

8.5 Data quality guards

Stale-feed watchdog: no tick for 5 seconds between 09:15 and 15:30 raises a red banner and blocks new entries.

Drop ticks with a timestamp earlier than the last accepted one; log them.

Compare the backend clock with exchange timestamps; warn if the drift is over 2 seconds.

Respect rate limits (historical data is about 3 requests per second, general REST about 10 per second): wrap all REST calls in one rate-limited client.

Maintain a holiday table (market_holidays) updated yearly from the NSE calendar; the scheduler skips closed days.

8.6 Open data questions to settle in week 1

Does TradingView's NIFTY1! OI series match Kite's futures OI minute by minute? Export both for one day and compare. If they differ, tune the OI thresholds (section 10, flow) on Kite data rather than copying TradingView numbers.

Your Renko chart uses the spot index (confirmed, decision D2), so bricks come from the NIFTY 50 index token; still read one real brick close to set the anchor (section 9.2).

9. Renko engine specification

The Renko builder is the foundation: if its bricks differ from TradingView's by even one, every signal after that point can differ. Build it first, test it hardest, and prove it brick by brick against a TradingView export.

9.1 Rules (traditional Renko, box size B = 50)

A brick is a fixed-size block; it has no time dimension and no wick (high = max(open, close), low = min(open, close)). Confirm the no-wick assumption on your chart export.

Continuation: after an up brick closing at C, a new up brick forms when price reaches C + B. After a down brick closing at C, a new down brick forms when price reaches C − B.

Reversal: after an up brick (open O, close C = O + B), a down brick forms only when price reaches O − B, that is C − 2B. After a down brick, an up brick forms at O + B, that is C + 2B.

A big price jump creates several bricks in one step, all with the same timestamp.

Boundary is inclusive: price exactly equal to the trigger forms the brick.

Bricks continue across days; there is no daily reset.

9.2 The grid anchor (the easily missed detail)

TradingView positions the brick grid from the first bar of the history it loaded, so brick levels are not always multiples of 50. The builder therefore takes an anchor_price: every brick open/close equals anchor_price + k × B. Read one real brick close from your TradingView chart, set anchor_price = that close, and the grids will coincide. If your chart shows closes like 24,025 and 24,075 the anchor is 25 mod 50.

9.3 Reference implementation (pseudo-code)

@dataclass(frozen=True)class Brick:    index: int    open: float    close: float    direction: int        # +1 green, -1 red    ts: datetime          # IST time of the tick that completed it    volume: floatclass RenkoBuilder:    def __init__(self, box: float, anchor: float):        self.box, self.anchor = box, anchor        self.last: Brick | None = None        self.index = 0    def on_price(self, price: float, ts: datetime) -> list[Brick]:        out: list[Brick] = []        if self.last is None:            # seed: snap price down to the grid, no brick yet            self._base = self.anchor + math.floor((price - self.anchor) / self.box) * self.box            self.last = Brick(-1, self._base, self._base, 0, ts, 0)        while True:            last = self.last            up_trigger   = last.close + self.box if last.direction >= 0 else last.open + self.box            down_trigger = last.close - self.box if last.direction <= 0 else last.open - self.box            if price >= up_trigger:                o = last.close if last.direction >= 0 else last.open                new = Brick(self.index, o, o + self.box, +1, ts, 0)            elif price <= down_trigger:                o = last.close if last.direction <= 0 else last.open                new = Brick(self.index, o, o - self.box, -1, ts, 0)            else:                return out            self.index += 1; self.last = new; out.append(new)

The seed case (direction == 0) must be handled so the first brick can go either way; add a test for it.

9.4 Two build modes (setting renko_mode)

Mode

Input

Matches

Trade-off

minute_close (default)

Close of each completed 1-minute candle

TradingView historical Renko built on a close source

Up to 60 seconds later than a tick; stable; no brick that appears and then vanishes

tick

Every tick

Fastest reaction

A brick can form on a spike and be undone within the same minute on TradingView; use only after comparing a full day

Start with minute_close, compare against TradingView for one week, and only then test tick.

9.5 Edge cases and their tests

Case

Expected behaviour

Gap open of 3 boxes

Three bricks, same timestamp, in order

Reversal gap of 4 boxes after an up brick

One reversal brick at 2B, then continuation bricks to the target

Price exactly on trigger

Brick forms

Duplicate or older-timestamp tick

Ignored, logged

Restart in the middle of the day

State rebuilt from stored bricks, then missed minutes replayed

Weekend or holiday gap

No bricks until price reaches a trigger; no reset

Anchor changed in settings

Existing bricks flagged invalid; rebuild required

9.6 How to prove parity

In TradingView, open the Renko chart and use Export chart data for the last 10 trading days.

Run python -m app.tools.parity_check renko --csv export.csv --anchor <close>.

The tool replays 1-minute candles, builds bricks and prints the first mismatch (index, expected, got). Target: zero mismatches over 10 days.

Keep the CSV in tests/fixtures/ as a permanent regression test.

10. Indicator port: module-by-module specification

Port the Pine script literally, one concern per file, with the Pine variable names kept in the Python code so you can read both side by side. The engine is a pure function of the brick stream: engine.on_new_brick(brick, market_ctx) -> IndicatorResult.

10.1 Module map

Python module

Pine part

What it must do

Parity watch-out

maths.py

ta.rsi, ta.atr, ta.supertrend, ta.crossover/under, ta.barssince, math.sum

Exact Pine formulas (Wilder RMA, seeded with an SMA of the first N values)

Wrong seeding makes RSI differ for dozens of bricks

state.py

All var variables

One dataclass holding lastTopP/R/I, prevTopP, lastBotP/R/I, prevBotP, lastDivDir/Bar, lastHidDir/Bar, orH/orL, orbUpSeen/DnSeen, trap levels and bars, srgArm, coreDone, lastSig*, trade fields, statistics arrays

Must be serialisable so a restart can resume

divergence.py

Divergence engine

topForm (green→red), botForm (red→green); equal/higher price rules with half = box/2; RSI gap; HDIV; forming flags

Uses close[1] and rsi[1] of the previous brick as the swing

flow.py

Flow engine

f_build, window and day build-up, VWAP side, volume spike, day side, flow score

Inputs come from the 5-minute futures series, aligned to the brick time

outlook.py

Outlook engine

Run length, aligned flag, 12 buckets of continue/total counts, average run, remaining bricks, upTrig/dnTrig, stretch, nearest ceiling/floor

Counts update once per confirmed brick, using the previous bucket

bias.py

Direction engine

The 10 factors, score, hysteresis, strong flag, reversal watch

Order of assignments matters because biasDir is persistent

signals.py

Signal engine

Raw conditions for 8 types, priority, cooldown, ORB window, BRK age, TRAP expiry, SRG arming

CORE resets on every Supertrend flip

grading.py

f_grade, f_riskN, f_riskLbl

Strength 1–3, risk Low/Medium/High, late-entry check

Late-entry uses brick timestamps (time[i] >= time − 15 min)

trade_plan.py

Trade engine

Exit-then-entry order, T1/T2, opposite-brick counter, optional safety exit, statistics per family

EXIT only after the entry brick, on a confirmed brick

texts.py

Tooltip builders

Same explanatory strings, returned as structured fields for the UI

Cosmetic; port last

engine.py

Main script body

Runs the modules in the order of section 3.1 and returns one result object

Deterministic: same bricks in, same result out

10.2 Core maths (reference)

def rma(values, length):                 # Pine ta.rma    out, prev = [], None    for i, v in enumerate(values):        if i < length - 1:   out.append(None); continue        if i == length - 1:  prev = sum(values[:length]) / length        else:                prev = (prev * (length - 1) + v) / length        out.append(prev)    return outdef true_range(h, l, prev_close):        # first bar: h - l    return h - l if prev_close is None else max(h - l, abs(h - prev_close), abs(l - prev_close))# Supertrend step (official Pine definition), called once per brick:#   src = hl2; upper = src + factor*atr; lower = src - factor*atr#   lower = lower if (lower > prev_lower or prev_close < prev_lower) else prev_lower#   upper = upper if (upper < prev_upper or prev_close > prev_upper) else prev_upper#   if atr_prev is None:            direction = 1#   elif prev_st == prev_upper:     direction = -1 if close > upper else 1#   else:                           direction = 1 if close < lower else -1#   st = lower if direction == -1 else upper        # direction -1 means UP-trend

In production the indicator keeps running values (previous RMA, previous bands) instead of recomputing lists, so each brick costs constant time.

10.3 The result object sent to the rest of the system

@dataclassclass IndicatorResult:    brick: Brick    supertrend: float; is_up: bool; rsi: float    bias: Bias              # score, direction (+1/0/-1), strong, parts{10 factors}, reversal_watch    signal_long: Signal | None   # type, grade (1-3), risk, family (CO/DIV/OT), reason text    signal_short: Signal | None    events: list[TradeEvent]     # ENTRY / T1 / EXIT with id, price, pct, reason    position: PositionState | None   # indicator's own hypothetical trade (entry, T1, T2)    levels: Levels          # ceiling, floor, next green/red trigger    flow: FlowSnapshot | None

The indicator keeps its own hypothetical trade (the Pine trade engine) so its ENTRY/EXIT events match TradingView exactly. The option trade in section 11 is driven by those events but is a separate object.

10.4 Porting order (each step ends with a passing test)

maths.py with unit tests against hand-checked values and a TradingView export of RSI and Supertrend.

State dataclass and the Renko-to-engine loop with a no-op engine.

Supertrend + CORE signal + trade engine (first full ENTRY/EXIT cycle).

Divergence and HDIV.

PB, BRK, TRAP.

Bias, grading, risk.

ORB and session handling.

Flow engine and SRG (needs the 5-minute futures series).

Outlook and statistics, then texts.py.

After steps 3, 5, 6 and 8 run the full parity check from section 18; do not move on until it passes.

11. Option-selling strategy layer

The indicator says which way the index will move; the strategy layer turns that into a hedged option-selling position, decides when to leave, and refuses trades that break your limits. Everything here is a setting, so you can tune it in paper mode without changing code.

11.1 From signal to trade

Indicator event

Meaning

Option action (default structure)

CO / DIV / OT BUY ENTRY

Bullish: market expected to rise or hold

Bull put spread: sell a PE, buy a lower PE

CO / DIV / OT SELL ENTRY

Bearish: market expected to fall or hold

Bear call spread: sell a CE, buy a higher CE

Matching EXIT

First closed opposite-colour brick, or Target 2

Close both legs

Opposite ENTRY while in a trade

Indicator exits first, then enters

Close the old spread, then open the new one

T1 reached

Information only

Show on dashboard; optional trailing rule (off by default)

Entry filters (all configurable):

Allowed families: CO, DIV, OT (default all three).

Minimum strength: Moderate (matches the Pine filter); can be raised to Strong.

Trading window: 09:30 to 14:45 IST; no new entries outside it.

Maximum new trades per day: 3. Maximum open trades: 1.

Skip when the indicator marks risk as High, or when the dashboard direction contradicts the signal (switchable).

11.2 Structure options

Option

Legs

Max loss

Margin

Default

A. Credit spread

Sell 1 near-the-money option, buy 1 further OTM option

Known (width − credit)

Low

ON

B. Naked short

Sell 1 option only

Large and open-ended

High

OFF; needs an explicit setting and a typed confirmation

C. Short strangle / straddle

Both sides

Open-ended

High

Not in v1

11.3 Strike and expiry selection

Read strike_step and lot_size for the underlying from the instruments table (NIFTY normally 50 points).

Spot reference = the signal brick close. ATM = round(spot ÷ step) × step.

Short strike = ATM moved short_offset_steps away from spot in the favourable direction (default 1 step OTM). For BUY: the PE strike at or below ATM; for SELL: the CE strike at or above ATM.

Hedge strike = short strike moved hedge_width_steps further OTM (default 4 steps, 200 points). Alternative mode: choose the strike whose premium is closest to a target (for example ₹5–10 for the hedge).

Expiry = nearest weekly expiry from the instruments file. Expiry-day policy setting: skip, trade_current or trade_next (default trade_next after 12:00 on expiry day).

Liquidity check on both strikes: bid-ask spread at most 2% of price (or ₹1), and minimum open interest. If it fails, move one step and retry; after two retries, skip and log the reason.

11.4 Order sequence

Entry: buy the hedge first, then sell the short leg. Closing: buy back the short first, then sell the hedge. This keeps margin low and risk bounded at every moment.

Use limit orders at last price plus or minus a small buffer, modify after a few seconds if unfilled, and fall back to the broker's protected market order only if your setting allows it. Check the current exchange and Zerodha rules on market orders for options before enabling that fallback.

Every order carries a unique tag (RT-<tradeId>-<leg>) so it can be found again after a crash.

If one leg fills and the other fails, the trade state becomes PARTIAL and the system automatically unwinds the filled leg and raises an alert.

11.5 Exit rules for the option trade (first one hit wins)

Kill switch pressed, or daily loss limit hit: close everything.

Indicator EXIT event for that trade (opposite closed brick, or Target 2).

Premium stop-loss: spread value has lost 50% of the maximum possible loss (setting sl_pct_of_max_loss).

Optional profit capture: spread has kept 70% of the credit (setting; off by default because the indicator exit usually comes first).

Time exit: 15:15 IST, before the broker's own 15:20 auto-square-off.

11.6 Position sizing

fixed_lots mode (default): lots = value in Settings, for example 1.

risk_pct mode: lots = floor(risk per trade ÷ max loss per lot), with risk per trade as a percentage of available capital.

Before every entry the system checks funds (wallet balance in paper; Kite margin API in live) and refuses the trade if margin is short.

11.7 Trade state machine

State

Meaning

Moves to

PLANNED

Signal accepted, strikes and quantity chosen

SENDING, REJECTED

SENDING

Hedge sent, then short leg

OPEN, PARTIAL

OPEN

Both legs filled; P&L streaming

CLOSING

CLOSING

Exit reason recorded, closing orders sent

CLOSED, PARTIAL

PARTIAL

One leg filled; auto-unwind running

CLOSED, FAILED

CLOSED

All legs flat; realised P&L stored

—

REJECTED / FAILED

Filter, margin, or order failure; reason stored

—

11.8 Costs in P&L

Store gross P&L and costs separately. The cost model (brokerage per order, STT, exchange charges, GST, SEBI and stamp charges) is a settings table with rates you fill from Zerodha's current brokerage calculator, so paper and live numbers are comparable.

11.9 What you must validate before real money

The indicator's targets are percentages of the index, but option spreads earn from time decay and lose on sharp moves, so index accuracy does not translate one-to-one into spread profit. Run at least four weeks in paper mode and compare, per signal family, the win rate, average win, average loss and worst day before enabling live trading.

12. Execution engine, Paper vs Live, and risk controls

Paper and Live share one decision path: the strategy layer builds a single trade plan (legs, strikes, quantity, exits), and only the last step, which broker receives the orders, differs. That is how the position stays identical in both modes.

12.1 The shared path

Indicator event → strategy layer → TradePlan (mode-agnostic, stored with a decision_id).

Risk gate checks the plan (section 12.4). Rejected plans are stored with the reason.

Order manager hands the plan to the active broker: PaperBroker or LiveBroker, both implementing the same interface.

Fills update the Position book; the position manager streams live P&L and applies exit rules.

Closed trades are written to history with entry, exit, costs and net P&L.

class Broker(Protocol):    async def place_order(self, order: OrderRequest) -> OrderAck: ...    async def modify_order(self, order_id: str, price: float) -> OrderAck: ...    async def cancel_order(self, order_id: str) -> None: ...    async def order_status(self, order_id: str) -> OrderStatus: ...    async def positions(self) -> list[BrokerPosition]: ...    async def funds(self) -> Funds: ...

12.2 Mode switch behaviour (your two buttons)

Situation

Paper button

Live button

What happens

App start

Selected

Available

Always starts in Paper, whatever it was yesterday

Click Live, no open trade

Becomes available

Opens a confirm dialog

Checks Kite login, static IP, funds, no kill switch; you type LIVE to arm

Live armed

Disabled while a live trade is open

Selected (red frame)

Header shows a red LIVE badge; orders go to Kite

A trade is open

Both disabled

Both disabled

Tooltip: "Close the open trade first"; a Close now button is shown

Trade closed

Both enabled again

Both enabled

You can switch

Any error in Live (login lost, reconciliation mismatch)

Auto-selected

Disabled

System falls back to Paper, blocks entries and raises an alert

Same position in both books: with the setting shadow_paper = on (default), every Live trade also runs as a paper trade from the same TradePlan. The History tab can show Paper, Live or Both, and a slippage report compares the two fills for the same signal.

12.3 Paper broker fill model

Market order: fills at best ask for a buy, best bid for a sell (from the full-mode depth of the option tick); falls back to last price ± slippage points.

Limit order: fills when the last price touches the limit, with an optional 500 ms latency.

Order ids start with P- so they can never be confused with Kite ids.

Paper funds come from the dummy wallet (section 16); margin is estimated per spread as max loss plus a configurable buffer.

12.4 Risk gate (applies to both modes; every check writes a reason on failure)

Control

Default

Behaviour

Daily loss limit

2% of capital

Close all, block entries until next day

Max loss per trade

1% of capital

Reject plans whose max loss exceeds it

Max trades per day

3

Block extra entries

Max open trades

1

Block extra entries

Trading window

09:30–14:45 entries; 15:15 square-off

Enforced by the scheduler

Stale data

No tick for 5 s

Block entries, keep exit rules running

Price sanity

Order price within 5% of last price

Reject otherwise (fat-finger guard)

Duplicate guard

Same decision_id never executes twice

Idempotent orders

Manual confirm (Live)

ON for the first weeks

Dashboard asks "Place this trade?" with a 30-second timer

Kill switch

Big red button + POST /api/kill

Cancels pending orders, closes all legs, switches to Paper

12.5 Reconciliation and crash recovery

Live: every 30 seconds compare the Position book with Kite positions. A mismatch blocks entries and raises a red alert; it never auto-fixes silently.

Order status is polled every second until complete (a postback webhook can replace polling once you have a public HTTPS address).

On startup: load open trades from the database, reconcile with the broker (Live) or reload the paper book, resume exit monitoring, then connect market data.

Every state change is written to the database before the next action is taken, so a crash never loses a trade.

12.6 Settings audit

Every change to mode, limits or strategy settings is stored with time, old value, new value and who changed it. The audit table is append-only.

13. Database schema

Twenty-one tables cover everything the dashboard shows; every user-owned table carries user_id so adding a second user is data, not a redesign. Money columns are NUMERIC(14,2), times are stored in UTC and shown in IST, and ids are 64-bit integers.

13.1 Market and indicator data

Table

Key columns

Purpose

instruments

token (PK), exchange, tradingsymbol, name, expiry, strike, instrument_type, lot_size, tick_size, loaded_on

Daily Kite dump; source of lot size, expiries and strikes

bricks

id, symbol, idx, open, close, direction, ts, volume, anchor, mode; unique (symbol, idx)

Rebuilt and live Renko bricks

fut_candles_5m

symbol, ts, open, high, low, close, volume, oi; unique (symbol, ts)

Flow-engine input

indicator_snapshots

brick_id (PK), bias_score, bias_dir, strong, rsi, supertrend, is_up, flow_score, details_json

One row per brick; feeds the Live tab and replay

signals

id, brick_id, type, family (CO/DIV/OT), direction, grade, risk, reason, accepted, reject_reason

Every signal, including ones that were filtered out

indicator_trades

id, trade_code, family, direction, entry_brick, entry_price, exit_brick, exit_price, pct, t1_hit, t2_hit, exit_reason

The Pine hypothetical trades; used for parity and statistics

market_holidays

date (PK), name

Scheduler skips these days

13.2 Trading

Table

Key columns

Purpose

trade_plans

id, decision_id (unique), signal_id, structure, underlying, expiry, legs_json, lots, credit, max_loss, created_at

Mode-agnostic plan; one per accepted signal

trades

id, user_id, mode (PAPER/LIVE), plan_id, trade_code, family, direction, state, opened_at, closed_at, entry_credit, exit_debit, gross_pnl, costs, net_pnl, pnl_pct_margin, pnl_pct_capital, exit_reason, shadow_of

One row per executed trade per mode; shadow_of links the paper twin of a live trade

trade_legs

id, trade_id, role (SHORT/HEDGE), token, tradingsymbol, side, qty, entry_price, exit_price, entry_time, exit_time

The legs of a trade

orders

id, trade_id, leg_id, mode, broker_order_id, tag, side, order_type, qty, price, status, placed_at, updated_at, raw_json

Every order and its status history

fills

id, order_id, qty, price, ts

Partial fills supported

pnl_ticks

trade_id, ts, mtm

Open-trade P&L sampled once a minute for the equity curve

daily_pnl

user_id, mode, date, trades, wins, gross, costs, net, pct_capital, capital_start; unique (user_id, mode, date)

Feeds weekly and monthly totals

13.3 Wallet, settings, operations

Table

Key columns

Purpose

users

id, name, email, role, created_at

One or two users now

settings

user_id, key, value_json, updated_at

Strategy, risk, Pine inputs, display

audit_log

id, ts, user_id, action, old_json, new_json

Append-only change history

broker_sessions

id, user_id, broker, access_token_enc, expires_at, created_at

Encrypted Kite token

wallet_accounts

id, user_id, name, currency, balance, created_at

Dummy-money account (section 16)

wallet_ledger

id, account_id, ts, type (DEPOSIT / WITHDRAW / PNL / COST / RESET), amount, balance_after, trade_id, note

Every rupee movement

alerts

id, ts, level, source, message, acknowledged

Dashboard alert feed

13.4 Indexes that matter

trades (user_id, mode, closed_at DESC) for History.

daily_pnl (user_id, mode, date) for period totals.

bricks (symbol, idx) and signals (brick_id) for replay.

orders (broker_order_id) and orders (tag) for reconciliation.

13.5 Weekly and monthly totals

Store only daily rows; compute the rest with a query so numbers can never disagree:

SELECT date_trunc('month', date) AS month,       SUM(net) AS net_pnl,       SUM(trades) AS trades,       SUM(wins)::float / NULLIF(SUM(trades),0) AS win_rate,       SUM(net) / MAX(capital_start) * 100 AS pct_of_capitalFROM daily_pnlWHERE user_id = :u AND mode = :mGROUP BY 1 ORDER BY 1 DESC;

(For weeks use date_trunc('week', date). SQLite uses strftime; SQLAlchemy hides the difference.)

13.6 Retention

Keep bricks, snapshots, signals, trades and orders forever (small volume). Keep pnl_ticks for 90 days. Back up daily.

14. Backend API

The dashboard talks to the backend through plain REST for actions and history, and one WebSocket for everything that moves. FastAPI publishes the full contract at /docs, and the front-end client is generated from it so the two sides cannot drift apart.

14.1 REST endpoints

Area

Method and path

Purpose

Auth

POST /api/login

Dashboard password → session cookie (JWT)

Kite

GET /api/auth/kite/login-url, GET /api/auth/kite/callback, GET /api/auth/status

Daily Kite login and connection status

Mode

GET /api/mode, POST /api/mode

Read or switch PAPER / LIVE; Live needs {mode:"LIVE", confirm:"LIVE"}

Live

GET /api/live/snapshot, GET /api/bricks?limit=300

Everything the Live tab needs on first load

Trading

GET /api/positions/open, POST /api/trades/{id}/close, POST /api/kill, POST /api/decisions/{id}/confirm

Open positions, manual close, kill switch, manual confirm

History

GET /api/trades, GET /api/trades/{id}, GET /api/export/trades.csv

Filter by date range, mode, family (CO/DIV/OT), direction, result; paging; CSV

P&L

GET /api/pnl/summary?period=day|week|month&mode=, GET /api/pnl/daily, GET /api/stats/by-family

Totals in rupees and percent; chart series; win rate by signal family

Signals

GET /api/signals

Signal feed including filtered-out signals with reasons

Wallet

GET /api/wallet, POST /api/wallet/deposit, POST /api/wallet/withdraw, POST /api/wallet/reset

Dummy money (section 16)

Settings

GET /api/settings, PUT /api/settings, POST /api/settings/preview-strikes

All Pine and strategy inputs; preview shows strikes for the current spot

System

GET /api/health, GET /api/alerts, POST /api/alerts/{id}/ack

Feed lag, token expiry, alerts; the TradingView shadow-check webhook is POST /api/shadow/tv-alert (section 18.3)

Dev only

POST /api/dev/replay

Replay a stored day through the engine (disabled in Live)

14.2 WebSocket /ws/live

The server pushes JSON messages with a type field; the browser never polls. Ticks are throttled to 4 per second.

type

Sent when

Main fields

tick

Price moves

ltp, ts, to_next_green, to_next_red

brick

A new brick closes

brick, indicator (supertrend, rsi, bias, signals), markers

signal

A signal is accepted or rejected

code (e.g. CO-BUY-ENTRY), grade, risk, reason, accepted

trade_event

Entry, T1, exit, state change

trade_id, event, price, mode

position

Every second while a trade is open

legs with live prices, mtm, pnl_pct, to_t1, to_t2

status

On change and every 5 s

kite, feed_lag_ms, mode, armed, kill, market_open

alert

Anything needing attention

level, message

Example messages:

{"type":"brick","brick":{"idx":4812,"open":24100,"close":24150,"dir":1,"ts":"2026-10-23T10:42:05+05:30"}, "indicator":{"supertrend":24020.5,"is_up":true,"rsi":61.2,   "bias":{"dir":1,"score":7,"strong":false}}, "markers":[{"kind":"ENTRY","code":"CO-BUY-ENTRY","id":"[K7M2Q]","price":24150}]}{"type":"position","trade_id":931,"mode":"PAPER","state":"OPEN", "legs":[{"role":"SHORT","symbol":"NIFTY26OCT24100PE","qty":75,"entry":88.5,"ltp":81.0},         {"role":"HEDGE","symbol":"NIFTY26OCT23900PE","qty":75,"entry":9.5,"ltp":8.0}], "mtm":468.75,"pnl_pct_margin":1.4,"to_t1":412.0,"to_t2":812.0}

(Symbols and quantities above are illustrative; real values come from the instruments file.)

14.3 Conventions

All times are ISO-8601 with the +05:30 offset; amounts are numbers in rupees; percentages are numbers (1.4 means 1.4%).

Errors use one shape: {"error":{"code":"RISK_DAILY_LOSS","message":"..."}} with the right HTTP status.

Every mutating endpoint requires the session cookie and is written to audit_log.

The API listens on 127.0.0.1 only in v1. Remote access later goes through a reverse proxy with HTTPS (section 17).

15. Frontend: screens, tabs and components

A dark, dense trading dashboard with four tabs (Live, History, Wallet, Settings), a permanent top bar, and one WebSocket feeding everything on screen. Figures use Indian grouping (₹12,34,567.50) and all times show IST.

15.1 Top bar (visible on every tab)

Element

Behaviour

Underlying and last price

NIFTY FUT 24,150.50, flashes green/red on change

Connection chips

Kite (green / red + Login button), Feed lag in ms, Market open/closed

Mode switch

Segmented control `Paper

Wallet chip

Dummy wallet ₹10,00,000  [+ Add]: the quick way to add unlimited virtual money from any page (Paper mode only; in Live it shows real Kite funds, read-only)

Kill switch

Red button with a confirm dialog

Clock

IST time and date

15.2 Tab 1: Live

Left side (about two thirds): the Renko chart. Right side: cards for direction, the active trade, the last closed trade and today.

Component

What it shows

Renko chart

Bricks as green/red blocks without wicks; Supertrend line coloured by trend; light green/red tint by direction bias; markers ▲ CO-BUY-ENTRY [K7M2Q] and ✖ CO-BUY-EXIT [K7M2Q] with the same trade ID; dashed lines for entry, Target 1, Target 2 of the active trade; optional lines for ceiling, floor and next-brick triggers. Hover a marker for the full explanation (what it means, why now, be careful, targets).

Chart toolbar

Toggles for Supertrend, markers, tint, levels, next-brick lines; zoom to last 100 / 300 bricks

Direction card

▲ BULLISH · Strong · score +9 with a "Why" expander listing the ten factors that agree and disagree

Active position card

Strategy (for example Bull put spread), both legs with strike, quantity, entry price, live price; live P&L in ₹ and %; distance to Target 1 / Target 2 on the index; stop-loss level; time in trade; Close now button

Last closed trade card

Exit time, exit reason (opposite brick, Target 2, stop, time, manual), realised P&L in ₹ and %, shown until the next trade opens

Today card

Trades, wins, net P&L ₹ and %, daily-loss limit used (progress bar)

Signal feed

Newest first: time, code, grade dots, risk, accepted or rejected with the reason

Alerts strip

Feed stale, reconciliation mismatch, login expiring, limit reached

Percent definitions shown in tooltips: % of margin = net P&L ÷ margin used by the trade; % of capital = net P&L ÷ start-of-day wallet balance.

15.3 Tab 2: History

Summary cards: Today, This week, This month, All time, each with net ₹, % of capital, trades and win rate.

Charts: daily net P&L bars with a cumulative line; monthly bars.

Weekly and monthly tables: period, trades, wins, gross, costs, net ₹, net %, best and worst trade.

Filters: date range, mode (Paper / Live / Both), family (CO / DIV / OT), direction, result, strength.

Trade table (sortable, paged, CSV export). Columns: Date, Day, Month, Year, In time, Out time, Mode, Signal code + trade ID, Direction, Strategy, Short strike, Hedge strike, Lots, Index entry, Index exit, Entry credit, Exit debit, Gross ₹, Costs ₹, Net ₹, Net %, Exit reason, Duration.

Row expand: legs and fills, order timeline, the indicator's explanation text for the signal, and a small chart of the trade.

15.4 Tab 3: Wallet (dummy money)

Balance, an amount box with Add and Withdraw buttons (no upper limit), a Reset-to-amount button, and the full ledger (deposits, P&L credits and debits, costs). Details in section 16. The wallet chip in the top bar is the shortcut to the same function.

15.5 Tab 4: Settings

Grouped forms with the same names as your Pine inputs: Supertrend, Direction and signals, Trade plan, Divergence, Extra signals, Flow engine, Outlook; then Strategy (structure, strikes, expiry policy, sizing), Risk limits, Data (Renko mode, anchor), and Display. Every field has a tooltip copied from the Pine tooltip. Buttons: Save, Reset to defaults, Export / Import JSON, Preview strikes now. Saving writes to the audit log; dangerous changes (naked selling, larger limits) need a typed confirmation.

15.6 Frontend technical notes

One useLiveSocket() hook with automatic reconnect; a store (Zustand) holds the latest tick, bricks, position and status; components subscribe to slices to avoid re-rendering the chart on every tick.

Lightweight Charts: use a candlestick series with wick colour equal to body colour; markers via the series marker API (text carries the code and ID); price lines for entry and targets; Supertrend as two line series (up colour, down colour) or one coloured line.

Initial load: GET /api/live/snapshot, then apply WebSocket messages; on reconnect, request the snapshot again so nothing is missed.

Accessibility and comfort: colour-blind-safe alternative palette in Display, optional sound on signal and exit, browser notifications.

16. Dummy wallet (virtual money)

The wallet is an accounting ledger used only in Paper mode: you can add any amount at any time, and every paper trade moves the balance exactly as real money would, so profit, loss and percentages are meaningful.

16.1 Rules

Rule

Behaviour

Starting balance

₹10,00,000 (setting)

Add money

Any positive amount, no upper limit (stored up to ₹999,999,999,999.99), from the top bar or the Wallet tab

Withdraw

Allowed up to the free balance (balance minus blocked margin)

Reset

Sets the balance to a chosen amount and writes a RESET ledger line; paper trades stay unless you tick "also delete paper history" (two confirmations)

Blocked margin

When a paper trade opens, its maximum loss plus a buffer (default 20%) is blocked; it is released at close

Not enough free money

Trade rejected with reason "insufficient wallet", or automatically topped up if auto_topup is on

Unlimited mode

Setting auto_topup = on adds the exact shortfall as a DEPOSIT line, so you never get rejected for funds but still see how much was needed

Live mode

The wallet is not used. The chip shows your real Kite funds, read-only, so dummy and real money can never mix

16.2 Ledger lines

Type

Written when

Effect on balance

DEPOSIT

You add money, or auto top-up

+ amount

WITHDRAW

You withdraw

− amount

PNL

A paper trade closes

+ gross P&L

COST

A paper trade closes

− estimated charges

RESET

You reset the wallet

Balance set to the new amount

Check formula: balance = deposits − withdrawals + sum of gross P&L − sum of costs (reset lines start a new baseline). A nightly job verifies it and raises an alert if it ever fails.

16.3 Percentages

Capital base for daily, weekly and monthly percentages = wallet balance at the start of the period, including deposits made before that period.

Deposits during a period are excluded from P&L; only PNL and COST lines count.

Each trade also stores % of margin used, so you can judge return on the capital the trade actually needed.

17. Security, compliance and company policy

Three things can hurt you more than a bad strategy: a leaked broker key, an order that should not have gone out, and a rule you did not know applied. This section closes all three.

17.1 Company policy check (do this before writing code)

Your organisation instructions point to the Springer Nature Technology and Information Use policy. I could not open it (it sits behind an internal login), so I have not checked it against this project. Before you start, read it for: personal projects on company laptops or networks, installing software, storing broker credentials, using company internet or IP addresses for trading, and use of AI coding tools with any company data. The safe default is a personal computer, personal network and personal accounts, and never pasting company information into Codex or any AI tool.

17.2 Secrets and access

Item

Rule

Kite API key and secret

In .env only; file excluded from Git; never printed in logs or sent to Codex

Kite access token

Stored encrypted (Fernet key held in an environment variable or Windows Credential Manager); deleted at expiry

Dashboard login

One password, hashed with Argon2; session cookie HttpOnly, SameSite=Strict; lock after 5 failed attempts

Network exposure

API bound to 127.0.0.1 in v1. For remote access use a reverse proxy with HTTPS and an IP allow-list, never an open port

Zerodha and TradingView accounts

Two-factor authentication on, strong unique passwords, no shared logins

Logs

Redact tokens, keys and account numbers; rotate daily; keep 90 days

Dependencies

Pin versions, update monthly, run pip-audit and npm audit

17.3 Order-safety controls (summary of section 12)

Live needs an explicit arm step with typed confirmation; the app always restarts in Paper.

A single code path sends real orders and checks mode, armed flag, risk gate and idempotency key.

Manual-confirm mode for the first weeks of live trading.

Kill switch from the UI, the API and a flag file that the engine checks every second.

17.4 Broker and regulatory points to confirm

Static IP: order placement needs a static IP registered with your Kite app (Kite forum). Options: an ISP static IP, or a small cloud VM with a fixed address where the backend runs. Market data and paper mode do not need it.

Order rate: staying under 10 orders per second per account keeps your own algo outside exchange registration (Zerodha FAQ). This app sends a handful of orders a day, but the order manager enforces a hard cap of 5 per second anyway.

Second user: each person trades their own Zerodha account through their own Kite app and their own login. Do not route another person's account through your API key. If the second user is not a family member you are sharing a tool with, ask Zerodha support what is allowed before enabling Live for them.

Rules change: exchange and SEBI circulars on retail algo trading, lot sizes, expiry days and market orders in options change often. Add a monthly checklist item: read Zerodha's and NSE's latest circulars and update the settings tables.

17.5 Records

The trade, order and fill tables are your audit trail for tax and dispute purposes; back them up and keep them for at least the period your tax adviser recommends.

18. Testing and validation

The Python engine is accepted only when it produces the same ENTRY and EXIT markers as TradingView on the same days, and the whole system has survived a month of paper trading and a set of failure drills.

18.1 Test layers

Layer

What it checks

Tooling

Unit

RMA, RSI, ATR, Supertrend, crossover, barssince; each signal rule on hand-made brick lists

pytest

Property tests

Renko invariants for any price path: every brick is exactly ±B, bricks are continuous, a reversal never starts before 2B

hypothesis

Parity

Renko bricks, Supertrend, RSI, bias score, flow score, every signal and trade event against TradingView data

tools/parity_check.py

Replay

A recorded day of ticks through the whole backend gives the same trades every run (determinism)

tools/replay.py

Integration

Fake Kite ticker and fake order API: login expiry, reconnect, partial fills, rejected orders

pytest + fakes

End to end

Browser test of Live, History, mode switch and wallet

Playwright

18.2 Getting the reference data out of TradingView

Save a copy of your Pine script as a debug build. Add plot() lines with display=display.data_window for the values to compare: st, rsi, biasScore, flowScore, runLen, plus numeric flags such as entL ? 1 : 0, entS ? 1 : 0, exitNow ? 1 : 0 and a signal-type code (1 = CORE, 2 = DIV, and so on).

Use Export chart data on the Renko chart for 10 trading days; the CSV then contains the bricks and every plotted value per brick.

Put the CSV in backend/tests/fixtures/ and run the parity tool. It prints the first brick where any value differs and the difference.

Keep the debug build next to your normal script; the trading logic must be identical.

18.3 Shadow check with TradingView alerts

The script already defines alerts (CO-BUY-ENTRY, DIV-SELL-EXIT and so on). Create them on your Renko chart with "Once Per Bar Close" and a webhook to the backend endpoint /api/shadow/tv-alert. The backend never trades from this feed; it only records it and compares it with its own events, and shows a mismatch banner if one side fires and the other does not within 2 bricks. This also tells you early when TradingView's data and Kite's data diverge.

18.4 Record real ticks every day

From day one, write every futures tick and every option tick of the traded strikes to a compressed file per day. These files are the best test data you will ever have: any bug found in live or paper can be replayed exactly.

18.5 Acceptance gates

Gate

Condition to pass

G1 Renko

Zero brick mismatches over 10 days

G2 Indicator

100% of ENTRY and EXIT events match on the same 10 days; bias and flow scores within a documented tolerance

G3 Strategy

Strike selection preview matches what you would choose by hand on 20 examples

G4 Paper burn-in

20 trading days in Paper with no unexplained rejection, crash, or orphan position; reconciliation clean

G5 Drills

All failure drills below passed

G6 Live pilot

1 lot, manual confirm on, daily loss limit small, for at least 10 trading days; paper twin within an acceptable slippage

18.6 Failure drills (run each on purpose)

Kill the backend while a trade is open, restart it: trade state restored and exit rules still run.

Cut the internet for 2 minutes: feed-stale alert, no new entries, reconnect, missed minutes backfilled.

Let the Kite token expire: banner, no crash, Paper still works.

Reject one leg of a spread: partial state, automatic unwind, alert.

Press the kill switch with an open Live trade: orders cancelled, legs closed, mode drops to Paper.

Change the clock by 5 seconds: drift warning appears.

Send the same signal twice: only one trade.

19. Deployment, scheduling, monitoring and scaling

In v1 everything runs as one backend process on your Windows PC that also serves the built dashboard; before real money it moves to a small cloud VM with a fixed IP, using the same code.

19.1 The trading day (all times IST, driven by APScheduler)

Time

Job

If it fails

08:30

Service up; load settings; check holiday calendar

Skip day if market closed

08:45

Check Kite login; show banner if missing

Alert; Paper still allowed after login

08:50

Download instruments; pick current futures and weekly expiry; refresh lot sizes

Retry every minute; block trading until done

09:00

Warm-up: backfill, rebuild bricks, run the engine silently

Block entries; alert

09:15

Market opens; opening range starts; live feed active

—

09:30

Entry window opens

—

14:45

Entry window closes

—

15:15

Square-off all open trades

Retry; alert; manual Close now

15:30

Market closes; feed stops

—

15:35

Daily report: daily_pnl, wallet check, reconciliation, summary alert

Alert

15:45

Database backup; rotate logs

Alert

19.2 Running on Windows (v1)

Build the dashboard once (npm run build) and let FastAPI serve the files, so there is one process and one port.

Install the backend as a Windows service with NSSM: automatic start, restart on failure, stdout and stderr to rotating log files.

Use a UPS or laptop battery if power cuts are common; keep Windows updates paused during 09:00–15:30.

Do not use Live mode on this setup unless you have a static IP at home or a static-IP service for orders.

19.3 Cloud deployment (before Live)

One small VM (2 vCPU, 2–4 GB RAM) in a Mumbai region with a reserved public IP; register that IP in the Kite app.

Docker Compose with three containers: backend, PostgreSQL, and a reverse proxy (Caddy) giving HTTPS. Restrict the dashboard to your IP addresses or put it behind a VPN.

The reverse proxy also gives TradingView a public HTTPS address for the shadow-check webhook (section 18.3); TradingView webhooks cannot reach a home PC without a tunnel.

Daily database dump to cloud storage, 30 days kept, restore tested once a month.

19.4 Monitoring

Signal

How

Process alive

GET /api/health pinged every minute by an external uptime service (for example Healthchecks.io)

Feed alive

Tick lag in the status chip; alert after 5 s without ticks

Trading safety

Red alerts for reconciliation mismatch, partial trade, risk-limit hit

Where alerts go

Dashboard feed (v1); Telegram bot and e-mail (phase 7)

Performance budget

Tick to brick to indicator under 50 ms; brick close to first order sent under 1 s

19.5 Scaling path

More underlyings: the engine is per underlying, so BankNifty is a second engine instance with its own settings.

More users: indicator engines are shared (they depend on the market, not the user); strategy, risk, execution and wallet are per user with their own Kite session. Every table already has user_id.

Heavier load: move the market-data worker into its own process and publish bricks and indicator results on Redis Streams; run several API instances behind the proxy.

Other brokers: add another class that implements the Broker interface; nothing above it changes.

20. Phased roadmap and task list

Eight phases take you from an empty folder to a supervised live pilot in roughly 18 calendar weeks at 10–15 hours a week with Codex doing most of the typing. Each phase ends with a gate; do not start the next phase until the gate passes.

Phase

Weeks

Outcome

Gate

0 Foundations

0–1

Policy checked, accounts ready, repo and tools set up, TradingView reference data exported

Backend and frontend "hello world" run

1 Data and Renko

1–3

Kite login, instruments, live ticks, historical backfill, Renko builder, tick recorder

G1: zero brick mismatches over 10 days

2 Indicator port

3–7

Full Pine logic in Python

G2: all ENTRY and EXIT events match

3 Strategy and paper execution

7–9

Signals become option spreads; paper fills; wallet; risk gate

G3: strike preview correct

4 API and dashboard

9–12

Live, History, Wallet and Settings tabs

Full day shown correctly on the dashboard in replay

5 Paper burn-in

12–16

20 trading days of paper trading with daily review

G4 and G5

6 Live pilot

16–18+

Live broker, static IP or cloud, reconciliation, manual confirm

G6

7 Extras

after

Telegram alerts, reports, BankNifty, second user

—

Phase 0: Foundations

☐ P0-01 Read the company technology policy; decide which machine and network to use.

☐ P0-02 Create the Kite developer account, choose the Connect plan, create the app, note key and secret.

☐ P0-03 Install tools (section 7.1); create the repository and the folder skeleton (section 6).

☐ P0-04 Add AGENTS.md, .env.example, .gitignore; first commit.

☐ P0-05 Save the Pine script as docs/pine/renko_indicator.pine; create the debug build with plots (section 18.2).

☐ P0-06 Export 10 days of Renko chart data from TradingView; commit as fixtures.

☐ P0-07 Backend hello world (/api/health) and frontend hello world; both run from IntelliJ.

Phase 1: Data and Renko

☐ P1-01 Settings module with typed config and .env loading.

☐ P1-02 Database models for instruments, bricks, fut_candles_5m, broker_sessions; first Alembic migration.

☐ P1-03 Kite login flow (login URL, callback, encrypted token, status endpoint).

☐ P1-04 Instruments download and futures/option lookup helpers with tests.

☐ P1-05 Historical backfill (1-minute and 5-minute with OI) with chunking and rate limiting.

☐ P1-06 Renko builder with property tests (section 9); anchor setting.

☐ P1-07 Parity tool for Renko; reach zero mismatches (G1).

☐ P1-08 Ticker worker: subscribe, queue, reconnect, resubscribe, stale-feed watchdog.

☐ P1-09 5-minute candle builder with VWAP, volume and OI.

☐ P1-10 Daily tick recorder.

Phase 2: Indicator port

☐ P2-01 maths.py plus tests against exported RSI and Supertrend.

☐ P2-02 state.py and the engine loop.

☐ P2-03 CORE signal and the trade engine (entry, T1, T2, opposite-brick exit, statistics).

☐ P2-04 Divergence engine: DIV, HDIV, forming flags.

☐ P2-05 PB, BRK, TRAP.

☐ P2-06 Outlook engine and the 10-factor bias with hysteresis.

☐ P2-07 Grading and risk labels; late-entry check.

☐ P2-08 ORB with IST session rules.

☐ P2-09 Flow engine and SRG.

☐ P2-10 texts.py explanation builders.

☐ P2-11 Full 10-day parity run; fix every difference; freeze (G2).

Phase 3: Strategy and paper execution

☐ P3-01 Option mapper and strike selector with unit tests and the preview endpoint.

☐ P3-02 Sizing and margin estimate.

☐ P3-03 Trade plan, trade state machine and persistence.

☐ P3-04 Paper broker (fills, order ids, latency option).

☐ P3-05 Position manager: live P&L, exit rules, 15:15 square-off.

☐ P3-06 Wallet service and ledger; auto top-up.

☐ P3-07 Risk gate and kill switch.

☐ P3-08 Daily P&L job; cost model.

☐ P3-09 Replay of a recorded day end to end (G3).

Phase 4: API and dashboard

☐ P4-01 REST endpoints and WebSocket server (section 14); OpenAPI client generation.

☐ P4-02 App shell, theme, top bar, mode switch, wallet chip.

☐ P4-03 Renko chart with Supertrend, markers, price lines, tint.

☐ P4-04 Live cards: direction, active position, last closed trade, today, signal feed, alerts.

☐ P4-05 History tab: summary, charts, weekly and monthly tables, filters, trade table, CSV.

☐ P4-06 Wallet tab and Settings tab with all inputs and tooltips.

☐ P4-07 Playwright smoke tests; replay a full day in the browser.

Phase 5: Paper burn-in

☐ P5-01 Run Paper every trading day; keep a daily review note (signals, trades, rejects, anomalies).

☐ P5-02 Compare with TradingView alerts through the shadow check every day.

☐ P5-03 Run all failure drills (section 18.6).

☐ P5-04 Weekly review: win rate and P&L per family, strength and time of day; tune settings only on paper, one change per week.

Phase 6: Live pilot

☐ P6-01 Cloud VM with fixed IP, Docker Compose, HTTPS; register the IP in the Kite app.

☐ P6-02 LiveBroker, order tagging, status polling, partial-fill unwind.

☐ P6-03 Reconciler and Live arm sequence; manual confirm.

☐ P6-04 Dry run: Live mode with orders logged but not sent.

☐ P6-05 Pilot: 1 lot, small limits, 10 trading days with the paper twin running; review slippage (G6).

21. Ready-to-use Codex prompts

Paste one prompt at a time, review the diff, run the tests, commit. Always attach the matching part of the Pine script (the file is long; give Codex only the section it is porting) and the matching section of this document saved as docs/SPEC.md.

21.1 Prompt template

Read AGENTS.md and docs/SPEC.md section <N>.Task: <one sentence>.Files to create or change: <paths>.Inputs: <Pine excerpt / sample data / interface to implement>.Rules: follow AGENTS.md; no extra features; keep names identical to Pine where porting.Tests: write pytest tests for <cases>; run them and show the result.Done when: <acceptance sentence from the roadmap>.

21.2 Prompts by phase

[P1-06 Renko builder]Read AGENTS.md and docs/SPEC.md section 9. Implement backend/app/market/renko_builder.py exactly as in 9.1-9.3, with an anchor and both modes(minute_close and tick). Add hypothesis property tests: every brick has |close-open| == box; consecutive bricks are continuous;a reversal brick never forms before 2*box; a gap of k boxes yields k bricks with the same timestamp. Also handle the first-price seed case.Done when pytest passes and a CSV-driven test can replay 1-minute closes into bricks.



[P1-07 Parity tool]Implement backend/app/tools/parity_check.py with a 'renko' subcommand: input a TradingView CSV export and 1-minute candles from a fixture file,build bricks, compare open/close/direction per brick, print the first mismatch (index, expected, got) and a summary. Exit code 1 on any mismatch.



[P2-01 maths]Implement backend/app/indicator/maths.py: Pine-exact rma (seeded with SMA of first n), rsi, atr, supertrend step (official Pine definition: hl2 source,direction -1 = uptrend), crossover, crossunder, barssince, rolling sum. Streaming versions (one value per call) plus list versions for tests.Compare against the fixture CSV columns st and rsi with tolerance 1e-6.



[P2-03 CORE + trade engine]Here is the Pine excerpt for CORE, the trade engine and exit logic: <paste lines>. Port it to indicator/signals.py and indicator/trade_plan.py using thestate dataclass in indicator/state.py. Order on each brick: exit check first, then entry. Emit TradeEvent(ENTRY/T1/EXIT) objects with a 5-character trade idbuilt by the same algorithm as f_id. Test: a hand-made sequence of bricks that triggers entry, T1, exit by opposite brick, and exit by Target 2.



[P2-04 Divergence]Port the divergence engine (topForm, botForm, bearDiv, bullDiv, hBearDiv, hBullDiv, bearForming, bullForming) from this Pine excerpt: <paste>.Keep variable names. Tests: equal-high divergence, higher-high divergence, lower-low divergence, hidden divergences, maxGap expiry, day reset when divCrossDay is false.



[P3-01 Option mapper]Implement strategy/option_mapper.py and strategy/strike_selector.py per SPEC section 11.3: input signal direction, spot, instruments table, settings;output a TradePlan with two legs, lots, expected credit, max loss. Never hard-code lot size, step, or expiry. Include the liquidity check and the expiry-day policy.Tests with a small fake instruments table including a weekly expiry on the test date.



[P3-04 Paper broker]Implement broker/base.py (Broker protocol) and broker/paper_broker.py per SPEC 12.3. Fill model: market uses best ask/bid from depth or last price +/- slippage; limit fillson touch. Order ids start with 'P-'. Include a test showing the same TradePlan runs against a FakeLiveBroker with identical results except ids.



[P4-01 API]Implement the FastAPI routes and the /ws/live WebSocket exactly as SPEC section 14, with Pydantic schemas and the error shape. Add an in-memory event hub the engine publishes to.Generate the OpenAPI JSON to frontend/src/api/openapi.json.



[P4-03 Chart]Build frontend/src/components/RenkoChart.tsx with lightweight-charts: candlestick series (wick colour = body colour), Supertrend as two line series, markers from the 'markers'array (text = code + trade id), price lines for entry/T1/T2, background tint from bias, a toolbar to toggle layers. Data from the zustand store; update the last bar without redrawing everything.



[P4-05 History]Build pages/History.tsx per SPEC 15.3: summary cards, daily P&L bar chart with cumulative line, weekly and monthly tables, filters, a TanStack table with the listed columns and CSV export.Use Indian number grouping and IST dates. Use mock data until the API is ready.



[P6-02 Live broker - review line by line]Implement broker/live_broker.py using the kiteconnect SDK, implementing the Broker protocol. Requirements: refuse to send unless mode == LIVE and armed == True;attach tag RT-<tradeId>-<leg>; poll order status; handle partial fills; one retry on network error with the same tag; log every request and response without secrets.Do not add any code path that sends orders from anywhere else.

21.3 Habits that save time

Ask Codex to explain its plan in five lines before writing code; correct the plan, not the code.

When a parity test fails, paste the first mismatch and the Pine excerpt, and ask for the smallest fix.

Never accept a change that edits test fixtures to make a test pass; fixtures come from TradingView only.

22. Risks, limitations and disclaimers

The biggest risk is not technical: nobody has shown yet that this indicator's signals make money when sold as option spreads, and option selling can lose several days of gains in one sharp move. The plan is built so that you find out with virtual money first.

Risk

Impact

Mitigation in this plan

Signal edge unproven for option spreads

Losses despite a "working" indicator

20+ paper days, per-family statistics, tune only on paper (sections 11.9, 18.5)

Python differs from TradingView (Renko grid, OI, VWAP)

Signals appear or vanish

Parity tool, debug build, shadow alerts, anchor setting

Feed outage or token expiry in the middle of a trade

Exit rules blind

Stale-feed block, broker-side protection by 15:15 square-off, alerts, reconciliation

Wide spreads or poor fills on the hedge leg

Slippage eats credit

Liquidity check, limit orders, paper twin to measure slippage

One leg fills, the other does not

Unhedged position

Hedge first, automatic unwind, partial state alert

Sharp gap or event move

Spread hits max loss

Defined-risk structure, daily loss limit, intraday only, no entries near events you choose to block

Wrong mode clicked

Real order from a test

Starts in Paper, typed Live confirmation, red frame, manual confirm

Regulatory or broker rule change

App stops placing orders

Monthly circular check, settings-driven values, no hard-coded rules

Windows PC failure, power cut, forced restart

Missed exits

Service auto-restart, state in database, move to cloud before Live

AI-generated code errors

Silent logic bugs

Small tasks, tests with every module, parity gates, code review of the order path line by line

Over-tuning on paper results

Looks good only in the past

One change per week, keep a changelog, out-of-sample weeks

Running costs (approximate; confirm current prices)

Item

Cost

Kite Connect plan

₹500 per month per app (Zerodha support); renewal credits may apply from October 2026 if brokerage is high enough

Static IP

ISP static IP or a small cloud VM with a fixed address; price varies by provider

TradingView, Codex, IntelliJ

Already owned

Disclaimer

This document is a technical specification, not investment, legal or tax advice, and I am not a financial adviser. Trading derivatives carries a risk of loss that can exceed your deposits when positions are not hedged. Verify every broker, exchange and regulatory detail with the official source before relying on it, and consult a qualified adviser for your own situation.

23. Appendix: Pine input map and glossary

23.1 Every trading input of the Pine script and its Python setting

Display-only inputs (colours, label size, dashboard position, joined Supertrend line, divergence line drawing, next-brick lines) become front-end preferences, not engine settings.

Pine input

Default

Python setting (indicator.*)

ATR Length

10

supertrend.atr_len

Factor

2.5

supertrend.factor

Renko box size

50

renko.box

CORE window (bricks after a flip)

3

signals.core_window

Min bricks between same-direction signals

3

signals.cooldown

Show signals of strength

Moderate and above

signals.min_grade (1, 2 or 3)

Track-record evaluation bricks

8

stats.eval_bricks

Divergence stays in score for N bricks

8

bias.div_fresh

Late-entry look-back minutes / bricks

15 / 3

grading.late_minutes, grading.late_bricks

Target 1 / Target 2 (% from entry)

2.5 / 4.0

trade.t1_pct, trade.t2_pct

Exit after N opposite bricks

1

trade.exit_opp_n

Exit at Target 2

on

trade.exit_at_t2

Safety-level exit / max distance (boxes)

off / 6

trade.exit_on_stop, trade.stop_cap_boxes

RSI length

14

divergence.rsi_len

Price structure

Equal or higher

divergence.top_type

Min RSI difference

0.5

divergence.min_rsi_gap

Max bricks between swings

60

divergence.max_gap

Bearish DIV first-top RSI at least / Bullish at most

50 / 50

divergence.rsi_hi, divergence.rsi_lo

Hidden divergence on

on

divergence.hdiv_on

Allow divergence across days

on

divergence.cross_day

PB on / trend age

on / 3

signals.pb_on, signals.pb_min_age

BRK on / swing age

on / 40

signals.brk_on, signals.brk_age

TRAP on / bricks to fail

on / 6

signals.trap_on, signals.trap_bars

ORB on / until / min range (boxes)

on / 11:30 / 2

signals.orb_on, signals.orb_until, signals.orb_min_boxes

SRG on / score needed / needs volume

on / 4 / on

signals.srg_on, signals.srg_min, signals.srg_need_vol

Flow engine on

on

flow.on

Futures symbol

NSE:NIFTY1!

flow.futures_underlying (resolved to the current Kite contract)

Use futures OI

on

flow.use_oi

Flow timeframe / build-up window

5 min / 3 bars

flow.tf_minutes, flow.window_bars

Min OI change % / min price change %

0.10 / 0.05

flow.oi_min_pct, flow.px_min_pct

Volume spike multiple

1.5

flow.vol_mult

Min samples for brick odds

20

outlook.min_samples

Stretched (boxes from Supertrend)

6

outlook.stretch_boxes

Manual ceiling / floor

0 / 0

outlook.manual_res, outlook.manual_sup

New settings added by the app (not in Pine): renko.anchor, renko.mode, and everything under strategy.*, risk.*, wallet.*.

23.2 Glossary

Term

Meaning

Brick / box

One Renko block; the box size is its height in index points

Supertrend

Trend line built from ATR; the trend flips when price closes through it

RSI divergence

Price makes a new high or low but RSI does not confirm; hidden divergence is the trend-continuation version

CO / DIV / OT

Signal families: Core trend start, Divergence, Other signals

Trade ID

Five-character code shown on the ENTRY and its EXIT so you can match them

Credit spread

Sell one option and buy a further out-of-the-money option; you receive a net credit and your loss is capped

Short leg / hedge leg

The sold option / the bought protective option

Lot

Minimum tradable quantity of an index option contract; read from the instruments file

OI

Open interest: number of open futures or option contracts

VWAP

Volume-weighted average price for the day

MTM

Mark to market: unrealised profit or loss at current prices

Parity

Python produces the same bricks and signals as TradingView

Paper / Live

Simulated orders against the dummy wallet / real orders through Kite

Kill switch

One action that cancels orders, closes all positions and switches to Paper

Shadow check

Comparing Python's events with TradingView alerts without trading from them

