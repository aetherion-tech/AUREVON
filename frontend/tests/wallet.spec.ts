// Runs only against tools/test_server.py: temporary SQLite, no dotenv, ports 5174/18765.
// The operator database and ports 5173/8000 are never used by this suite.
import { test, expect, type Page } from "@playwright/test";
test.beforeEach(async ({ baseURL }) => {
  expect(baseURL).toBe("https://127.0.0.1:5174");
});
async function openWallet(page: Page) {
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("link", { name: "Wallet", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Paper wallet", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Deposit paper funds", exact: true }),
  ).toBeEnabled();
}
async function amountAction(page: Page, name: string, amount: string) {
  await page.getByRole("button", { name, exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Amount in INR").fill(amount);
  return dialog;
}
test("temporary fixture mutations preserve history and refresh exact balances", async ({
  page,
}) => {
  await openWallet(page);
  const before = await (await page.request.get("/api/wallet")).json();
  const ledgerBefore = await (
    await page.request.get("/api/wallet/ledger?limit=100")
  ).json();
  const dialog = await amountAction(page, "Deposit paper funds", "0.01");
  await dialog
    .getByRole("button", { name: "Add paper funds", exact: true })
    .click();
  await expect(dialog.getByRole("status")).toContainText("deposit recorded");
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.getByRole("table")).toContainText("DEPOSIT");
  await amountAction(page, "Withdraw paper funds", "0.01");
  await dialog.getByRole("button", { name: "Confirm withdrawal" }).click();
  await expect(dialog.getByRole("status")).toContainText("withdrawal recorded");
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await amountAction(page, "Reset paper wallet", before.balance);
  await expect(
    dialog.getByRole("button", { name: "Confirm reset" }),
  ).toBeDisabled();
  await dialog.getByRole("checkbox").check();
  await dialog.getByRole("button", { name: "Confirm reset" }).click();
  await expect(dialog.getByRole("status")).toContainText(
    "History and risk locks preserved",
  );
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  const after = await (await page.request.get("/api/wallet")).json();
  expect(after.balance).toBe(before.balance);
  expect(after.killed).toBe(before.killed);
  expect(after.loss_locked).toBe(before.loss_locked);
  const ledgerAfter = await (
    await page.request.get("/api/wallet/ledger?limit=100")
  ).json();
  expect(ledgerAfter.items.slice(0, ledgerBefore.items.length)).toEqual(
    ledgerBefore.items,
  );
  expect(
    ledgerAfter.items.slice(-3).map((e: { kind: string }) => e.kind),
  ).toEqual(["DEPOSIT", "WITHDRAW", "RESET"]);
  const free = await page
    .getByRole("heading", { name: "Free paper capital", exact: true })
    .locator("..")
    .locator(".metric")
    .innerText();
  await expect(page.locator(".wallet-chip strong")).toHaveText(free);
  await expect(
    page.getByRole("button", { name: /Delete paper history/ }),
  ).toBeDisabled();
  await page.screenshot({
    path: "test-results/wallet-desktop.png",
    fullPage: true,
  });
});
test("free-fund validation and mocked exposure rejection are visible", async ({
  page,
}) => {
  await openWallet(page);
  const dialog = await amountAction(
    page,
    "Withdraw paper funds",
    "999999999999.99",
  );
  await expect(dialog.getByRole("alert")).toContainText(
    "exceeds available free funds",
  );
  await expect(
    dialog.getByRole("button", { name: "Confirm withdrawal" }),
  ).toBeDisabled();
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await page.route("**/api/wallet/reset", (route) =>
    route.fulfill({
      status: 409,
      json: {
        error: {
          code: "domain_conflict",
          message: "cannot reset while a position or reservation exists",
        },
      },
    }),
  );
  await amountAction(page, "Reset paper wallet", "0");
  await dialog.getByRole("checkbox").check();
  await dialog.getByRole("button", { name: "Confirm reset" }).click();
  await expect(dialog.getByRole("alert")).toContainText(
    "position or reservation exists",
  );
  await dialog.getByRole("button", { name: /I checked the ledger/ }).click();
});
test("lost fixture withdrawal reply recovers with one debit and the same key", async ({
  page,
}) => {
  await openWallet(page);
  const before = await (
    await page.request.get("/api/wallet/ledger?limit=100")
  ).json();
  const keys: string[] = [];
  await page.route("**/api/wallet/withdraw", async (route) => {
    keys.push(route.request().headers()["idempotency-key"]);
    const response = await route.fetch();
    if (keys.length === 1) await route.abort("failed");
    else await route.fulfill({ response });
  });
  const dialog = await amountAction(page, "Withdraw paper funds", "0.01");
  await dialog.getByRole("button", { name: "Confirm withdrawal" }).dblclick();
  await expect(dialog.getByText(/outcome may be uncertain/)).toBeVisible();
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .getByRole("button", { name: "Withdraw paper funds", exact: true })
    .click();
  await expect(dialog.getByLabel("Amount in INR")).toBeDisabled();
  await dialog.getByRole("button", { name: "Confirm withdrawal" }).click();
  await expect(dialog.getByRole("status")).toContainText("withdrawal recorded");
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  const after = await (
    await page.request.get("/api/wallet/ledger?limit=100")
  ).json();
  expect(after.items.length).toBe(before.items.length + 1);
});
test("mocked ledger pages retain exact running balances on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const calls: string[] = [];
  await page.route("**/api/wallet/ledger?*", (route) => {
    const url = new URL(route.request().url());
    calls.push(url.searchParams.get("mode")!);
    const offset = Number(url.searchParams.get("offset"));
    return route.fulfill({
      json: {
        items: Array.from({ length: offset ? 1 : 25 }, (_, i) => ({
          sequence: offset + i,
          at: "2026-10-29T04:00:00Z",
          kind: offset ? "COSTS" : "DEPOSIT",
          key: `fixture:${offset + i}`,
          amount: offset ? "-0.01" : "0.01",
          balance: offset ? "999999999999.98" : "999999999999.99",
          reserved: "0.00",
        })),
        pagination: { limit: 25, offset, next_offset: offset ? null : 25 },
      },
    });
  });
  await openWallet(page);
  await page.getByRole("button", { name: "Next ledger page" }).click();
  await expect(page.getByRole("table")).toContainText("COSTS");
  await expect(page.getByRole("table")).toContainText("9,99,99,99,99,999.98");
  await expect(
    page.getByRole("button", { name: "Next ledger page" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Previous ledger page" }).click();
  await expect(page.getByRole("table")).toContainText("DEPOSIT");
  expect(calls.every((mode) => mode === "PAPER")).toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/wallet-mobile.png",
    fullPage: true,
  });
});
test("mocked blocked capital and foreign mode disable financial actions", async ({
  page,
}) => {
  let foreign = false;
  await page.route("**/api/wallet{,?*}", async (route) => {
    const response = await route.fetch();
    const wallet = await response.json();
    await route.fulfill({
      json: { ...wallet, mode: foreign ? "LIVE" : "PAPER", reserved: "0.01" },
    });
  });
  await openWallet(page);
  await expect(
    page.getByRole("button", { name: "Reset paper wallet", exact: true }),
  ).toBeDisabled();
  foreign = true;
  await page.getByRole("button", { name: "Refresh data", exact: true }).click();
  await expect(
    page.getByText("PAPER wallet unavailable. Financial actions are disabled."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Deposit paper funds", exact: true }),
  ).toBeDisabled();
  await expect(page.locator(".wallet-chip")).toContainText("Unavailable");
  await expect(
    page.getByRole("table", { name: "Paper wallet ledger" }),
  ).toHaveCount(0);
});

test("mocked settled trade event refreshes wallet, ledger and top bar together", async ({
  page,
}) => {
  let settled = false;
  let emit: (() => void) | undefined;
  await page.route("**/api/wallet{,?*}", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      json: {
        ...(await response.json()),
        balance: settled ? "100.01" : "100.00",
        free: settled ? "100.01" : "100.00",
        auto_topup: true,
      },
    });
  });
  await page.route("**/api/wallet/ledger?*", (route) =>
    route.fulfill({
      json: {
        items: settled
          ? [
              {
                sequence: 0,
                at: "2026-10-29T04:00:00Z",
                key: "mock-settlement",
                kind: "REALISED_GROSS",
                amount: "0.01",
                balance: "100.01",
                reserved: "0.00",
              },
            ]
          : [],
        pagination: { offset: 0, limit: 25, next_offset: null },
      },
    }),
  );
  await page.routeWebSocket("**/ws/live*", async (ws) => {
    const snapshot = await (
      await page.request.get("/api/live/snapshot")
    ).json();
    ws.send(JSON.stringify({ type: "snapshot", snapshot }));
    emit = () =>
      ws.send(
        JSON.stringify({
          type: "events",
          run_id: snapshot.run_id,
          sequence: snapshot.sequence + 1,
          events: [
            {
              api_version: "1.0",
              run_id: snapshot.run_id,
              sequence: snapshot.sequence + 1,
              kind: "trade",
              payload: {},
              at: new Date().toISOString(),
            },
          ],
        }),
      );
  });
  await openWallet(page);
  await expect(page.locator(".wallet-chip strong")).toContainText("100.00");
  await expect(page.getByText("Owner setting:")).toContainText("Enabled");
  await expect(page.getByText("No ledger entries on this page.")).toBeVisible();
  await expect.poll(() => typeof emit).toBe("function");
  settled = true;
  emit!();
  await expect(page.locator(".wallet-chip strong")).toContainText("100.01");
  await expect(page.getByRole("table")).toContainText("REALISED_GROSS");
  await expect(
    page.getByRole("heading", { name: "Total paper capital" }).locator(".."),
  ).toContainText("100.01");
});
