import { useRef, useState, type FormEvent } from "react";
import { api, cache } from "./state";
import { ApiError } from "./api/client";
import { depositAmount, money } from "./format";
import { paise } from "./history-data";
import { Dialog, ErrorMessage } from "./ui";
import { readIntent, saveIntent, type Intent } from "./intents";
export type WalletAction = "deposit" | "withdraw" | "reset";
export function FinancialDialog({
  kind,
  close,
  free,
}: {
  kind: WalletAction | "kill";
  close: () => void;
  free?: string;
}) {
  const intent = useRef<Intent | null>(readIntent(kind)),
    inFlight = useRef(false);
  const [amount, setAmount] = useState(intent.current?.amount ?? ""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [confirmed, setConfirmed] = useState(false),
    [result, setResult] = useState("");
  const validAmount =
    depositAmount(amount) ||
    (kind === "reset" && /^0+(\.0{1,2})?$/.test(amount));
  const exceedsFree =
    kind === "withdraw" &&
    validAmount &&
    free !== undefined &&
    paise(amount) > paise(free);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (inFlight.current || result) return;
    if (kind !== "kill" && (!validAmount || (!intent.current && exceedsFree)))
      return;
    if (kind === "reset" && !confirmed) return;
    if (!intent.current) {
      intent.current = { key: crypto.randomUUID(), amount };
      saveIntent(kind, intent.current);
    }
    inFlight.current = true;
    setBusy(true);
    setError(undefined);
    try {
      if (kind !== "kill") {
        const wallet = await api.post(
          `/api/wallet/${kind}`,
          kind === "reset"
            ? { amount: intent.current.amount, confirm: "RESET PAPER WALLET" }
            : { amount: intent.current.amount },
          { key: intent.current.key },
        );
        cache.setQueryData(["wallet"], wallet);
        void cache.invalidateQueries({ queryKey: ["wallet"] });
        setResult(
          kind === "deposit"
            ? "Paper deposit recorded."
            : kind === "withdraw"
              ? "Paper withdrawal recorded."
              : "Paper wallet reset recorded. History and risk locks preserved.",
        );
      } else {
        const response = await api.post(
          "/api/kill",
          {},
          { key: intent.current.key },
        );
        setResult(
          `Entries ${response.entries_locked ? "locked" : "not locked"} · ${response.pending_closures} pending closures. ${response.pending_closures ? "Wait for fresh quotes and verify both fills and settlement." : "Verify positions and ledger before resuming."}`,
        );
      }
      void cache.invalidateQueries({ queryKey: ["snapshot"] });
      saveIntent(kind, null);
    } catch (err) {
      setError(err);
      if (err instanceof ApiError && err.status === 401)
        void cache.invalidateQueries({ queryKey: ["session"] });
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={
        kind === "deposit"
          ? "Add paper funds"
          : kind === "withdraw"
            ? "Withdraw paper funds"
            : kind === "reset"
              ? "Reset paper wallet"
              : "Kill paper execution"
      }
      close={close}
      busy={busy}
    >
      <form onSubmit={(e) => void submit(e)}>
        {kind !== "kill" ? (
          <>
            <p>
              Simulated funds only. Maximum ₹9,99,99,99,99,999.99 per amount;
              server balance limits also apply.
            </p>
            <label>
              Amount in INR
              <input
                autoFocus
                inputMode="decimal"
                value={amount}
                disabled={!!intent.current || busy || !!result}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
            {amount && !validAmount && (
              <p role="alert">
                Enter {kind === "reset" ? "a nonnegative" : "a positive"} amount
                with at most two decimal places, within the server limit.
              </p>
            )}
            {kind === "withdraw" && (
              <p>
                Available free paper funds: {money(free)}. Withdrawals cannot
                use blocked capital. The server rechecks current funds.
              </p>
            )}
            {exceedsFree && !intent.current && (
              <p role="alert">Withdrawal exceeds available free funds.</p>
            )}
            {kind === "reset" && (
              <>
                <p>
                  Reset is allowed only with no open/pending positions or
                  reservations. All trades, ledger history, risk counters and
                  loss/kill locks are preserved. This sets the total balance; it
                  is not a profit.
                </p>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    disabled={busy || !!result}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  I confirm RESET PAPER WALLET and preserve history
                </label>
              </>
            )}
          </>
        ) : (
          <p>
            Lock new entries, cancel pending orders and request closure of open
            paper positions. A pending closure is not a completed exit.
          </p>
        )}
        {error !== undefined && (
          <>
            <ErrorMessage error={error} />
            <p>
              The outcome may be uncertain. Retry keeps this action’s original
              amount and key. Closing and submitting a new action could
              duplicate a financial action; check the ledger first. Server
              rejection reasons are shown above; a rejected key keeps its
              original outcome.
            </p>
          </>
        )}
        {result && <p role="status">{result}</p>}
        {intent.current && !result && !busy && (
          <>
            <p>
              An earlier request needs review. Retry preserves the original
              action. Keep this tab open until the outcome is verified.
            </p>
            <button
              type="button"
              onClick={() => {
                saveIntent(kind, null);
                intent.current = null;
                close();
              }}
            >
              I checked the ledger and positions; discard this request
            </button>
          </>
        )}
        {!result && (
          <button
            className={kind === "kill" ? "danger" : ""}
            disabled={
              busy ||
              (kind !== "kill" &&
                (!validAmount || (!intent.current && exceedsFree))) ||
              (kind === "reset" && !confirmed)
            }
          >
            {busy
              ? "Waiting for server…"
              : error
                ? "Retry same action"
                : kind === "kill"
                  ? "Confirm kill"
                  : kind === "withdraw"
                    ? "Confirm withdrawal"
                    : kind === "reset"
                      ? "Confirm reset"
                      : "Add paper funds"}
          </button>
        )}
      </form>
    </Dialog>
  );
}
