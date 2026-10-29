import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { money, ist, percent, depositAmount } from "./format";
import { LiveCursor, type Snapshot, type Event } from "./api/client";
import { reduceEvent, api } from "./state";
import { FinancialDialog } from "./App";
import { readIntent, saveIntent } from "./intents";
afterEach(() => {
  cleanup();
  saveIntent("deposit", null);
  saveIntent("kill", null);
});
const snapshot = {
  run_id: "r",
  sequence: 0,
  ticks: [],
  signals: [],
  positions: [],
  latest_brick: null,
} as unknown as Snapshot;
describe("financial and temporal formats", () => {
  it("preserves paise and Indian grouping at the storage limit", () => {
    expect(money("999999999999.99")).toBe("₹9,99,99,99,99,999.99");
    expect(money("-123456.01")).toBe("−₹1,23,456.01");
    expect(money(null)).toBe("Unavailable");
  });
  it("validates exact positive bounded deposits", () => {
    for (const v of ["0", "-1", "1e2", "1.001", "1000000000000.00", "NaN"])
      expect(depositAmount(v)).toBe(false);
    expect(depositAmount("0.01")).toBe(true);
    expect(depositAmount("999999999999.99")).toBe(true);
  });
  it("uses IST independent of the browser timezone", () => {
    expect(ist("2026-10-29T00:00:00Z")).toContain("5:30:00");
    expect(ist("bad")).toBe("Unavailable");
    expect(percent(null)).toBe("Unavailable");
  });
});
describe("ordered projections", () => {
  it("rejects gaps atomically and ignores duplicate events", () => {
    const c = new LiveCursor();
    c.reset(snapshot);
    const e = {
      run_id: "r",
      sequence: 1,
      kind: "tick",
      payload: { token: 1, price: "1.00", time: "x" },
    } as Event;
    const frame = {
      type: "events" as const,
      run_id: "r",
      sequence: 1,
      events: [e],
      api_version: "1.0" as const,
    };
    expect(c.accept(frame).events).toHaveLength(1);
    expect(c.accept(frame).events).toHaveLength(0);
    expect(
      c.accept({ ...frame, sequence: 3, events: [{ ...e, sequence: 3 }] })
        .resync,
    ).toBe(true);
    expect(c.sequence).toBe(1);
  });
  it("keeps chart references stable on ticks and deduplicates signal ids", () => {
    const e = {
      sequence: 1,
      kind: "tick",
      payload: { token: 1, price: "1.00" },
    } as Event;
    const next = reduceEvent(snapshot, e);
    expect(next.signals).toBe(snapshot.signals);
    expect(next.positions).toBe(snapshot.positions);
    const signal = {
      sequence: 2,
      kind: "signal",
      payload: { id: "a" },
    } as Event;
    expect(reduceEvent(reduceEvent(next, signal), signal).signals).toHaveLength(
      1,
    );
  });
});
describe("financial action safety", () => {
  it("recovers the action across dialog destruction without changing its key", () => {
    const saved = { key: "pending-original", amount: "12.01" };
    saveIntent("deposit", saved);
    expect(readIntent("deposit")).toEqual(saved);
    expect(
      JSON.parse(sessionStorage.getItem("aurevon.pending.deposit")!),
    ).toEqual(saved);
    saveIntent("deposit", null);
    expect(readIntent("deposit")).toBeNull();
  });
  it("retries a lost reply using the same key and frozen amount", async () => {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute("open", "");
    };
    const post = vi
      .spyOn(api, "post")
      .mockRejectedValueOnce(new Error("lost reply"))
      .mockResolvedValueOnce({ free: "1.00" } as never);
    render(<FinancialDialog kind="deposit" close={() => {}} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Amount in INR"), "1.00");
    await user.click(screen.getByRole("button", { name: "Add paper funds" }));
    await screen.findByText(/outcome may be uncertain/);
    expect(
      (screen.getByLabelText("Amount in INR") as HTMLInputElement).disabled,
    ).toBe(true);
    await user.click(screen.getByRole("button", { name: "Retry same action" }));
    await screen.findByText("Paper deposit recorded.");
    expect(post.mock.calls[0]).toEqual(post.mock.calls[1]);
  });
  it("blocks duplicate kill clicks and reports pending closures", async () => {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute("open", "");
    };
    let resolve!: (v: never) => void;
    const post = vi.spyOn(api, "post").mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    render(<FinancialDialog kind="kill" close={() => {}} />);
    const user = userEvent.setup();
    await user.dblClick(screen.getByRole("button", { name: "Confirm kill" }));
    expect(post).toHaveBeenCalledTimes(1);
    resolve({ entries_locked: true, pending_closures: 2 } as never);
    await screen.findByText(/2 pending closures/);
  });
});
