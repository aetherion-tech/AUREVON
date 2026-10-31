import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/dashboard/");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Live paper desk" }),
  ).toBeVisible();
}

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "wait" });
});

test("B4 positions and summary stay coherent through refresh, stale, missing, error and empty states", async ({
  page,
}) => {
  let stage:
    "fresh" | "updated" | "stale" | "future" | "missing" | "error" | "empty" =
    "fresh";
  await page.route("**/api/positions/open", (route) => {
    if (stage === "error")
      return route.fulfill({
        status: 500,
        json: {
          error: {
            code: "fixture_positions_unavailable",
            message: "Fixture positions unavailable",
          },
        },
      });
    const at = new Date(
      Date.now() +
        (stage === "stale" ? -60000 : stage === "future" ? 60000 : -2000),
    ).toISOString();
    const position = (
      id: string,
      pnl: string | null,
      shortMark: string | null,
      shortPnl: string | null,
      hedgeMark: string,
      hedgePnl: string,
    ) => ({
      trade_id: id,
      state: "OPEN",
      created_at: "2026-10-29T09:30:00+05:30",
      mark_at: at,
      margin: "10000.00",
      unrealised: pnl,
      legs: [
        {
          role: "SHORT",
          symbol: `${id} SHORT`,
          quantity: 25,
          entry: "100.00",
          mark: shortMark,
          strike: "24000",
          expiry: "2026-11-03",
          lot_size: 25,
          unrealised: shortPnl,
        },
        {
          role: "HEDGE",
          symbol: `${id} HEDGE`,
          quantity: 25,
          entry: "10.00",
          mark: hedgeMark,
          strike: "23800",
          expiry: "2026-11-03",
          lot_size: 25,
          unrealised: hedgePnl,
        },
      ],
    });
    return route.fulfill({
      json:
        stage === "empty"
          ? []
          : [
              position(
                "B4-A",
                stage === "missing"
                  ? null
                  : stage === "updated"
                    ? "2.50"
                    : "1.25",
                stage === "missing"
                  ? null
                  : stage === "updated"
                    ? "99.85"
                    : "99.90",
                stage === "missing"
                  ? null
                  : stage === "updated"
                    ? "3.75"
                    : "2.50",
                "9.95",
                "-1.25",
              ),
              position(
                "B4-B",
                stage === "updated" ? "-1.25" : "-2.50",
                stage === "updated" ? "100.05" : "100.10",
                stage === "updated" ? "-1.25" : "-2.50",
                "10.00",
                "0.00",
              ),
            ],
    });
  });
  await login(page);
  const summary = page.getByRole("complementary", {
    name: "Strategy and P&L summary",
  });
  const positions = page.getByRole("region", {
    name: "Open positions",
    exact: true,
  });
  const total = summary.locator(".pnl-total");
  const spreadA = positions.getByRole("article", { name: "Spread B4-A" });
  const shortA = spreadA.getByRole("row").filter({ hasText: "B4-A SHORT" });
  await expect(total).toHaveText(/1.25/);
  await expect(total).toHaveClass(/pnl-loss/);
  await expect(positions.getByRole("article")).toHaveCount(2);
  await expect(
    shortA.getByRole("cell", { name: "99.90", exact: true }),
  ).toBeVisible();
  await expect(shortA.locator(".pnl-profit")).toHaveText(/2.50/);
  stage = "updated";
  await page.getByRole("button", { name: "Refresh data", exact: true }).click();
  await expect(total).toHaveClass(/pnl-profit/);
  await expect(total).toHaveText(/1.25/);
  await expect(
    shortA.getByRole("cell", { name: "99.85", exact: true }),
  ).toBeVisible();
  await expect(shortA.locator(".pnl-profit")).toHaveText(/3.75/);
  await expect(spreadA.getByText(/Mark received/)).toBeVisible();
  await expect(summary.getByText(/total is not a fresh valuation/)).toHaveCount(
    0,
  );
  for (const next of ["future", "stale"] as const) {
    stage = next;
    await page
      .getByRole("button", { name: "Refresh data", exact: true })
      .click();
    await expect(
      summary.getByText(/total is not a fresh valuation/),
    ).toBeVisible();
    await expect(spreadA.getByText(/Stale or unavailable mark/)).toBeVisible();
  }
  stage = "missing";
  await page.getByRole("button", { name: "Refresh data", exact: true }).click();
  await expect(total).toHaveText("Unavailable");
  await expect(
    shortA.getByRole("cell", { name: "Unavailable", exact: true }),
  ).toHaveCount(2);
  stage = "error";
  await page.getByRole("button", { name: "Refresh data", exact: true }).click();
  await expect(total).toHaveText("Unavailable");
  await expect(summary.getByRole("alert")).toBeVisible();
  await expect(positions.getByRole("alert")).toBeVisible();
  stage = "empty";
  await page.getByRole("button", { name: "Refresh data", exact: true }).click();
  await expect(total).toHaveText(/0.00/);
  await expect(positions.getByText("No active paper spread.")).toBeVisible();
  await expect(positions.getByRole("article")).toHaveCount(0);
});
