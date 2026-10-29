import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  historyFilters,
  paise,
  pnlSeries,
  rupees,
  validDay,
  winRate,
} from "./history-data";
import { PnlChart } from "./HistoryPage";
import type { Schema } from "./live-data";
afterEach(cleanup);
it("round-trips storage-limit money and negative paise without floating arithmetic", () => {
  expect(rupees(paise("999999999999.99") + paise("0.01"))).toBe(
    "1000000000000.00",
  );
  expect(rupees(paise("-0.01"))).toBe("-0.01");
  expect(() => paise("1.001")).toThrow();
});
it("sorts IST buckets and accumulates exact profit without including cash-flow fields", () => {
  const rows = [
    { start: "2026-10-29", net: "-0.01", external_flows: "10000.00" },
    { start: "2026-10-28", net: "0.03", external_flows: "10000.00" },
  ] as Schema["PnlSummary"][];
  expect(pnlSeries(rows)).toEqual([
    { day: "2026-10-28", net: "0.03", cumulative: "0.03" },
    { day: "2026-10-29", net: "-0.01", cumulative: "0.02" },
  ]);
});
it("leaves zero-denominator win rate unavailable", () => {
  expect(winRate(0, 0)).toBe("Unavailable");
  expect(winRate(1, 3)).toBe("33.33%");
  expect(winRate(1, 1)).toBe("100%");
});
it("parses all typed URL filters and keeps exact server sort choices", () => {
  const { query, error } = historyFilters(
    new URLSearchParams(
      "start=2026-10-01&end=2026-10-29&family=CO&direction=-1&grade=3&result=WIN&sort=net&order=asc",
    ),
    "2026-10-29",
  );
  expect(error).toBe("");
  expect(query).toEqual({
    mode: "PAPER",
    start: "2026-10-01",
    end: "2026-10-29",
    family: "CO",
    direction: -1,
    grade: 3,
    result: "WIN",
    sort: "net",
    order: "asc",
  });
});
it("rejects bad calendar dates, future/reversed ranges, unsupported grades and live mode", () => {
  expect(validDay("2026-02-30")).toBe(false);
  for (const value of [
    "start=2026-10-30",
    "end=2026-10-30",
    "grade=4",
    "mode=LIVE",
    "start=bad",
  ])
    expect(
      historyFilters(new URLSearchParams(value), "2026-10-29").error,
    ).not.toBe("");
});
it("renders explicit no-bucket and exact chart values", () => {
  const { rerender } = render(<PnlChart title="Daily" rows={[]} />);
  expect(screen.getByText("No reporting buckets available.")).toBeTruthy();
  rerender(
    <PnlChart
      title="Daily"
      rows={[{ start: "2026-10-29", net: "0.00" } as Schema["PnlSummary"]]}
    />,
  );
  expect(screen.getByRole("img")).toBeTruthy();
  expect(screen.getAllByText("₹0.00")).toHaveLength(2);
});
