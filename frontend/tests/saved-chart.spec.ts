import { test, expect } from "@playwright/test";

test("saved chart and previous signals stay visible without starting market data", async ({
  page,
}) => {
  test.skip(
    process.env.PLAYWRIGHT_SAVED_CHART !== "1",
    "Requires isolated saved-source fixture",
  );
  let starts = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/market/service/start")) starts++;
  });
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const chart = page.getByTestId("renko-chart");
  await expect(chart).toBeVisible();
  await expect(
    page.getByText("Previous saved signals.", { exact: false }),
  ).toBeVisible();
  await expect(chart.locator("[data-marker]").first()).toBeAttached();
  const snapshot = await (await page.request.get("/api/live/snapshot")).json();
  expect(snapshot.desired).toBe(false);
  expect(snapshot.entries_enabled).toBe(false);
  expect(snapshot.context.chart_display_mode).toBe("historical");
  expect(snapshot.context.historical_signals_available).toBe(true);
  const signals = await (
    await page.request.get(
      `/api/signals?stream=${encodeURIComponent(snapshot.stream)}`,
    )
  ).json();
  expect(signals.items.length).toBeGreaterThan(0);
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await expect(chart).toBeVisible();
    await chart.screenshot({
      path: `test-results/saved-chart-${viewport.width}.png`,
    });
  }
  await page.reload();
  await expect(chart).toBeVisible();
  const after = await (await page.request.get("/api/live/snapshot")).json();
  expect(after.stream).toBe(snapshot.stream);
  expect(after.configuration_id).toBe(snapshot.configuration_id);
  expect(after.desired).toBe(false);
  expect(starts).toBe(0);
});
