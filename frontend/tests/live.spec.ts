import { test, expect, type Page } from "@playwright/test";
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "wait" });
});
test("B1 exact total, metadata, stale and missing prices on mobile", async ({
  page,
}) => {
  let missing = false;
  await page.route("**/api/positions/open", (route) =>
    route.fulfill({
      json: [
        {
          trade_id: "B1-fixture",
          state: "OPEN",
          created_at: "2026-10-29T09:30:00+05:30",
          mark_at: "2026-10-29T09:31:00+05:30",
          margin: "10000.00",
          unrealised: missing ? null : "49.95",
          legs: [
            {
              role: "SHORT",
              symbol: "FIXTURE SHORT",
              quantity: 50,
              entry: "100.10",
              mark: "98.10",
              strike: "24000",
              expiry: "2026-11-03",
              lot_size: 25,
              unrealised: "100.00",
            },
            {
              role: "HEDGE",
              symbol: "FIXTURE HEDGE",
              quantity: 50,
              entry: "10.10",
              mark: missing ? null : "9.099",
              strike: "23800",
              expiry: "2026-11-03",
              lot_size: 25,
              unrealised: missing ? null : "-50.05",
            },
          ],
        },
      ],
    }),
  );
  await login(page);
  const card = page
    .getByRole("heading", { name: "Active paper spreads" })
    .locator("..");
  await expect(page.locator(".pnl-total")).toHaveText(/49.95/);
  await expect(
    card.getByRole("cell", { name: "24000", exact: true }),
  ).toBeVisible();
  await expect(
    card.getByRole("cell", { name: "Sell", exact: true }),
  ).toBeVisible();
  await expect(
    card.getByRole("cell", { name: "Buy", exact: true }),
  ).toBeVisible();
  await expect(card.getByRole("cell", { name: "2", exact: true })).toHaveCount(
    2,
  );
  await expect(card.locator(".pnl-loss")).toHaveText(/50.05/);
  await expect(page.getByText(/total is not a fresh valuation/)).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  missing = true;
  await page.reload();
  await expect(page.locator(".pnl-total")).toHaveText("Unavailable");
  await expect(
    card
      .getByRole("row")
      .filter({ hasText: "FIXTURE HEDGE" })
      .getByRole("cell", { name: "Unavailable", exact: true }),
  ).toHaveCount(2);
});
import type { Schema } from "../src/live-data";
test("B1 empty positions and fresh negative aggregate", async ({ page }) => {
  let empty = true;
  await page.route("**/api/positions/open", (route) =>
    route.fulfill({
      json: empty
        ? []
        : [
            {
              trade_id: "B1-negative",
              state: "OPEN",
              created_at: new Date().toISOString(),
              mark_at: new Date().toISOString(),
              margin: "10000.00",
              unrealised: "-0.30",
              legs: [],
            },
          ],
    }),
  );
  await login(page);
  const card = page
    .getByRole("heading", { name: "Active paper spreads" })
    .locator("..");
  await expect(card.getByText("No active paper spread.")).toBeVisible();
  await expect(page.locator(".pnl-total")).toHaveText(/0.00/);
  empty = false;
  await page.reload();
  await expect(page.locator(".pnl-total.pnl-loss")).toHaveText(/0.30/);
  await expect(page.getByText(/total is not a fresh valuation/)).toHaveCount(0);
});
async function login(page: Page) {
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Live paper desk" }),
  ).toBeVisible();
}
test("B2 chart left, summary right, positions below and responsive stacking", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await login(page);
  await expect(
    page.getByTestId("renko-chart").locator("[data-brick-index]"),
  ).toHaveCount(100);
  const chart = page.getByRole("region", { name: "Market chart", exact: true });
  const summary = page.getByRole("complementary", {
    name: "Strategy and P&L summary",
  });
  const positions = page.getByRole("region", {
    name: "Open positions",
    exact: true,
  });
  const activity = page.getByRole("region", {
    name: "Paper activity",
    exact: true,
  });
  await expect(
    summary.getByRole("heading", { name: "Open paper P&L" }),
  ).toBeVisible();
  await expect(
    summary.getByRole("heading", { name: "Direction and strength" }),
  ).toBeVisible();
  await expect(
    summary.getByRole("heading", { name: "Today", exact: true }),
  ).toBeVisible();
  const c = (await chart.boundingBox())!,
    s = (await summary.boundingBox())!,
    p = (await positions.boundingBox())!;
  expect(c.x + c.width).toBeLessThanOrEqual(s.x);
  expect(c.width).toBeGreaterThan(s.width * 1.8);
  expect(Math.abs(c.y - s.y)).toBeLessThan(2);
  expect(p.y).toBeGreaterThanOrEqual(Math.max(c.y + c.height, s.y + s.height));
  expect(p.width).toBeGreaterThan(c.width + s.width);
  expect(Math.abs(p.x + p.width - (s.x + s.width))).toBeLessThan(2);
  expect((await activity.boundingBox())!.y).toBeGreaterThanOrEqual(
    p.y + p.height,
  );
  await page.screenshot({
    path: "../docs/testing/UI-LIVE-B2-desktop.png",
    fullPage: true,
  });
  for (const width of [1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    const stackedChart = (await chart.boundingBox())!,
      stackedSummary = (await summary.boundingBox())!,
      stackedPositions = (await positions.boundingBox())!;
    expect(stackedSummary.y).toBeGreaterThanOrEqual(
      stackedChart.y + stackedChart.height,
    );
    expect(stackedPositions.y).toBeGreaterThanOrEqual(
      stackedSummary.y + stackedSummary.height,
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
  }
  await page.screenshot({
    path: "../docs/testing/UI-LIVE-B2-mobile.png",
    fullPage: true,
  });
});
test("last closed results and today risk values use server projections", async ({
  page,
}) => {
  const day = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  const trade: Schema["TradeRecord"] = {
    trade_id: "P-closed-fixture",
    closed_at: `${day}T10:00:00+05:30`,
    day,
    family: "CO",
    direction: 1,
    grade: 3,
    result: "WIN",
    gross: "124.50",
    costs: "1.05",
    net: "123.45",
    margin: "10000.00",
    entry_capital: "1000000.00",
    margin_return_pct: "1.2345",
    capital_return_pct: "0.012345",
    reason: "premium_target",
    short_symbol: "SHORT",
    hedge_symbol: "HEDGE",
  };
  await page.route("**/api/trades?*", (route) =>
    route.fulfill({
      json: { items: [trade], next_cursor: null, revision: 1, mode: "PAPER" },
    }),
  );
  await page.route("**/api/pnl/summary?*", (route) =>
    route.fulfill({
      json: {
        start: day,
        end: day,
        starting_capital: "1000000.00",
        trades: 3,
        wins: 2,
        gross: "124.50",
        costs: "1.05",
        net: "123.45",
        external_flows: "10000.00",
        capital_return_pct: "0.012345",
        by_family_net: { CO: "123.45" },
        basis: "CLOSED_TRADES_NET_OF_ESTIMATED_COSTS",
      },
    }),
  );
  await page.route("**/api/wallet", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: {
        ...body,
        risk_day: day,
        daily_loss_limit: "20000",
        daily_loss_used: "400",
        daily_loss_utilisation_pct: "2",
      },
    });
  });
  await login(page);
  const closed = page
    .getByRole("heading", { name: "Last closed trade" })
    .locator("..");
  await expect(
    closed.getByText("premium_target", { exact: true }),
  ).toBeVisible();
  await expect(closed.getByText("₹123.45", { exact: true })).toBeVisible();
  await expect(closed.getByText("1.2345%", { exact: true })).toBeVisible();
  const today = page
    .getByRole("heading", { name: "Today", exact: true })
    .locator("..");
  await expect(today.getByText("3 / 2", { exact: true })).toBeVisible();
  await expect(today.getByText("2%", { exact: true })).toBeVisible();
  await expect(today.getByText("0.012345%", { exact: true })).toBeVisible();
});
test("real published Renko history, equal-time ordering, paging, source and persisted layers", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const initialHistory = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/bricks" &&
      response.status() === 200,
  );
  await login(page);
  await initialHistory;
  const chart = page.getByTestId("renko-chart");
  await expect(chart.locator("[data-brick-index]")).toHaveCount(100);
  await expect(page.getByText(/INDICATOR_REPLAY · source/)).toBeVisible();
  await page.getByLabel("Brick window").selectOption("300");
  await expect(chart.locator("[data-brick-index]")).toHaveCount(300);
  await expect(chart.locator("[data-brick-index]").last()).toHaveAttribute(
    "data-brick-index",
    "654",
  );
  expect(
    await chart
      .locator("[data-brick-index]")
      .evaluateAll((nodes) =>
        nodes.map((n) => Number(n.getAttribute("data-brick-index"))),
      ),
  ).toEqual(Array.from({ length: 300 }, (_, i) => 355 + i));
  expect(await chart.locator("[data-marker]").count()).toBeGreaterThan(0);
  await page
    .getByText("Accessible chart data and event details", { exact: true })
    .click();
  const rows = page.locator(".renko-frame tbody tr");
  expect(await rows.nth(0).locator("td").nth(1).textContent()).toBe(
    await rows.nth(1).locator("td").nth(1).textContent(),
  );
  await page.getByLabel("events", { exact: true }).uncheck();
  await expect(chart.locator("[data-marker]")).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel("events", { exact: true })).not.toBeChecked();
  await page.getByLabel("Brick window").selectOption("300");
  await expect(chart.locator("[data-brick-index]").last()).toHaveAttribute(
    "data-brick-index",
    "654",
  );
  await page
    .getByRole("button", { name: "Load older history", exact: true })
    .click();
  await expect(chart.locator("[data-brick-index]").last()).toHaveAttribute(
    "data-brick-index",
    "354",
  );
  await page.getByRole("button", { name: "Follow latest" }).click();
  await expect(chart.locator("[data-brick-index]").last()).toHaveAttribute(
    "data-brick-index",
    "654",
  );
  await page.getByText("Ten-factor explanation", { exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Direction and strength" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/live-desktop.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("empty history, unavailable overlays and stale prices stay explicit on mobile", async ({
  page,
}) => {
  await page.route("**/api/bricks?*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: {
        ...body,
        items: [],
        overlays: [],
        indicator_source: null,
        overlay_status: "empty",
        overlay_reason: "not_published",
        next_after: null,
      },
    });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await expect(
    page.getByText("No Renko history for this source."),
  ).toBeVisible();
  await expect(page.getByText(/Feed readiness blocked/)).toBeVisible();
  await expect(page.getByText("No active paper spread.")).toBeVisible();
  await expect(page.getByText("No closed paper trade.")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/live-mobile-empty.png",
    fullPage: true,
  });
});
test("alerts remain until server acknowledgement and newest signals show reasons", async ({
  page,
}) => {
  let acknowledged = false;
  await page.route("**/api/alerts?*", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: "alert-1",
            level: "critical",
            code: "daily_loss_locked",
            at: "2026-10-29T10:00:00+05:30",
            acknowledged_at: acknowledged ? "2026-10-29T10:01:00+05:30" : null,
          },
        ],
        pagination: { limit: 50, offset: 0, total: 1, next_offset: null },
      },
    }),
  );
  await page.route("**/api/alerts/alert-1/ack", async (route) => {
    acknowledged = true;
    await route.fulfill({
      json: {
        id: "alert-1",
        level: "critical",
        code: "daily_loss_locked",
        at: "2026-10-29T10:00:00+05:30",
        acknowledged_at: "2026-10-29T10:01:00+05:30",
      },
    });
  });
  await login(page);
  await expect(
    page.getByRole("link", {
      name: "1 alerts need attention in loaded history",
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Acknowledge daily_loss_locked" })
    .click();
  await expect(
    page.getByRole("button", { name: "Acknowledge daily_loss_locked" }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Acknowledge daily_loss_locked" }),
  ).toHaveCount(0);
  await expect(page.getByText("Signal feed", { exact: true })).toBeVisible();
  await expect
    .poll(() => page.locator(".feed").first().locator("li").count())
    .toBeGreaterThan(0);
});
test("manual close duplicate guard, pending state and final exit reason", async ({
  page,
}) => {
  const position = {
    trade_id: "P-fixture",
    decision_id: "decision",
    mode: "PAPER",
    state: "OPEN",
    created_at: "2026-10-29T09:30:00+05:30",
    mark_at: "2026-10-29T09:31:00+05:30",
    legs: [
      {
        role: "SHORT",
        symbol: "NIFTY SHORT",
        quantity: 50,
        token: 1,
        entry: "100",
        mark: "98",
      },
      {
        role: "HEDGE",
        symbol: "NIFTY HEDGE",
        quantity: 50,
        token: 2,
        entry: "10",
        mark: "9",
      },
    ],
    margin: "10000.00",
    gross: "50.00",
    costs: "1.00",
    net: "49.00",
    unrealised: "50.00",
    spread_debit: "89",
    exit_reason: null,
    orders: [],
    stop_debit_per_unit: "130",
    profit_capture_debit_per_unit: "45",
    profit_capture_enabled: true,
    margin_return_pct: "0.5",
    closed_at: null as string | null,
  };
  let closeCalls = 0,
    closed = false,
    requested = false;
  await page.route("**/api/positions/open", (route) =>
    route.fulfill({
      json: closed
        ? []
        : [{ ...position, state: requested ? "CLOSING" : "OPEN" }],
    }),
  );
  await page.route("**/api/trades/P-fixture", (route) =>
    route.fulfill({
      json: {
        ...position,
        state: closed ? "CLOSED" : requested ? "CLOSING" : "OPEN",
        exit_reason: closed ? "manual" : null,
        closed_at: closed ? "2026-10-29T09:32:00+05:30" : null,
      },
    }),
  );
  await page.route("**/api/trades/P-fixture/close", async (route) => {
    closeCalls++;
    requested = true;
    await new Promise((r) => setTimeout(r, 200));
    await route.fulfill({
      json: {
        mode: "PAPER",
        armed: false,
        entries_locked: false,
        pending_closures: 1,
      },
    });
  });
  await login(page);
  await expect(page.getByRole("cell", { name: "NIFTY HEDGE" })).toBeVisible();
  await expect(page.getByText("130", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Close paper spread", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Confirm close" }).dblclick();
  await expect(dialog.getByRole("status")).toContainText("1 pending closures");
  expect(closeCalls).toBe(1);
  await expect(dialog.getByText(/Closed · exit reason/)).toHaveCount(0);
  closed = true;
  await expect(dialog.getByRole("status")).toContainText(
    "Closed · exit reason manual",
  );
});

test("ticks preserve chart nodes; brick updates are incremental and gaps reload snapshot/history", async ({
  page,
}) => {
  let last = 654,
    opens = 0,
    chartRequests = 0;
  const brick = (index: number): Schema["BrickData"] => ({
    index,
    open: "23900",
    close: "23850",
    direction: -1,
    ts: "2026-10-29T09:33:38+05:30",
    volume: "0",
  });
  let emit:
    | ((
        kind: "tick" | "brick",
        payload: Schema["TickData"] | Schema["BrickData"],
        skip?: number,
      ) => void)
    | undefined;
  await page.route("**/api/live/snapshot", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: { ...body, latest_brick: brick(last) },
    });
  });
  await page.route("**/api/bricks?*", async (route) => {
    chartRequests++;
    const response = await route.fetch();
    const body = await response.json();
    const params = new URL(route.request().url()).searchParams;
    const items = body.items as Schema["BrickData"][];
    if (
      last === 655 &&
      body.next_after === null &&
      Number(params.get("after")) < 655 &&
      items.length < 300
    )
      items.push(brick(655));
    await route.fulfill({
      response,
      json: {
        ...body,
        items,
        indicator_source: null,
        overlays: [],
        overlay_status: "unavailable",
        overlay_reason: "not_published",
        indicators_available: false,
      },
    });
  });
  await page.routeWebSocket("**/ws/live*", async (ws) => {
    opens++;
    const snapshot = await (
      await page.request.get("/api/live/snapshot")
    ).json();
    let sequence = snapshot.sequence;
    ws.send(JSON.stringify({ type: "snapshot", snapshot }));
    emit = (kind, payload, skip = 0) => {
      sequence += 1 + skip;
      ws.send(
        JSON.stringify({
          type: "events",
          run_id: snapshot.run_id,
          sequence,
          events: [
            {
              api_version: "1.0",
              run_id: snapshot.run_id,
              sequence,
              kind,
              payload,
              at: new Date().toISOString(),
            },
          ],
        }),
      );
    };
  });
  const initialHistory = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === "/api/bricks" &&
      response.status() === 200,
  );
  await login(page);
  await initialHistory;
  const chart = page.getByTestId("renko-chart");
  await expect(chart.locator("[data-brick-index]").last()).toHaveAttribute(
    "data-brick-index",
    "654",
  );
  await expect.poll(() => typeof emit).toBe("function");
  const original = await chart
    .locator('[data-brick-index="653"]')
    .elementHandle();
  const requestsBeforeTick = chartRequests;
  emit!("tick", {
    token: 111,
    price: "24000.00",
    time: new Date().toISOString(),
  });
  await expect
    .poll(() =>
      chart
        .locator('[data-brick-index="653"]')
        .evaluate((node, previous) => node === previous, original),
    )
    .toBe(true);
  expect(chartRequests).toBe(requestsBeforeTick);
  last = 655;
  emit!("brick", brick(655));
  await expect(chart.locator("[data-brick-index]").last()).toHaveAttribute(
    "data-brick-index",
    "655",
  );
  await expect(chart.locator("[data-brick-index]")).toHaveCount(100);
  expect(
    await chart
      .locator('[data-brick-index="653"]')
      .evaluate((node, previous) => node === previous, original),
  ).toBe(true);
  const beforeGap = chartRequests;
  emit!(
    "tick",
    { token: 111, price: "24001.00", time: new Date().toISOString() },
    1,
  );
  await expect.poll(() => opens).toBeGreaterThan(1);
  await expect.poll(() => chartRequests).toBeGreaterThan(beforeGap);
  await expect(chart.locator("[data-brick-index]")).toHaveCount(100);
});

test("a changed chart revision rejects older pages and reloads a coherent generation", async ({
  page,
}) => {
  let changed = false;
  await page.route("**/api/live/snapshot", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.latest_brick = {
      index: 654,
      open: "23900",
      close: "23850",
      direction: -1,
      ts: "2026-10-29T09:33:38+05:30",
      volume: "0",
    };
    await route.fulfill({ response, json: body });
  });
  // Suppress the normal initial socket snapshot in this deterministic source fixture.
  await page.routeWebSocket("**/ws/live*", () => {});
  await page.route("**/api/bricks?*", async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.has("revision") && !changed) {
      changed = true;
      await route.fulfill({
        status: 409,
        json: {
          error: { code: "source_changed", message: "Chart source changed" },
        },
      });
      return;
    }
    const response = await route.fetch();
    const body = await response.json();
    if (changed) {
      body.revision = 2;
      if (body.indicator_source) {
        body.indicator_source.market_revision = 2;
        body.indicator_source.source_id = "b".repeat(64);
      }
    }
    await route.fulfill({ response, json: body });
  });
  await login(page);
  await page.getByLabel("Brick window").selectOption("300");
  await expect(
    page.getByTestId("renko-chart").locator("[data-brick-index]"),
  ).toHaveCount(300);
  await page
    .getByRole("button", { name: "Load older history", exact: true })
    .click();
  await expect(
    page.getByText(
      "Chart source changed. History and overlays were reloaded together.",
    ),
  ).toBeVisible();
  await expect(page.locator(".source-identity")).toContainText("revision 2");
  await expect(
    page.getByTestId("renko-chart").locator("[data-brick-index]"),
  ).toHaveCount(300);
});
