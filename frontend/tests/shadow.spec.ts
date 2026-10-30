import { test, expect } from "@playwright/test";

test("shadow comparison is explicitly disabled by default", async ({
  page,
}) => {
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "TradingView shadow comparison" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Shadow ingestion is disabled. No TradingView comparison evidence is available.",
    ),
  ).toBeVisible();
});

test("mocked comparison shows both mismatch directions and the pending window", async ({
  page,
}) => {
  await page.route("**/api/shadow/status", (route) =>
    route.fulfill({
      json: {
        enabled: true,
        stream: "synthetic-browser",
        source_id: "a".repeat(64),
        latest_index: 20,
        note: "Synthetic browser fixture only",
      },
    }),
  );
  await page.route("**/api/shadow/comparison?*", (route) =>
    route.fulfill({
      json: {
        source_id: "a".repeat(64),
        start: 0,
        end: 20,
        matched: 3,
        pending: 1,
        missing_tradingview: ["synthetic-browser:5:0"],
        missing_backend: ["tv-fixture-7"],
        reference_verified: false,
      },
    }),
  );
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByText(
      "Shadow mismatch: 1 missing from TradingView; 1 missing from backend.",
    ),
  ).toBeVisible();
  await page.getByText("Mismatch event identifiers", { exact: true }).click();
  await expect(page.getByText("Backend missing: tv-fixture-7")).toBeVisible();
  await expect(
    page.getByText("TradingView missing: synthetic-browser:5:0"),
  ).toBeVisible();
  await expect(page.getByText(/3 matched · 1 awaiting/)).toBeVisible();
});
