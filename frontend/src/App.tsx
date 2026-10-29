import { useCallback, useEffect, useRef, useState, memo } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, Route, Routes } from "react-router-dom";
import { api, cache } from "./state";
import { ApiError } from "./api/client";
import { useLive } from "./live";
import { ist, money } from "./format";
import { Card, ErrorMessage } from "./ui";
import { FinancialDialog, type WalletAction } from "./FinancialDialog";
export { FinancialDialog } from "./FinancialDialog";
import { WalletPage } from "./WalletPage";
import { LivePage } from "./LivePage";
import { HistoryPage } from "./HistoryPage";
import { SettingsPage } from "./SettingsPage";
import { PreferencesRuntime } from "./preferences";

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
        <strong>
          {wallet.data?.mode === "PAPER"
            ? money(wallet.data.free)
            : "Unavailable"}
        </strong>
      </span>
      <button
        onClick={deposit}
        disabled={
          !wallet.data?.initialized ||
          wallet.data.mode !== "PAPER" ||
          wallet.isError
        }
      >
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
export function App() {
  const [signed, setSigned] = useState(false),
    [reason, setReason] = useState(""),
    [dialog, setDialog] = useState<WalletAction | "kill" | null>(null);
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
      <PreferencesRuntime />
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
            <Route path="/wallet" element={<WalletPage action={setDialog} />} />
            <Route
              path="/settings"
              element={
                <>
                  <SettingsPage />
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
        <FinancialDialog
          kind={dialog}
          free={cache.getQueryData<{ free: string }>(["wallet"])?.free}
          close={() => setDialog(null)}
        />
      )}
    </div>
  );
}
