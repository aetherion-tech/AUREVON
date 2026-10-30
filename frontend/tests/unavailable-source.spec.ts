import { test, expect } from "@playwright/test";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
}

test("quote-only missing source avoids 404 requests and resumes when history appears", async ({
  page,
}) => {
  let available = false;
  let chartCalls = 0;
  let signalCalls = 0;
  // This is a mocked availability transition; the actual operator feed is untouched.
  await page.routeWebSocket("**/ws/live*", () => {});
  await page.route("**/api/live/snapshot", async (route) => {
    const response = await route.fetch();
    const snapshot = await response.json();
    await route.fulfill({
      json: available
        ? { ...snapshot, unavailable: [] }
        : {
            ...snapshot,
            state: "running_quotes_only_anchor_required",
            latest_brick: null,
            unavailable: ["indicators", "signals"],
            signals: [],
            entries_enabled: false,
          },
    });
  });
  for (const kind of ["bricks", "signals"]) {
    await page.route(`**/api/${kind}?*`, async (route) => {
      if (kind === "bricks") chartCalls++;
      else signalCalls++;
      if (available) await route.continue();
      else
        await route.fulfill({
          status: 404,
          json: {
            error: {
              code: "http_error",
              message: "Not Found",
              request_id: "missing-source",
            },
          },
        });
    });
  }
  await login(page);
  await expect(
    page.getByText(/verified Renko anchor is required before chart history/),
  ).toBeVisible();
  await expect(
    page.getByText(/Signals are unavailable until Renko history/),
  ).toBeVisible();
  await expect(page.getByText("Not Found", { exact: false })).toHaveCount(0);
  expect(chartCalls).toBe(0);
  expect(signalCalls).toBe(0);
  await page.screenshot({
    path: "test-results/live-quote-only-fixed.png",
    fullPage: true,
  });
  available = true;
  await page.getByRole("button", { name: "Refresh data", exact: true }).click();
  await expect(page.locator(".source-identity")).toBeVisible();
  await expect.poll(() => chartCalls).toBeGreaterThan(0);
  await expect.poll(() => signalCalls).toBeGreaterThan(0);
  await expect(
    page.getByText(/Signals are unavailable until Renko history/),
  ).toHaveCount(0);

  // The cache now contains overlays/signals. Returning to unavailable must not
  // display those stale values under the same stream/configuration identity.
  available = false;
  await page.getByRole("button", { name: "Refresh data", exact: true }).click();
  await expect(
    page.getByText(/verified Renko anchor is required before chart history/),
  ).toBeVisible();
  await expect(page.locator(".source-identity")).toHaveCount(0);
  await expect(
    page.getByText(
      "Indicator bias unavailable until matching overlays are published.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText(/Signals are unavailable until Renko history/),
  ).toBeVisible();
});

test("available-source server failures remain visible instead of becoming empty states", async ({
  page,
}) => {
  await page.routeWebSocket("**/ws/live*", () => {});
  await page.route("**/api/live/snapshot", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      json: { ...(await response.json()), unavailable: [] },
    });
  });
  for (const kind of ["bricks", "signals"]) {
    await page.route(`**/api/${kind}?*`, (route) =>
      route.fulfill({
        status: 500,
        json: {
          error: {
            code: "internal_error",
            message: `${kind} service failed`,
            request_id: `failure-${kind}`,
          },
        },
      }),
    );
  }
  await login(page);
  await expect(page.getByText(/bricks service failed/)).toBeVisible();
  await expect(page.getByText(/signals service failed/)).toBeVisible();
  await expect(
    page.getByText(/Signals are unavailable until Renko history/),
  ).toHaveCount(0);
});

test("a stopped source with missing history explains its 404 without inventing data", async ({
  page,
}) => {
  await page.routeWebSocket("**/ws/live*", () => {});
  let signals = 0;
  await page.route("**/api/live/snapshot", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      json: {
        ...(await response.json()),
        state: "stopped",
        latest_brick: null,
        unavailable: ["indicators", "signals"],
        entries_enabled: false,
      },
    });
  });
  await page.route("**/api/bricks?*", (route) =>
    route.fulfill({
      status: 404,
      json: {
        error: {
          code: "http_error",
          message: "Not Found",
          request_id: "missing-stopped-source",
        },
      },
    }),
  );
  await page.route("**/api/signals?*", (route) => {
    signals++;
    return route.continue();
  });
  await login(page);
  await expect(
    page.getByText(/No Renko history for this source yet/),
  ).toBeVisible();
  await expect(
    page.getByText(/Signals are unavailable until Renko history/),
  ).toBeVisible();
  await expect(page.getByText(/Not Found/)).toHaveCount(0);
  expect(signals).toBe(0);
});
