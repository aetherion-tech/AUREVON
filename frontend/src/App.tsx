import {
  useCallback,
  useEffect,
  useRef,
  useState,
  memo,
  type FormEvent,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, Route, Routes } from "react-router-dom";
import { api, cache } from "./state";
import { ApiError } from "./api/client";
import { useLive } from "./live";
import { depositAmount, ist, money } from "./format";
import { Card, Dialog, ErrorMessage } from "./ui";
import { readIntent, saveIntent, type Intent } from "./intents";
import { LivePage } from "./LivePage";
import { HistoryPage } from "./HistoryPage";

function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return <time>{ist(now)}</time>;
}
const TopStatus = memo(function TopStatus() {
  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["snapshot"],
    queryFn: ({ signal }) =>
      api.get("/api/live/snapshot", undefined, { signal }),
    refetchInterval: 15000,
  });
  const tick = data?.ticks.find((t) => t.token === data.selected?.spot);
  const old = tick && Date.now() - new Date(tick.time).getTime() > 15000;
  return (
    <div className="status">
      <strong>NIFTY · {tick ? money(tick.price) : "Price unavailable"}</strong>
      <span className="chip">Feed: {data?.state ?? "Unavailable"}</span>
      <span className="chip">
        Market:{" "}
        {typeof data?.context.session_state === "string"
          ? data.context.session_state
          : "Unavailable"}
      </span>
      {(old || data?.quality.stale) && (
        <span className="warning">Stale prices</span>
      )}
      <Clock />
      {isPending && <span role="status">Loading feed status…</span>}
      {error && <ErrorMessage error={error} retry={() => void refetch()} />}
    </div>
  );
});
export function FinancialDialog({
  kind,
  close,
}: {
  kind: "deposit" | "kill";
  close: () => void;
}) {
  const intent = useRef<Intent | null>(readIntent(kind)),
    inFlight = useRef(false);
  const [amount, setAmount] = useState(intent.current?.amount ?? ""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [result, setResult] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (inFlight.current || result) return;
    if (kind === "deposit" && !depositAmount(amount)) return;
    if (!intent.current) {
      intent.current = { key: crypto.randomUUID(), amount };
      saveIntent(kind, intent.current);
    }
    inFlight.current = true;
    setBusy(true);
    setError(undefined);
    try {
      if (kind === "deposit") {
        const wallet = await api.post(
          "/api/wallet/deposit",
          { amount: intent.current.amount },
          { key: intent.current.key },
        );
        cache.setQueryData(["wallet"], wallet);
        setResult("Paper deposit recorded.");
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
      title={kind === "deposit" ? "Add paper funds" : "Kill paper execution"}
      close={close}
      busy={busy}
    >
      <form onSubmit={(e) => void submit(e)}>
        {kind === "deposit" ? (
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
                disabled={!!intent.current}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
            {amount && !depositAmount(amount) && (
              <p role="alert">
                Enter a positive amount with at most two decimal places.
              </p>
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
              duplicate a deposit; check the ledger first.
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
            disabled={busy || (kind === "deposit" && !depositAmount(amount))}
          >
            {busy
              ? "Waiting for server…"
              : error
                ? "Retry same action"
                : kind === "kill"
                  ? "Confirm kill"
                  : "Add paper funds"}
          </button>
        )}
      </form>
    </Dialog>
  );
}
function WalletChip({ deposit }: { deposit: () => void }) {
  const wallet = useQuery({
    queryKey: ["wallet"],
    queryFn: ({ signal }) => api.get("/api/wallet", undefined, { signal }),
    refetchInterval: 15000,
  });
  return (
    <div className="wallet-chip">
      <span>
        Paper free cash{" "}
        <strong>{wallet.data ? money(wallet.data.free) : "Unavailable"}</strong>
      </span>
      <button onClick={deposit} disabled={!wallet.data?.initialized}>
        Add paper funds
      </button>
      {wallet.error && (
        <ErrorMessage
          error={wallet.error}
          retry={() => void wallet.refetch()}
        />
      )}
    </div>
  );
}
function Kite() {
  const kite = useQuery({
    queryKey: ["kite"],
    queryFn: ({ signal }) =>
      api.get("/api/auth/kite/status", undefined, { signal }),
    refetchInterval: 30000,
  });
  const data = kite.data;
  const expired =
    data?.expires_at && new Date(data.expires_at).getTime() <= Date.now();
  return (
    <div className="kite">
      <span>
        Kite:{" "}
        {data
          ? !data.configured
            ? "Not configured"
            : expired
              ? "Expired"
              : data.authenticated
                ? "Verified"
                : "Configured · login required"
          : "Unavailable"}
      </span>
      {data?.message && <small>{data.message}</small>}
      {data?.configured && (
        <a className="button" href="/api/auth/kite/login">
          Log in to Kite
        </a>
      )}
      {kite.error && (
        <ErrorMessage error={kite.error} retry={() => void kite.refetch()} />
      )}
    </div>
  );
}
function Login({
  ready,
  reason,
  configured,
  checkSetup,
}: {
  ready: () => void;
  reason: string;
  configured: boolean;
  checkSetup: () => void;
}) {
  const [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  return (
    <main className="login">
      <div className="eyebrow">AUREVON / PAPER DESK</div>
      <Card title="Operator sign in">
        {!configured ? (
          <>
            <p role="alert">
              Dashboard password is not configured. Save your password locally,
              then restart the backend.
            </p>
            <p>Run this from the backend directory in PowerShell:</p>
            <pre className="setup-command">
              .\.venv\Scripts\python.exe -m app.tools.dashboard_password --save
            </pre>
            <button onClick={checkSetup}>Check setup again</button>
          </>
        ) : (
          <>
            <p>{reason || "Use your locally configured dashboard password."}</p>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (busy) return;
                setBusy(true);
                setError(undefined);
                try {
                  await api.login(password);
                  setPassword("");
                  ready();
                } catch (err) {
                  setError(err);
                  setPassword("");
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                Dashboard password
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              <button disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
              </button>
              {error !== undefined && <ErrorMessage error={error} />}
            </form>
          </>
        )}
      </Card>
    </main>
  );
}
function Foundation({ page }: { page: string }) {
  return (
    <Card title={`${page} workspace`}>
      <p>
        {page === "Live"
          ? "No chart or trading view has been accepted yet. Feed status and global paper controls are available above."
          : `${page} detail tools are scheduled in the next frontend milestones.`}
      </p>
      <p className="muted">
        Missing data and an unattached paper owner remain unavailable. This
        shell does not activate paper trading.
      </p>
    </Card>
  );
}
export function App() {
  const [signed, setSigned] = useState(false),
    [reason, setReason] = useState(""),
    [dialog, setDialog] = useState<"deposit" | "kill" | null>(null);
  const [compact, setCompact] = useState(() => {
    try {
      return localStorage.getItem("aurevon.compact") === "true";
    } catch {
      return false;
    }
  });
  const requireLogin = useRef(false);
  const expire = useCallback(() => {
    requireLogin.current = true;
    setSigned(false);
    setDialog(null);
    setReason("Your session expired. Sign in to continue.");
    void cache.cancelQueries();
    cache.clear();
  }, []);
  const session = useQuery({
    queryKey: ["session"],
    queryFn: () => api.session(),
    refetchInterval: 30000,
  });
  useEffect(() => {
    if (session.data?.authenticated && !requireLogin.current) setSigned(true);
    else if (session.data && signed) expire();
  }, [session.data, signed, expire]);
  useEffect(
    () =>
      cache.getQueryCache().subscribe((event) => {
        if (
          event.type === "updated" &&
          event.query.state.error instanceof ApiError &&
          event.query.state.error.status === 401
        )
          expire();
      }),
    [expire],
  );
  const connection = useLive(signed, expire);
  if (!signed) {
    if (session.isPending)
      return <main role="status">Checking dashboard session…</main>;
    if (session.error)
      return (
        <ErrorMessage
          error={session.error}
          retry={() => void session.refetch()}
        />
      );
    return (
      <Login
        reason={reason}
        configured={session.data?.configured ?? false}
        checkSetup={() => void session.refetch()}
        ready={() => {
          void session.refetch().then(({ data }) => {
            if (data?.authenticated) {
              requireLogin.current = false;
              setSigned(true);
              setReason("");
            }
          });
        }}
      />
    );
  }
  return (
    <div className={compact ? "app compact" : "app"}>
      <a className="skip" href="#workspace">
        Skip to workspace
      </a>
      <aside>
        <div className="brand">
          AUREVON<span>PAPER DESK / 01</span>
        </div>
        <nav aria-label="Main navigation">
          {["Live", "History", "Wallet", "Settings"].map((p) => (
            <NavLink
              key={p}
              to={p === "Live" ? "/" : `/${p.toLowerCase()}`}
              end
            >
              {p}
            </NavLink>
          ))}
        </nav>
        <div className="aside-foot">
          Local workspace
          <br />
          PAPER · UNARMED
        </div>
      </aside>
      <div className="content">
        <header>
          <div className="header-line">
            <span className="eyebrow">OPERATOR WORKSPACE</span>
            <button
              onClick={async () => {
                try {
                  await api.logout(crypto.randomUUID());
                  expire();
                  setReason("Signed out.");
                } catch {
                  setReason("Logout failed. Try again.");
                }
              }}
            >
              Sign out
            </button>
          </div>
          <TopStatus />
          <Kite />
        </header>
        <main id="workspace">
          <div className="toolbar">
            <span className="chip">PAPER · Unarmed</span>
            <span role="status">{connection}</span>
            <button className="danger" onClick={() => setDialog("kill")}>
              Kill paper execution
            </button>
          </div>
          {reason && <p role="alert">{reason}</p>}
          <WalletChip deposit={() => setDialog("deposit")} />
          <div className="notice">
            Paper trading remains gated. Check feed quality, risk settings and
            operational readiness before any paper action.
          </div>
          <Routes>
            <Route path="/" element={<LivePage connection={connection} />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/wallet" element={<Foundation page="Wallet" />} />
            <Route
              path="/settings"
              element={
                <>
                  <Foundation page="Settings" />
                  <Card title="Display preferences">
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={compact}
                        onChange={(e) => {
                          setCompact(e.target.checked);
                          try {
                            localStorage.setItem(
                              "aurevon.compact",
                              String(e.target.checked),
                            );
                          } catch {
                            /* preferences are optional */
                          }
                        }}
                      />
                      Compact spacing
                    </label>
                  </Card>
                </>
              }
            />
            <Route
              path="*"
              element={
                <Card title="Page not found">
                  <NavLink to="/">Return to Live</NavLink>
                </Card>
              }
            />
          </Routes>
          <footer>
            Server data is authoritative ·{" "}
            <button onClick={() => void cache.invalidateQueries()}>
              Refresh data
            </button>
          </footer>
        </main>
      </div>
      {dialog && (
        <FinancialDialog kind={dialog} close={() => setDialog(null)} />
      )}
    </div>
  );
}
