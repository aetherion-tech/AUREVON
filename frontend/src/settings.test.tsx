import { afterEach, expect, it } from "vitest";
import {
  canonical,
  contract,
  dependency,
  getAt,
  importSettings,
  pendingSettings,
  resolve,
  setAt,
  settingsChanges,
  validateSettings,
  type Bundle,
  type Json,
  type Rule,
} from "./settings-data";
function defaults(input: Rule = contract.schema): Json {
  const rule = resolve(input);
  if (rule.default !== undefined) return structuredClone(rule.default);
  if (rule.type === "object")
    return Object.fromEntries(
      Object.entries(rule.properties ?? {}).map(([key, r]) => [
        key,
        key === "pine"
          ? Object.fromEntries(
              Object.entries(contract.pine).map(([k, v]) => [k, v.default]),
            )
          : defaults(r),
      ]),
    );
  return null;
}
afterEach(() => pendingSettings(null));
it("reviews exact changed fields without counting key order or untouched groups", () => {
  const before = defaults();
  const after = setAt(before, "wallet.initial_capital", "999999999999.99");
  expect(settingsChanges(before, after)).toEqual([
    {
      path: "wallet.initial_capital",
      before: getAt(before, "wallet.initial_capital"),
      after: "999999999999.99",
    },
  ]);
  expect(settingsChanges({ a: 1, b: false }, { b: false, a: 1 })).toEqual([]);
});
it("accepts every generated backend default and preserves Pine defaults through JSON", () => {
  const bundle = defaults();
  expect(validateSettings(bundle)).toEqual({});
  expect(importSettings(JSON.stringify(bundle))).toEqual(bundle);
  expect(getAt(bundle, "pine.factor")).toBe(2.5);
  expect(getAt(bundle, "pine.exitOppN")).toBe(1);
  expect(getAt(bundle, "strategy.hedge_target_premium")).toBe("7.50");
  expect(Object.keys(contract.ui)).toEqual(Object.keys(contract.pine));
});
it("rejects unsupported versions, unknown fields and unsafe integer imports", () => {
  const bundle = defaults();
  for (const bad of [
    setAt(bundle, "version", 2),
    setAt(bundle, "strategy.fixed_lots", "2"),
    setAt(bundle, "strategy.fixed_lots", 0),
    setAt(bundle, "risk.max_trades", Number.MAX_SAFE_INTEGER + 1),
    setAt(bundle, "pine.unexpected", true),
  ])
    expect(() => importSettings(JSON.stringify(bad))).toThrow();
  expect(() => importSettings('{"version":1}')).toThrow();
  expect(() => importSettings("x".repeat(200001))).toThrow("200 KB");
});
it("validates exact decimals, precision and risk limits without float rounding", () => {
  const bundle = defaults();
  expect(
    validateSettings(
      setAt(bundle, "wallet.initial_capital", "999999999999.99"),
    ),
  ).toEqual({});
  expect(
    validateSettings(
      setAt(bundle, "wallet.initial_capital", "1000000000000.00"),
    )["wallet.initial_capital"],
  ).toBeTruthy();
  expect(
    validateSettings(setAt(bundle, "wallet.initial_capital", "1.001"))[
      "wallet.initial_capital"
    ],
  ).toBeTruthy();
  for (const value of [
    "NaN",
    "Infinity",
    "1e3",
    "-1",
    "100.00000000000000000001",
  ])
    expect(
      validateSettings(setAt(bundle, "risk.daily_loss_pct", value))[
        "risk.daily_loss_pct"
      ],
    ).toBeTruthy();
});
it("validates local IST windows, square-off and ORB HHMM", () => {
  const bundle = defaults();
  expect(
    validateSettings(setAt(bundle, "strategy.entry_start", "15:00:00"))[
      "strategy.entry_end"
    ],
  ).toBeTruthy();
  expect(
    validateSettings(setAt(bundle, "risk.square_off", "14:00:00"))[
      "risk.square_off"
    ],
  ).toBeTruthy();
  expect(
    validateSettings(setAt(bundle, "risk.entry_start", "09:30:00+05:30"))[
      "risk.entry_start"
    ],
  ).toBeTruthy();
  expect(
    validateSettings(setAt(bundle, "pine.orbUntil", 1160))["pine.orbUntil"],
  ).toBeTruthy();
});
it("synchronizes the grid in both directions and rejects mismatched imports", () => {
  const bundle = defaults();
  expect(getAt(setAt(bundle, "data.box", "25.5"), "pine.boxSize")).toBe(25.5);
  expect(getAt(setAt(bundle, "pine.boxSize", 75), "data.box")).toBe("75");
  const bad = structuredClone(bundle) as Record<string, Json>;
  (bad.data as Record<string, Json>).box = "75";
  expect(validateSettings(bad)["data.box"]).toBeTruthy();
});
it("keeps disabled field values and checks actual parent dependencies", () => {
  const bundle = defaults();
  expect(dependency("pine.stopCapBx", bundle)).toContain("exitOnStop");
  expect(dependency("strategy.hedge_target_premium", bundle)).toContain(
    "premium",
  );
  expect(
    dependency("pine.oiMinPct", setAt(bundle, "pine.useOI", false)),
  ).toContain("useOI");
  expect(getAt(bundle, "pine.stopCapBx")).toBe(6);
  expect(dependency("pine.rsiLen", bundle)).toBeUndefined();
});
it("stores a frozen versioned recovery command and canonicalizes key order", () => {
  const request = {
    key: "test-settings-key",
    body: {
      expected_revision: 3,
      settings: defaults() as Bundle,
      rebuild: false,
    },
  };
  pendingSettings(request);
  expect(pendingSettings()).toEqual(request);
  expect(canonical({ b: 2, a: 1 })).toBe(canonical({ a: 1, b: 2 }));
  pendingSettings(null);
  expect(pendingSettings()).toBeNull();
});
