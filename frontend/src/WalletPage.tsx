import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./state";
import { paise } from "./history-data";
import { money, ist } from "./format";
import { Card, ErrorMessage } from "./ui";
import type { WalletAction } from "./FinancialDialog";

export function WalletPage({
  action,
}: {
  action: (kind: WalletAction) => void;
}) {
  const [offset, setOffset] = useState(0);
  const wallet = useQuery({
    queryKey: ["wallet"],
    queryFn: ({ signal }) =>
      api.get("/api/wallet", { mode: "PAPER" }, { signal }),
    refetchInterval: 15000,
  });
  const ledger = useQuery({
    queryKey: ["wallet", "ledger", "PAPER", offset],
    queryFn: ({ signal }) =>
      api.get(
        "/api/wallet/ledger",
        { mode: "PAPER", offset, limit: 25 },
        { signal },
      ),
    enabled: !!wallet.data?.initialized && wallet.data.mode === "PAPER",
    refetchInterval: 15000,
  });
  const w = wallet.data?.mode === "PAPER" ? wallet.data : undefined;
  const available = !!w?.initialized && !wallet.isError && !wallet.isFetching;
  return (
    <>
      <div className="readiness">
        <div className="eyebrow">SIMULATED ACCOUNT / INR</div>
        <h1>Paper wallet</h1>
        <p>
          Simulated funds only. These balances are separate from broker funds
          and the project cash budget.
        </p>
      </div>
      {wallet.isPending && <p role="status">Loading paper wallet…</p>}
      {wallet.error && (
        <ErrorMessage
          error={wallet.error}
          retry={() => void wallet.refetch()}
        />
      )}
      {!wallet.isPending && !w && !wallet.error && (
        <p role="alert">
          PAPER wallet unavailable. Financial actions are disabled.
        </p>
      )}
      {wallet.isError && w && (
        <p className="warning">
          Balances below are the last known snapshot. Refresh before financial
          actions.
        </p>
      )}
      {w && !w.initialized && (
        <p role="alert">
          Wallet is not initialized. An attached paper owner must configure it
          first.
        </p>
      )}
      <div className="summary-cards wallet-balances">
        <Card title="Total paper capital">
          <p className="metric">{money(w?.balance)}</p>
          <small>Free plus blocked capital; not marked-to-market equity.</small>
        </Card>
        <Card title="Free paper capital">
          <p className="metric">{money(w?.free)}</p>
          <small>Available for reservations and withdrawals.</small>
        </Card>
        <Card title="Blocked paper capital">
          <p className="metric">{money(w?.reserved)}</p>
          <small>Reserved by the paper execution book.</small>
        </Card>
      </div>
      <Card title="Manage paper funds">
        <p>
          Exact INR amounts, at most two decimal places. Maximum per amount and
          resulting balance: {money("999999999999.99")}. Current free funds and
          exposure may impose lower limits.
        </p>
        <div className="history-actions">
          <button disabled={!available} onClick={() => action("deposit")}>
            Deposit paper funds
          </button>
          <button disabled={!available} onClick={() => action("withdraw")}>
            Withdraw paper funds
          </button>
          <button
            className="danger"
            disabled={!available || (w ? paise(w.reserved) !== 0n : true)}
            onClick={() => action("reset")}
          >
            Reset paper wallet
          </button>
        </div>
        <p className="muted">
          Reset requires a flat book with no pending positions or reservations;
          the server checks this atomically. History and risk locks always
          survive reset.
        </p>
        <button disabled>Delete paper history — unavailable</button>
        <p className="muted">
          No history-deletion API is implemented. There is no destructive action
          to confirm or send.
        </p>
      </Card>
      <Card title="Automatic paper top-up">
        <p>
          Owner setting:{" "}
          <strong>
            {w ? (w.auto_topup ? "Enabled" : "Disabled") : "Unavailable"}
          </strong>
        </p>
        <p>
          When enabled, the owner may add simulated funds required by an
          eligible paper admission. Top-ups and manual deposits are cash flows,
          never trading profit; returns exclude cash flows. Planning capital is
          a simulated funding ceiling, not free cash or project cash.
        </p>
        <p className="muted">
          This is the attached owner's effective setting. Settings changes
          require the versioned settings flow and a safe owner rebind; this
          screen does not toggle it.
        </p>
        {w && (
          <p>
            Entry locks: {w.killed ? "Kill active" : "Kill inactive"} ·{" "}
            {w.loss_locked ? "Loss lock active" : "Loss lock inactive"}. Reset
            does not clear these locks.
          </p>
        )}
      </Card>
      <Card title="Paper ledger">
        <p>
          Oldest first, in server sequence order. Running balances include all
          preceding entries, including earlier pages. COSTS are charges;
          REALISED_GROSS is gross trading P&amp;L. RESERVE/RELEASE change
          blocked capital, not profit. INITIAL/DEPOSIT/WITHDRAW/RESET are
          funding adjustments, not profit.
        </p>
        {ledger.isPending && w?.initialized && (
          <p role="status">Loading ledger…</p>
        )}
        {ledger.error && (
          <ErrorMessage
            error={ledger.error}
            retry={() => void ledger.refetch()}
          />
        )}
        {!w?.initialized && (
          <p>
            Ledger unavailable until an initialized PAPER wallet is attached.
          </p>
        )}
        {w?.initialized && ledger.data && (
          <>
            <div className="table-scroll">
              <table aria-label="Paper wallet ledger">
                <thead>
                  <tr>
                    <th>Sequence</th>
                    <th>Time (IST)</th>
                    <th>Type</th>
                    <th>Amount</th>
                    <th>Running balance</th>
                    <th>Blocked</th>
                    <th>Reference</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.data.items.map((e) => (
                    <tr key={e.sequence}>
                      <td>{e.sequence}</td>
                      <td>{ist(e.at)}</td>
                      <td>{e.kind}</td>
                      <td>{money(e.amount)}</td>
                      <td>{money(e.balance)}</td>
                      <td>{money(e.reserved)}</td>
                      <td className="source-identity">{e.key}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!ledger.data.items.length && (
              <p>No ledger entries on this page.</p>
            )}
            <div className="history-actions">
              <button
                disabled={offset === 0 || ledger.isFetching}
                onClick={() => setOffset(0)}
              >
                First ledger page
              </button>
              <button
                disabled={offset === 0 || ledger.isFetching}
                onClick={() => setOffset(Math.max(0, offset - 25))}
              >
                Previous ledger page
              </button>
              <span>
                Entries {offset + (ledger.data.items.length ? 1 : 0)}–
                {offset + ledger.data.items.length}
              </span>
              <button
                disabled={
                  ledger.data.pagination.next_offset == null ||
                  ledger.isFetching
                }
                onClick={() => setOffset(ledger.data.pagination.next_offset!)}
              >
                Next ledger page
              </button>
            </div>
          </>
        )}
      </Card>
    </>
  );
}
