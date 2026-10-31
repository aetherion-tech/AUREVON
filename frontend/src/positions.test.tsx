import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { PnlValue, totalOpenPnl } from "./positions";
import type { Schema } from "./live-data";
afterEach(cleanup);
const positions = (...values: (string | null)[]) =>
  values.map((unrealised) => ({ unrealised }) as Schema["PositionView"]);
it("totals exact server rupees with mixed signs and large amounts", () => {
  expect(totalOpenPnl(positions("90071992547409.91", "0.09", "-0.01"))).toBe(
    "90071992547409.99",
  );
  expect(totalOpenPnl(positions("0.10", "0.20", "-1.00"))).toBe("-0.70");
  expect(totalOpenPnl([])).toBe("0.00");
  expect(totalOpenPnl(positions("10.00", null))).toBeNull();
  expect(totalOpenPnl(positions("NaN"))).toBeNull();
});
it("shows profit, loss, neutral zero and explicit unavailable without treating absence as zero", () => {
  const { rerender } = render(<PnlValue value="10.00" prominent />);
  expect(screen.getByText(/10.00/).className).toContain("pnl-profit");
  rerender(<PnlValue value="-0.01" />);
  expect(screen.getByText(/0.01/).className).toContain("pnl-loss");
  rerender(<PnlValue value="0.00" />);
  expect(screen.getByText(/0.00/).className).not.toMatch(/pnl-profit|pnl-loss/);
  rerender(<PnlValue value={null} />);
  expect(screen.getByText("Unavailable")).toBeTruthy();
});
