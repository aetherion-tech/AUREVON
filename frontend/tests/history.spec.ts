import { test, expect, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import type { Schema } from "../src/live-data";
import { todayIST } from "../src/live-data";
import { paise, shiftDay } from "../src/history-data";
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "wait" });
});
async function login(page: Page) {
  await page.goto("/dashboard/history");
  await page
    .getByLabel("Dashboard password", { exact: true })
    .fill("browser-fixture-only");
  const response = page.waitForResponse((r) =>
    r.url().endsWith("/api/auth/dashboard/login"),
  );
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  expect((await response).status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "History and P&L" }),
  ).toBeVisible();
  // The initial socket handshake refetches active queries. Wait for that
  // completion before interacting with pagination that is disabled while fetching.
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
}
const today = todayIST(),
  previous = shiftDay(today, -1);
function record(
  id: string,
  day: string,
  net: string,
  family: "CO" | "DIV",
  grade: number,
  result: "WIN" | "LOSS" | "FLAT",
): Schema["TradeRecord"] {
  return {
    trade_id: id,
    closed_at: `${day}T10:00:00+05:30`,
    day,
    family,
    direction: 1,
    grade,
    result,
    gross: net === "30.00" ? "32.00" : net === "-5.00" ? "-2.00" : "3.00",
    costs: net === "30.00" ? "2.00" : "3.00",
    net,
    margin: "10000.00",
    entry_capital: "100000.00",
    margin_return_pct:
      net === "30.00" ? "0.3" : net === "-5.00" ? "-0.05" : "0",
    capital_return_pct:
      net === "30.00" ? "0.03" : net === "-5.00" ? "-0.005" : "0",
    reason: "manual",
    short_symbol: "PAPER-SHORT",
    hedge_symbol: "PAPER-HEDGE",
    created_at: `${day}T09:30:00+05:30`,
    quantity: 1,
    short_entry: "100",
    hedge_entry: "10",
    short_exit: "68",
    hedge_exit: "10",
    duration_seconds: 1800,
    signal_id: "browser-live:640:0",
  };
}
const records = [
  record("P-history-win", today, "30.00", "CO", 3, "WIN"),
  record("P-history-loss", previous, "-5.00", "DIV", 2, "LOSS"),
  record("P-history-flat", today, "0.00", "CO", 1, "FLAT"),
];
function report(
  rows: Schema["TradeRecord"][],
  start = previous,
  end = today,
): Schema["PnlSummary"] {
  const net = rows.reduce((sum, r) => sum + paise(r.net), 0n),
    gross = rows.reduce((sum, r) => sum + paise(r.gross), 0n),
    costs = rows.reduce((sum, r) => sum + paise(r.costs), 0n);
  const money = (v: bigint) =>
    `${v < 0n ? "-" : ""}${(v < 0n ? -v : v) / 100n}.${String((v < 0n ? -v : v) % 100n).padStart(2, "0")}`;
  const sorted = [...rows].sort((a, b) => Number(paise(a.net) - paise(b.net)));
  return {
    start,
    end,
    starting_capital: "100000.00",
    trades: rows.length,
    wins: rows.filter((r) => r.result === "WIN").length,
    gross: money(gross),
    costs: money(costs),
    net: money(net),
    external_flows: "10000.00",
    capital_return_pct: rows.length ? "0.025" : null,
    by_family_net: {},
    basis: "CLOSED_TRADES_NET_OF_ESTIMATED_COSTS",
    best_trade_id: sorted.at(-1)?.trade_id ?? null,
    best_trade_net: sorted.at(-1)?.net ?? null,
    worst_trade_id: sorted[0]?.trade_id ?? null,
    worst_trade_net: sorted[0]?.net ?? null,
  };
}
async function fixture(
  page: Page,
  options: { empty?: boolean; conflict?: boolean; exportError?: boolean } = {},
) {
  const conflict = options.conflict ?? false;
  const source = options.empty ? [] : records;
  const exports: URLSearchParams[] = [];
  function filtered(params: URLSearchParams) {
    return source
      .filter(
        (r) =>
          (!params.get("start") || r.day >= params.get("start")!) &&
          (!params.get("end") || r.day <= params.get("end")!) &&
          (["family", "direction", "grade", "result"] as const).every(
            (k) => !params.get(k) || String(r[k]) === params.get(k),
          ),
      )
      .sort((a, b) => {
        const key =
          params.get("sort") === "net"
            ? Number(paise(a.net) - paise(b.net))
            : a.closed_at.localeCompare(b.closed_at);
        return (
          (key || a.trade_id.localeCompare(b.trade_id)) *
          (params.get("order") === "asc" ? 1 : -1)
        );
      });
  }
  await page.route("**/api/pnl/summary?*", (route) => {
    const period = new URL(route.request().url()).searchParams.get("period");
    const rows =
      period === "daily" ? source.filter((r) => r.day === today) : source;
    return route.fulfill({
      json: report(rows, period === "daily" ? today : previous),
    });
  });
  await page.route("**/api/pnl/daily?*", (route) =>
    route.fulfill({
      json: [
        report(
          source.filter((r) => r.day === previous),
          previous,
          previous,
        ),
        report(
          source.filter((r) => r.day === today),
          today,
          today,
        ),
      ],
    }),
  );
  await page.route("**/api/pnl/periods?*", (route) =>
    route.fulfill({ json: [report(source)] }),
  );
  await page.route("**/api/trades?*", async (route) => {
    const params = new URL(route.request().url()).searchParams;
    if (params.get("cursor") && conflict) {
      // A stale cursor stays invalid until the client reloads page one. A
      // canceled/background request must not consume a one-shot rejection.
      await route.fulfill({
        status: 409,
        json: {
          error: {
            code: "history_changed",
            message: "History changed; reload first page",
          },
        },
      });
      return;
    }
    const rows = filtered(params),
      offset = Number(params.get("cursor") ?? 0);
    await route.fulfill({
      json: {
        items: rows.slice(offset, offset + 1),
        next_cursor: offset + 1 < rows.length ? String(offset + 1) : null,
        revision: 1,
        mode: "PAPER",
      },
    });
  });
  await page.route("**/api/trades/export?*", async (route) => {
    const params = new URL(route.request().url()).searchParams;
    exports.push(params);
    if (options.exportError) {
      await route.fulfill({
        status: 503,
        json: { error: { code: "unavailable", message: "Export unavailable" } },
      });
      return;
    }
    const fields = [
      "trade_id",
      "closed_at",
      "family",
      "direction",
      "grade",
      "result",
      "gross",
      "costs",
      "net",
      "margin",
      "margin_return_pct",
      "capital_return_pct",
      "short_symbol",
      "hedge_symbol",
      "reason",
    ] as const;
    const csv =
      [
        fields.join(","),
        ...filtered(params).map((r) => fields.map((k) => r[k] ?? "").join(",")),
      ].join("\n") + "\n";
    await route.fulfill({ contentType: "text/csv", body: csv });
  });
  await page.route("**/api/trades/P-history-*", (route) => {
    const id = new URL(route.request().url()).pathname.split("/").at(-1)!;
    const r = records.find((r) => r.trade_id === id)!;
    const detail: Schema["PositionView"] = {
      trade_id: id,
      decision_id: "fixture",
      mode: "PAPER",
      state: "CLOSED",
      created_at: r.created_at!,
      closed_at: r.closed_at,
      mark_at: null,
      legs: [
        {
          role: "SHORT",
          symbol: r.short_symbol,
          token: 1,
          quantity: 1,
          entry: "100",
          mark: "68",
        },
        {
          role: "HEDGE",
          symbol: r.hedge_symbol,
          token: 2,
          quantity: 1,
          entry: "10",
          mark: "10",
        },
      ],
      margin: r.margin,
      gross: r.gross,
      costs: r.costs,
      net: r.net,
      unrealised: null,
      spread_debit: null,
      exit_reason: r.reason,
      orders: [
        {
          id: "P-order-entry",
          status: "FILLED",
          side: "SELL",
          token: 1,
          quantity: 1,
          fill_price: "100",
          costs: "1.00",
          reason: null,
          created_at: r.created_at,
          eligible_at: r.created_at,
          filled_at: r.created_at ?? null,
        },
        {
          id: "P-order-close",
          status: "FILLED",
          side: "BUY",
          token: 1,
          quantity: 1,
          fill_price: "68",
          costs: "1.00",
          reason: "manual",
          created_at: r.closed_at,
          eligible_at: r.closed_at,
          filled_at: r.closed_at,
        },
      ],
      signal_stream: "browser-live",
      signal_index: 640,
      signal_explanation: "Synthetic persisted signal explanation",
      indicator_trade_id: "[CO123]",
    };
    return route.fulfill({ json: detail });
  });
  return { exports };
}
test("history summaries, exact charts, periods, paging, sort and CSV agree", async ({
  page,
}) => {
  const f = await fixture(page);
  await login(page);
  const all = page
    .getByRole("heading", { name: "All time", exact: true })
    .locator("..");
  await expect(all.getByText("₹25.00", { exact: true })).toBeVisible();
  await expect(all.getByText("33.33%", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("img", {
      name: "Daily P&L: net bars and cumulative net line",
    }),
  ).toBeVisible();
  const table = page
    .getByRole("heading", { name: "Closed paper trades" })
    .locator("..");
  await expect(
    table.getByText("P-history-win", { exact: false }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Next trades", exact: true }).click();
  await expect(table.getByText("Page 2", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Net P&L", exact: true }).click();
  await expect(table.getByText("Page 1", { exact: false })).toBeVisible();
  await expect(
    table.getByText("P-history-win", { exact: false }).first(),
  ).toBeVisible();
  expect(new URL(page.url()).searchParams.get("sort")).toBe("net");
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export matching CSV" }).click();
  const download = await downloaded;
  const text = await readFile((await download.path())!, "utf8");
  const rows = text
    .trim()
    .split("\n")
    .slice(1)
    .map((r) => r.split(","));
  expect(rows.map((r) => r[0])).toEqual([
    "P-history-win",
    "P-history-flat",
    "P-history-loss",
  ]);
  expect(rows.reduce((sum, r) => sum + paise(r[8]), 0n)).toBe(2500n);
  expect(f.exports[0].get("cursor")).toBeNull();
  expect(f.exports[0].get("sort")).toBe("net");
  await page.getByLabel("Signal family", { exact: true }).selectOption("DIV");
  await expect(
    table.getByText("P-history-loss", { exact: false }).first(),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Signal family", { exact: true })).toHaveValue(
    "DIV",
  );
  await expect(
    page
      .getByRole("heading", { name: "Closed paper trades" })
      .locator("..")
      .getByText("P-history-loss", { exact: false })
      .first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/history-mobile.png",
    fullPage: true,
  });
});
test("trade expansion loads persisted fills, order timeline, explanation and replay chart", async ({
  page,
}) => {
  await fixture(page);
  await login(page);
  await page.getByRole("button", { name: "Net P&L", exact: true }).click();
  await page.getByText("Details P-history-win", { exact: true }).click();
  await expect(
    page.getByText(
      "Signal explanation: Synthetic persisted signal explanation",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("P-order-entry · SELL · FILLED", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Order timeline" }),
  ).toBeVisible();
  await expect(page.getByTestId("renko-chart")).toBeVisible();
  await page.screenshot({
    path: "test-results/history-details.png",
    fullPage: true,
  });
});
test("empty and zero-denominator periods remain honest and export failures recover", async ({
  page,
}) => {
  await fixture(page, { empty: true, exportError: true });
  await login(page);
  await expect(
    page.getByText("No closed trades match these filters."),
  ).toBeVisible();
  const all = page
    .getByRole("heading", { name: "All time", exact: true })
    .locator("..");
  await expect(all.getByText("₹0.00", { exact: true })).toBeVisible();
  expect(await all.getByText("Unavailable", { exact: true }).count()).toBe(2);
  await page.getByRole("button", { name: "Export matching CSV" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Export unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Export matching CSV" }),
  ).toBeEnabled();
});
test("stale history cursor requires first-page reload and filters reset paging", async ({
  page,
}) => {
  await fixture(page, { conflict: true });
  await login(page);
  await page.getByRole("button", { name: "Next trades", exact: true }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "History changed" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Reload first page", exact: true })
    .click();
  await expect(page.getByText("Page 1", { exact: false })).toBeVisible();
  await page.getByLabel("Strength", { exact: true }).selectOption("3");
  await expect(page.getByText("Page 1", { exact: false })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Next trades" }),
  ).toBeDisabled();
});
test("invalid URL dates and unsupported LIVE mode block trade requests", async ({
  page,
}) => {
  let requests = 0;
  await page.route("**/api/trades?*", (route) => {
    requests++;
    return route.continue();
  });
  await login(page);
  const before = requests;
  await page.goto("/dashboard/history?start=2026-02-30&mode=LIVE");
  await expect(
    page.getByRole("alert").filter({ hasText: "Unsupported mode" }),
  ).toBeVisible();
  expect(requests).toBe(before);
  await expect(
    page.getByRole("heading", { name: "Closed paper trades" }),
  ).toHaveCount(0);
});
test("rapid filter changes cancel the old request and cannot show an obsolete page", async ({
  page,
}) => {
  await fixture(page);
  let release!: () => void, started!: () => void;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  const reached = new Promise<void>((resolve) => {
    started = resolve;
  });
  await page.route("**/api/trades?*", async (route) => {
    if (new URL(route.request().url()).searchParams.get("family") !== "CO") {
      await route.fallback();
      return;
    }
    started();
    await waiting;
    try {
      await route.fulfill({
        json: {
          items: [records[0]],
          next_cursor: null,
          revision: 1,
          mode: "PAPER",
        },
      });
    } catch {
      /* Expected when the AbortSignal cancels this superseded request. */
    }
  });
  await login(page);
  await page.getByLabel("Signal family", { exact: true }).selectOption("CO");
  await reached;
  const canceled = page.waitForEvent(
    "requestfailed",
    (request) => new URL(request.url()).searchParams.get("family") === "CO",
  );
  await page.getByLabel("Signal family", { exact: true }).selectOption("DIV");
  await canceled;
  release();
  const table = page
    .getByRole("heading", { name: "Closed paper trades" })
    .locator("..");
  await expect(
    table.getByText("P-history-loss", { exact: false }).first(),
  ).toBeVisible();
  await expect(table.getByText("P-history-win", { exact: false })).toHaveCount(
    0,
  );
  expect(new URL(page.url()).searchParams.get("family")).toBe("DIV");
});
