import { test, expect } from "@playwright/test";

test("closed historical chart loads from the real cache API and remains explicitly stale", async ({
  page,
}) => {
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByText(/Historical \/ stale chart · completed source data through/),
  ).toBeVisible();
  await expect(page.getByTestId("renko-chart")).toBeVisible();
  await expect(page.getByText("5-minute Close · wicks")).toBeVisible();
  const response = await page.request.get("/api/live/snapshot");
  expect(response.ok()).toBeTruthy();
  const snapshot = await response.json();
  expect(snapshot.context.chart_display_mode).toBe("historical");
  expect(snapshot.context.historical_as_of).toBe("2026-10-23T15:30:00+05:30");
  expect(snapshot.quality.stale).toBe(true);
  expect(snapshot.quality.connected).toBe(false);
  expect(snapshot.entries_enabled).toBe(false);
  expect(snapshot.ticks).toEqual([]);
  const history = await (
    await page.request.get(
      `/api/bricks?stream=${encodeURIComponent(snapshot.stream)}&after=-1&limit=300`,
    )
  ).json();
  expect(history.items.length).toBeGreaterThan(0);
  expect(history.configuration.scope).toBe("SPOT_ONLY_DISPLAY");
  expect(history.configuration.future).toBeNull();
  expect(history.configuration.reference_verified).toBe(false);
  const identity = snapshot.configuration_id;
  await page.reload();
  await expect(page.getByTestId("renko-chart")).toBeVisible();
  const reloaded = await (await page.request.get("/api/live/snapshot")).json();
  expect(reloaded.configuration_id).toBe(identity);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(
      page.getByText(
        /Historical \/ stale chart · completed source data through/,
      ),
    ).toBeVisible();
    await expect(page.getByTestId("renko-chart")).toBeVisible();
    await page.screenshot({
      path: `../docs/testing/UI-LIVE-B3-closed-history-${width}.png`,
      fullPage: true,
    });
  }
});
