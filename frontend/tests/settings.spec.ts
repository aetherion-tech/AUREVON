// Uses only tools/test_server.py's temporary SQLite and dummy wallet on 5174/18765.
// No dotenv, operator database, market feed or ports 5173/8000 are used.
import { test, expect, type Page } from "@playwright/test";
test.beforeEach(async ({ baseURL }) => {
  expect(baseURL).toBe("https://127.0.0.1:5174");
});
async function openSettings(page: Page, ready = true) {
  // Start on the page under test instead of loading 655 unrelated Live fixture
  // bricks before the initial resync; keep the same Connected readiness check.
  await page.goto("/dashboard/settings");
  await page.getByLabel("Dashboard password").fill("browser-fixture-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  if (ready)
    await expect(
      page.getByRole("heading", {
        name: "Versioned paper settings",
        exact: true,
      }),
    ).toBeVisible();
}
async function group(page: Page, name: string) {
  const details = page
    .locator("details")
    .filter({ has: page.locator("summary", { hasText: name }) });
  if ((await details.getAttribute("open")) === null)
    await details.locator("summary").click();
}
async function confirmSave(page: Page, rebuild = false) {
  await page
    .getByRole("button", { name: "Review and save", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("button", { name: "Confirm save" }),
  ).toBeDisabled();
  await dialog.getByLabel("I confirm these paper settings changes").check();
  if (rebuild)
    await dialog
      .getByLabel("I acknowledge a separate indicator/data rebuild is required")
      .check();
  await dialog.getByRole("button", { name: "Confirm save" }).click();
}
test("all backend/Pine defaults render with bounds, dependencies and staged validation", async ({
  page,
}) => {
  await openSettings(page);
  const defaults = await (
    await page.request.get("/api/settings/defaults")
  ).json();
  await expect(page.getByLabel("ATR Length", { exact: true })).toHaveValue(
    String(defaults.pine.atrLen),
  );
  await expect(
    page.getByLabel("Join Supertrend flips with a line"),
  ).toHaveAttribute("title", /continuous line/);
  await group(page, "Trade Plan (Entry / Exit)");
  await expect(
    page.getByLabel("Safety level: max distance (boxes)"),
  ).toBeDisabled();
  await page
    .getByLabel("Also EXIT if the safety level is broken (optional)")
    .check();
  await expect(
    page.getByLabel("Safety level: max distance (boxes)"),
  ).toBeEnabled();
  await group(page, "Strategy, sizing and strikes");
  await expect(
    page.getByLabel("Hedge Target Premium", { exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Hedge Mode", { exact: true }).selectOption("premium");
  await expect(
    page.getByLabel("Hedge Target Premium", { exact: true }),
  ).toBeEnabled();
  await page.getByLabel("Fixed Lots", { exact: true }).fill("0");
  await expect(
    page.getByRole("button", { name: "Review and save" }),
  ).toBeDisabled();
  await expect(
    page.getByText("Outside the allowed bounds.", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Discard edits and load server" })
    .click();
  await expect(
    page.getByText("No unsaved changes", { exact: true }),
  ).toBeVisible();
});
test("keyboard editing and confirmation show the exact reviewed changes", async ({
  page,
}) => {
  await openSettings(page);
  const atr = page.getByLabel("ATR Length", { exact: true });
  await atr.focus();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.type("23");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Factor", { exact: true })).toBeFocused();
  const review = page.getByRole("button", {
    name: "Review and save",
    exact: true,
  });
  await review.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("list", { name: "Changes to save" }),
  ).toContainText("pine.atrLen");
  await expect(
    dialog.getByRole("list", { name: "Changes to save" }),
  ).toContainText("23");
  await expect(
    dialog.getByRole("button", { name: "Confirm save" }),
  ).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(review).toBeFocused();
  await expect(atr).toHaveValue("23");
});

test("temporary settings save acknowledges rebuild and never changes wallet or launches a feed", async ({
  page,
}) => {
  await openSettings(page);
  const before = await (await page.request.get("/api/settings")).json();
  const wallet = await (await page.request.get("/api/wallet")).json();
  await page
    .getByLabel("ATR Length", { exact: true })
    .fill(String(before.settings.pine.atrLen + 1));
  await confirmSave(page, true);
  await expect(
    page.getByText(new RegExp(`Saved revision ${before.revision + 1}`)),
  ).toBeVisible();
  await expect(
    page.getByText(/Rebuild required; no rebuild has been started/),
  ).toBeVisible();
  const after = await (await page.request.get("/api/settings")).json();
  expect(after.revision).toBe(before.revision + 1);
  expect(after.activation).toBe("owner_rebind_required");
  expect(after.requires_rebuild).toBe(true);
  expect(await (await page.request.get("/api/wallet")).json()).toEqual(wallet);
  const snapshot = await (await page.request.get("/api/live/snapshot")).json();
  expect(snapshot.state).toBe("stopped");
  await page.screenshot({
    path: "test-results/settings-desktop.png",
    fullPage: true,
  });
});
test("SPA navigation, browser back and reload guard unsaved edits", async ({
  page,
}) => {
  await openSettings(page);
  // Establish a real in-app previous history entry before testing browser back.
  await page.getByRole("link", { name: "Live", exact: true }).click();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByLabel("ATR Length", { exact: true }).fill("19");
  await page.getByRole("link", { name: "Wallet", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading")).toHaveText(
    "Leave unsaved settings?",
  );
  await dialog.getByRole("button", { name: "Keep editing" }).click();
  await expect(page.getByLabel("ATR Length", { exact: true })).toHaveValue(
    "19",
  );
  await page.goBack();
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Keep editing" }).click();
  const beforeUnload = page.waitForEvent("dialog");
  await page.evaluate(() => {
    setTimeout(() => location.reload(), 0);
  });
  const native = await beforeUnload;
  expect(native.type()).toBe("beforeunload");
  await native.dismiss();
  await expect(page.getByLabel("ATR Length", { exact: true })).toHaveValue(
    "19",
  );
  await page.getByRole("link", { name: "Wallet", exact: true }).click();
  await dialog
    .getByRole("button", { name: "Leave settings", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Paper wallet", exact: true }),
  ).toBeVisible();
});
test("invalid JSON is rejected, valid import/defaults stay local and export is versioned", async ({
  page,
}) => {
  await openSettings(page);
  const before = await (await page.request.get("/api/settings")).json();
  await page
    .getByLabel("Settings JSON", { exact: true })
    .fill('{"version":2,"password":"never-store"}');
  await page.getByRole("button", { name: "Validate and stage import" }).click();
  await expect(page.getByRole("alert").last()).toContainText(
    "Unsupported schema version",
  );
  await page.getByLabel("Settings JSON", { exact: true }).fill(
    JSON.stringify({
      ...before.settings,
      risk: { ...before.settings.risk, max_trades: 7 },
    }),
  );
  await page.getByRole("button", { name: "Validate and stage import" }).click();
  await group(page, "Risk and square-off");
  await expect(page.getByLabel("Max Trades", { exact: true })).toHaveValue("7");
  expect(
    (await (await page.request.get("/api/settings")).json()).revision,
  ).toBe(before.revision);
  await page.getByRole("button", { name: "Restore defaults locally" }).click();
  const defaults = await (
    await page.request.get("/api/settings/defaults")
  ).json();
  await expect(page.getByLabel("Max Trades", { exact: true })).toHaveValue(
    String(defaults.risk.max_trades),
  );
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export saved settings JSON" })
    .click();
  expect((await download).suggestedFilename()).toBe("aurevon-settings-v1.json");
  await page
    .getByRole("button", { name: "Discard edits and load server" })
    .click();
});
test("stale server revision preserves local edits and blocks overwrite", async ({
  page,
}) => {
  let revision = 0;
  await page.route("**/api/settings", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      json: { ...body, revision: body.revision + revision },
    });
  });
  await openSettings(page);
  await page.getByLabel("ATR Length", { exact: true }).fill("21");
  revision = 1;
  await page.getByRole("button", { name: "Refresh data", exact: true }).click();
  await expect(page.getByText(/Server revision changed to/)).toBeVisible();
  await expect(page.getByLabel("ATR Length", { exact: true })).toHaveValue(
    "21",
  );
  await expect(
    page.getByRole("button", { name: "Review and save" }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Discard edits and load server" })
    .click();
  await expect(page.getByText(/Server revision changed to/)).toHaveCount(0);
});
test("lost temporary save reply survives reload with the same key and one revision", async ({
  page,
}) => {
  await openSettings(page);
  const before = await (await page.request.get("/api/settings")).json();
  const keys: string[] = [],
    bodies: string[] = [];
  await page.route("**/api/settings", async (route) => {
    if (route.request().method() !== "PUT") {
      await route.continue();
      return;
    }
    keys.push(route.request().headers()["idempotency-key"]);
    bodies.push(route.request().postData()!);
    const response = await route.fetch();
    if (keys.length === 1) await route.abort("failed");
    else await route.fulfill({ response });
  });
  await group(page, "Saved display settings");
  await page
    .getByLabel("Sounds", { exact: true })
    .setChecked(!before.settings.display.sounds);
  await confirmSave(page);
  await expect(
    page.getByText("A saved request needs review.", { exact: false }),
  ).toBeVisible();
  page.on("dialog", (dialog) => void dialog.accept());
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Retry same settings request" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Retry same settings request" })
    .dblclick();
  await expect(
    page.getByText(new RegExp(`Saved revision ${before.revision + 1}`)),
  ).toBeVisible();
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  expect(bodies[0]).toBe(bodies[1]);
  expect(
    (await (await page.request.get("/api/settings")).json()).revision,
  ).toBe(before.revision + 1);
});
test("server field errors and unavailable settings recover without hiding rejection", async ({
  page,
}) => {
  await page.route("**/api/settings/schema", (route) =>
    route.fulfill({
      status: 503,
      json: {
        error: { code: "unavailable", message: "Settings schema unavailable" },
      },
    }),
  );
  await openSettings(page, false);
  await expect(page.getByRole("alert")).toContainText(
    "Settings schema unavailable",
  );
  await page.unroute("**/api/settings/schema");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Versioned paper settings" }),
  ).toBeVisible();
  await group(page, "Risk and square-off");
  await page.getByLabel("Max Trades", { exact: true }).fill("8");
  await page.route("**/api/settings", (route) =>
    route.request().method() === "PUT"
      ? route.fulfill({
          status: 422,
          json: {
            error: {
              code: "validation_error",
              message: "Request validation failed.",
              details: [
                {
                  location: ["body", "settings", "risk", "max_trades"],
                  code: "test_field_rejection",
                  message: "Invalid value",
                },
              ],
            },
          },
        })
      : route.continue(),
  );
  await confirmSave(page);
  await expect(page.getByRole("alert").first()).toContainText(
    "Request validation failed",
  );
  await expect(
    page.getByText("Invalid value (test_field_rejection)", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Max Trades", { exact: true })).toHaveValue("8");
});
test("read-only preview shows real rejection and mocked accepted economics without an order endpoint", async ({
  page,
}) => {
  await openSettings(page);
  const paths: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST") paths.push(new URL(r.url()).pathname);
  });
  await page.getByLabel("Index spot", { exact: true }).fill("24000");
  await page.getByLabel("Index target 1", { exact: true }).fill("24100");
  await page.getByLabel("Index target 2", { exact: true }).fill("24200");
  await page
    .getByRole("button", { name: "Preview strikes without execution" })
    .click();
  await expect(page.getByText(/Preview rejected:/)).toBeVisible();
  await page.route("**/api/strikes/preview", (route) =>
    route.fulfill({
      json: {
        version: 1,
        accepted: true,
        executable: false,
        reason: "paper_estimate",
        attempts: [],
        candidates: [],
        plan: {
          structure: "BULL_PUT_SPREAD",
          expiry: "2026-11-03",
          lots: 1,
          short: {
            contract: { symbol: "FIXTURE-24000PE", strike: "24000" },
            quantity: 75,
            limit_price: "100.00",
          },
          hedge: {
            contract: { symbol: "FIXTURE-23800PE", strike: "23800" },
            quantity: 75,
            limit_price: "7.50",
          },
          credit: "6937.50",
          required_margin: "15000.00",
          maximum_loss: "8062.50",
          margin_source: "PAPER_ESTIMATE",
          short_quote_at: "2026-10-29T04:00:00Z",
          hedge_quote_at: "2026-10-29T04:00:00Z",
        },
      },
    }),
  );
  await page
    .getByRole("button", { name: "Preview strikes without execution" })
    .click();
  await expect(page.getByText(/Preview accepted:/)).toContainText(
    "Executable: false",
  );
  await expect(page.getByText(/estimated margin/)).toContainText("15,000.00");
  expect(paths).toEqual(["/api/strikes/preview", "/api/strikes/preview"]);
  await page.getByLabel("Index spot", { exact: true }).fill("23900");
  await expect(page.getByText(/Preview accepted:/)).toHaveCount(0);
});
test("local preferences persist, notifications require a click, and settings fit mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    Object.defineProperty(window, "Notification", {
      configurable: true,
      value: class {
        static permission = "denied";
        static async requestPermission() {
          sessionStorage.setItem("notification-requested", "yes");
          return "denied";
        }
      },
    });
  });
  await openSettings(page);
  expect(
    await page.evaluate(() => sessionStorage.getItem("notification-requested")),
  ).toBeNull();
  await page
    .getByLabel("Chart color palette", { exact: true })
    .selectOption("accessible");
  await expect(page.locator("html")).toHaveAttribute(
    "data-palette",
    "accessible",
  );
  await page
    .getByRole("button", { name: "Enable browser notifications", exact: true })
    .click();
  await expect(
    page.getByText(/Notification permission was not granted/),
  ).toBeVisible();
  expect(
    await page.evaluate(() => sessionStorage.getItem("notification-requested")),
  ).toBe("yes");
  await page
    .getByRole("button", { name: "Enable and test event sounds", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Disable event sounds", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Disable event sounds", exact: true })
    .click();
  await page.reload();
  await expect(
    page.getByLabel("Chart color palette", { exact: true }),
  ).toHaveValue("accessible");
  await group(page, "Data and Renko grid");
  await expect(page.getByLabel("Mode", { exact: true })).toHaveValue(
    "minute_close",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/settings-mobile.png",
    fullPage: true,
  });
});
