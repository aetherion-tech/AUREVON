import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { FinancialDialog } from "./FinancialDialog";
import { WalletPage } from "./WalletPage";
import { api, cache } from "./state";
import { saveIntent } from "./intents";

afterEach(() => {
  cleanup();
  cache.clear();
  vi.restoreAllMocks();
  for (const k of ["deposit", "withdraw", "reset"]) saveIntent(k, null);
});
function dialog(kind: "withdraw" | "reset", free = "1.00") {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  render(<FinancialDialog kind={kind} free={free} close={() => {}} />);
  return userEvent.setup();
}
it("blocks insufficient withdrawals using exact paise at the storage limit", async () => {
  const post = vi.spyOn(api, "post");
  const user = dialog("withdraw", "999999999999.98");
  await user.type(screen.getByLabelText("Amount in INR"), "999999999999.99");
  expect(screen.getByRole("alert").textContent).toContain("exceeds available");
  await user.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  expect(post).not.toHaveBeenCalled();
});
it("requires reset confirmation, permits zero and sends the exact API confirmation", async () => {
  const post = vi
    .spyOn(api, "post")
    .mockResolvedValue({ mode: "PAPER", free: "0.00" } as never);
  const user = dialog("reset");
  await user.type(screen.getByLabelText("Amount in INR"), "0.00");
  await user.click(screen.getByRole("button", { name: "Confirm reset" }));
  expect(post).not.toHaveBeenCalled();
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Confirm reset" }));
  await screen.findByText(/reset recorded/);
  expect(post.mock.calls[0][1]).toEqual({
    amount: "0.00",
    confirm: "RESET PAPER WALLET",
  });
});
it("recovers ambiguous withdrawals after remount with the original body and key", async () => {
  const post = vi
    .spyOn(api, "post")
    .mockRejectedValueOnce(new Error("lost reply"))
    .mockResolvedValueOnce({ free: "0.99" } as never);
  let user = dialog("withdraw");
  await user.type(screen.getByLabelText("Amount in INR"), "0.01");
  await user.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  await screen.findByText(/outcome may be uncertain/);
  cleanup();
  // The original action may already have reduced the free balance.
  user = dialog("withdraw", "0.00");
  await user.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  await screen.findByText("Paper withdrawal recorded.");
  expect(post.mock.calls[0]).toEqual(post.mock.calls[1]);
});
it("blocks duplicate withdrawal clicks while awaiting the server", async () => {
  let resolve!: (value: never) => void;
  const post = vi.spyOn(api, "post").mockImplementation(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  const user = dialog("withdraw");
  await user.type(screen.getByLabelText("Amount in INR"), "0.01");
  await user.dblClick(
    screen.getByRole("button", { name: "Confirm withdrawal" }),
  );
  expect(post).toHaveBeenCalledTimes(1);
  resolve({ free: "0.99" } as never);
  await screen.findByText("Paper withdrawal recorded.");
});
it("invalidates balances and every ledger page after a successful mutation", async () => {
  vi.spyOn(api, "post").mockResolvedValue({ free: "0.99" } as never);
  cache.setQueryData(["wallet", "ledger", "PAPER", 0], { items: [] });
  cache.setQueryData(["wallet", "ledger", "PAPER", 25], { items: [] });
  const user = dialog("withdraw");
  await user.type(screen.getByLabelText("Amount in INR"), "0.01");
  await user.click(screen.getByRole("button", { name: "Confirm withdrawal" }));
  await screen.findByText("Paper withdrawal recorded.");
  for (const offset of [0, 25])
    expect(
      cache.getQueryState(["wallet", "ledger", "PAPER", offset])?.isInvalidated,
    ).toBe(true);
  expect(cache.getQueryData(["wallet"])).toEqual({ free: "0.99" });
});
it("rejects non-PAPER wallet responses and does not query their ledger", async () => {
  const get = vi
    .spyOn(api, "get")
    .mockResolvedValue({
      mode: "LIVE",
      initialized: true,
      free: "10.00",
    } as never);
  render(
    <QueryClientProvider client={cache}>
      <WalletPage action={() => {}} />
    </QueryClientProvider>,
  );
  await screen.findByText(
    "PAPER wallet unavailable. Financial actions are disabled.",
  );
  expect(
    (
      screen.getByRole("button", {
        name: "Withdraw paper funds",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  expect(get).toHaveBeenCalledTimes(1);
});
