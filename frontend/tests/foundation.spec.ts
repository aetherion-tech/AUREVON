import { test, expect, type Page } from "@playwright/test";
test("unconfigured dashboard explains local password setup before login", async ({
  page,
}) => {
  await page.route("**/api/auth/dashboard/status", (route) =>
    route.fulfill({ json: { configured: false, authenticated: false } }),
  );
  await page.goto("/dashboard/");
  await expect(page.getByRole("alert")).toContainText(
    "Dashboard password is not configured",
  );
  await expect(
    page.getByText(/app.tools.dashboard_password --save/),
  ).toBeVisible();
  await expect(
    page.getByLabel("Dashboard password", { exact: true }),
  ).toHaveCount(0);
});
async function login(page: Page) {
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  const loginResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/auth/dashboard/login") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  expect((await loginResponse).status()).toBe(200);
  await expect(page.getByRole("navigation")).toBeVisible();
}
test("real HTTPS proxy, secure cookie, guarded routes, exact deposit, pending kill and logout", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await login(page);
  await page.screenshot({
    path: "test-results/desktop-shell.png",
    fullPage: true,
  });
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
  await expect(page.getByText("Kite: Not configured")).toBeVisible();
  await page.getByRole("link", { name: "History", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "History and P&L" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "History and P&L" }),
  ).toBeVisible();
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Add paper funds", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Amount in INR")).toBeFocused();
  await dialog.getByLabel("Amount in INR").fill("0.01");
  const depositResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/wallet/deposit") &&
      response.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "Add paper funds", exact: true })
    .click();
  expect((await depositResponse).status()).toBe(200);
  await expect(dialog.getByRole("status")).toHaveText(
    "Paper deposit recorded.",
  );
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Add paper funds", exact: true }),
  ).toBeFocused();
  await page
    .getByRole("button", { name: "Kill paper execution", exact: true })
    .click();
  await page.keyboard.press("Tab");
  await expect(
    dialog.getByRole("button", { name: "Close", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    dialog.getByRole("button", { name: "Confirm kill" }),
  ).toBeFocused();
  await dialog.getByRole("button", { name: "Confirm kill" }).click();
  await expect(dialog.getByRole("status")).toContainText("0 pending closures");
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByLabel("Compact spacing").check();
  await page.reload();
  await expect(page.getByLabel("Compact spacing")).toBeChecked();
  await page.goto("/dashboard/missing");
  await expect(
    page.getByRole("heading", { name: "Page not found" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Dashboard password")).toBeVisible();
  await page.goto("/dashboard/wallet");
  await expect(page.getByLabel("Dashboard password")).toBeVisible();
  expect(errors).toEqual([]);
});
test("session expiry clears private screens and stale socket", async ({
  page,
}) => {
  await login(page);
  await page.route("**/api/wallet", (route) =>
    route.fulfill({
      status: 401,
      json: {
        error: { code: "authentication_required", message: "Sign in first" },
      },
    }),
  );
  await page.getByRole("button", { name: "Refresh data" }).click();
  await expect(page.getByLabel("Dashboard password")).toBeVisible();
  await expect(page.getByRole("navigation")).toHaveCount(0);
});
test("socket reconnect reloads REST snapshot; mobile navigation remains usable", async ({
  page,
}) => {
  let count = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/api/live/snapshot")) count++;
  });
  let opens = 0;
  await page.routeWebSocket("**/ws/live*", (ws) => {
    opens++;
    if (opens === 1)
      setTimeout(() => ws.close({ code: 1013, reason: "fixture resync" }), 200);
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await expect.poll(() => opens).toBeGreaterThan(1);
  expect(count).toBeGreaterThan(1);
  await page.getByRole("link", { name: "Wallet", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Paper wallet" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
test("lost committed deposit reply survives reload and retries without duplicating funds", async ({
  page,
}) => {
  await login(page);
  const before = await (await page.request.get("/api/wallet")).json();
  const keys: string[] = [];
  let loseReply = true;
  await page.route("**/api/wallet/deposit", async (route) => {
    keys.push(route.request().headers()["idempotency-key"]);
    if (loseReply) {
      loseReply = false;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await page
    .getByRole("button", { name: "Add paper funds", exact: true })
    .click();
  await page.getByLabel("Amount in INR").fill("0.02");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Add paper funds", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByRole("alert")).toBeVisible({
    timeout: 15000,
  });
  await page.reload();
  await page
    .getByRole("button", { name: "Add paper funds", exact: true })
    .click();
  await expect(page.getByLabel("Amount in INR")).toHaveValue("0.02");
  await expect(page.getByLabel("Amount in INR")).toBeDisabled();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Add paper funds", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByRole("status")).toHaveText(
    "Paper deposit recorded.",
  );
  const after = await (await page.request.get("/api/wallet")).json();
  expect(Number(after.balance) - Number(before.balance)).toBeCloseTo(0.02, 5);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});
test("Kite configured, expired and verified states and official login link", async ({
  page,
}) => {
  let status = {
    configured: true,
    authenticated: false,
    message: "Fixture configuration only",
    expires_at: null as string | null,
  };
  await page.route("**/api/auth/kite/status", (route) =>
    route.fulfill({ json: status }),
  );
  await login(page);
  await expect(
    page.getByText("Kite: Configured · login required"),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Log in to Kite" }),
  ).toHaveAttribute("href", "/api/auth/kite/login");
  status = {
    ...status,
    authenticated: true,
    expires_at: "2000-01-01T00:00:00Z",
  };
  await page.getByRole("button", { name: "Refresh data" }).click();
  await expect(page.getByText("Kite: Expired")).toBeVisible();
  status = { ...status, expires_at: "2099-01-01T00:00:00Z" };
  await page.getByRole("button", { name: "Refresh data" }).click();
  await expect(page.getByText("Kite: Verified")).toBeVisible();
});
test("unattached wallet stays unavailable with recoverable error and socket auth close guards the shell", async ({
  page,
}) => {
  let closeSocket = () => {};
  await page.routeWebSocket("**/ws/live*", (ws) => {
    closeSocket = () => ws.close({ code: 1008, reason: "fixture expired" });
  });
  await page.route("**/api/wallet", (route) =>
    route.fulfill({
      status: 409,
      json: {
        error: {
          code: "paper_unavailable",
          message: "Paper owner unavailable",
        },
      },
    }),
  );
  await login(page);
  await expect(
    page.getByRole("alert").filter({ hasText: "Paper owner unavailable" }),
  ).toContainText("Paper owner unavailable");
  await expect(
    page.getByRole("button", { name: "Add paper funds", exact: true }),
  ).toBeDisabled();
  await expect(page.getByText("Paper free cash")).toContainText("Unavailable");
  await page
    .locator(".wallet-chip")
    .getByRole("button", { name: "Retry", exact: true })
    .click();
  await page.unroute("**/api/wallet");
  await page.getByRole("button", { name: "Refresh data", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Add paper funds", exact: true }),
  ).toBeEnabled();
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
  closeSocket();
  await expect(page.getByLabel("Dashboard password")).toBeVisible();
});
