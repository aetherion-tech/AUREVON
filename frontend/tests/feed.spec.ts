import { test, expect } from "@playwright/test";

test("market-data start requires a verified Kite login", async ({ page }) => {
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start market data", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText(
      "Complete Kite login until the status says Verified, then start market data.",
    ),
  ).toBeVisible();
});

test("mocked feed controls call data-only actions and preserve entry locks", async ({
  page,
}) => {
  // This scenario mocks the feed owner. Keep its transport consistent: the real
  // fixture's periodic stopped-state socket must not overwrite the mocked start.
  await page.routeWebSocket("**/ws/live*", () => {});
  let desired = false;
  await page.route("**/api/live/snapshot", async (route) => {
    const response = await route.fetch();
    const snapshot = await response.json();
    await route.fulfill({
      json: {
        ...snapshot,
        desired,
        state: desired ? "warming_up" : "stopped",
        entries_enabled: false,
      },
    });
  });
  await page.route("**/api/auth/kite/status", (route) =>
    route.fulfill({
      json: {
        configured: true,
        authenticated: true,
        message: "Synthetic verified session only",
      },
    }),
  );
  const calls: string[] = [];
  await page.route("**/api/market/service/*", async (route) => {
    const response = await page.request.get("/api/live/snapshot");
    const snapshot = await response.json();
    const start = route.request().url().endsWith("/start");
    desired = start;
    calls.push(start ? "start" : "stop");
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers()["x-csrf-token"]).toBeTruthy();
    await route.fulfill({
      json: {
        ...snapshot,
        desired: start,
        state: start ? "warming_up" : "stopped",
        entries_enabled: false,
      },
    });
  });
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Start market data", exact: true })
    .click();
  await expect(
    page.getByText(/Data service requested · warming_up/),
  ).toBeVisible();
  await expect(
    page.getByText("PAPER · Unarmed", { exact: true }),
  ).toBeVisible();
  const stopped = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/market/service/stop") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Stop market data", exact: true })
    .click();
  expect((await stopped).status()).toBe(200);
  expect(calls).toEqual(["start", "stop"]);
});
