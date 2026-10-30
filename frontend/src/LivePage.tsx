import { memo, useEffect, useRef, useState, type ReactNode } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api, cache } from "./state";
import { ApiError } from "./api/client";
import { ChartPane } from "./Chart";
import {
  decimal,
  duration,
  todayIST,
  useSnapshot,
  type Schema,
} from "./live-data";
import { ist, money } from "./format";
import { Card, Dialog, ErrorMessage } from "./ui";
import { readIntent, saveIntent, type Intent } from "./intents";
import { ShadowPanel } from "./ShadowPanel";
import { FeedControls } from "./FeedControls";

function Datum({ name, children }: { name: string; children: ReactNode }) {
  return (
    <div>
      <dt>{name}</dt>
      <dd>{children}</dd>
    </div>
  );
}
function ResultState({
  pending,
  error,
  empty,
  retry,
}: {
  pending: boolean;
  error: unknown;
  empty?: string;
  retry: () => void;
}) {
  return (
    <>
      {pending && <p role="status">Loading server data…</p>}
      {error != null && <ErrorMessage error={error} retry={retry} />}{" "}
      {!pending && !error && empty && <p>{empty}</p>}
    </>
  );
}
function Freshness({ at }: { at: string | null | undefined }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(timer);
  }, []);
  const stale =
    !at || !Number.isFinite(Date.parse(at)) || now - Date.parse(at) > 15000;
  return (
    <p className={stale ? "warning" : "muted"}>
      {stale ? "Stale or unavailable mark" : "Mark received"} ·{" "}
      {at ? ist(at) : "Unavailable"}
    </p>
  );
}
function Readiness({ connection }: { connection: string }) {
  const q = useSnapshot((s) => ({
    quality: s.quality,
    unavailable: s.unavailable,
    entries: s.entries_enabled,
    state: s.state,
    recovery: s.recovery,
  }));
  const d = q.data;
  return (
    <section aria-label="Live readiness" className="readiness">
      <h1>Live paper desk</h1>
      <AlertStrip />
      <FeedControls />
      <ShadowPanel />
      <p>
        Server state: {d?.state ?? "Unavailable"} · Entries{" "}
        {d?.entries ? "enabled by owner" : "blocked"}
      </p>
      {connection !== "Connected" && (
        <p role="status" className="notice">
          {connection}. Displayed data may be old; reconnect reloads server
          evidence.
        </p>
      )}
      {d && (
        <>
          {(d.quality.stale ||
            !d.quality.connected ||
            d.quality.gap_requires_replay ||
            d.quality.history_pending ||
            d.quality.clock_or_feed_delay ||
            d.quality.reconnect_exhausted) && (
            <p className="notice">
              Feed readiness blocked:{" "}
              {Object.entries(d.quality)
                .filter(([k, v]) =>
                  k === "connected" ? !v : typeof v === "boolean" && v,
                )
                .map(([k]) => k.replaceAll("_", " "))
                .join(" · ")}
            </p>
          )}
          <details>
            <summary>Readiness and recovery details</summary>
            <dl>
              {Object.entries(d.quality.readiness ?? {}).map(([k, v]) => (
                <Datum key={k} name={k.replaceAll("_", " ")}>
                  {typeof v === "boolean"
                    ? v
                      ? "Ready"
                      : "Blocked"
                    : JSON.stringify(v)}
                </Datum>
              ))}
            </dl>
            <p>Recovery: {JSON.stringify(d.recovery)}</p>
          </details>
          {!!d.unavailable?.length && (
            <p className="muted">
              Unavailable domains: {d.unavailable.join(", ")}
            </p>
          )}
        </>
      )}
      {q.error && (
        <ErrorMessage error={q.error} retry={() => void q.refetch()} />
      )}
    </section>
  );
}
const DirectionCard = memo(function DirectionCard() {
  const { data: source } = useSnapshot((s) => ({
    stream: s.stream,
    config: s.configuration_id,
    available: s.state !== "running_quotes_only_anchor_required",
  }));
  const q = useQuery<
    Schema["BrickHistory"],
    Error,
    Schema["IndicatorOverlay"] | undefined
  >({
    queryKey: ["chart", source?.stream, source?.config],
    enabled: false,
    select: (h) =>
      source?.available && h.configuration_id === source.config
        ? h.overlays?.at(-1)
        : undefined,
  });
  const o =
    q.error instanceof ApiError && q.error.status === 404 ? undefined : q.data;
  return (
    <Card title="Direction and strength">
      {o ? (
        <>
          <p className="metric">
            {o.bias_direction === 1
              ? "Bullish"
              : o.bias_direction === -1
                ? "Bearish"
                : "Neutral"}
          </p>
          <p>
            {o.bias_strong ? "Strong bias" : "Normal bias"} · score{" "}
            {o.bias_score} · up probability{" "}
            {o.up_probability == null ? "Unavailable" : `${o.up_probability}%`}
          </p>
          <p className="muted">
            Indicator replay · brick {o.index} · {ist(o.at)}
          </p>
          <details>
            <summary>Ten-factor explanation</summary>
            <dl>
              {Object.entries(o.factors).map(([factor, value]) => (
                <Datum key={factor} name={factor}>
                  {value > 0 ? "Bullish" : value < 0 ? "Bearish" : "Neutral"} (
                  {value})
                </Datum>
              ))}
            </dl>
            {Object.keys(o.factors).length !== 10 && (
              <p>
                Available factors: {Object.keys(o.factors).length}/10. Missing
                factors are unavailable.
              </p>
            )}
          </details>
        </>
      ) : (
        <p>Indicator bias unavailable until matching overlays are published.</p>
      )}
    </Card>
  );
});
export function CloseDialog({
  tradeId,
  close,
}: {
  tradeId: string;
  close: () => void;
}) {
  const kind = `close:${tradeId}`,
    intent = useRef<Intent | null>(readIntent(kind)),
    inFlight = useRef(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [requested, setRequested] = useState(false),
    [response, setResponse] = useState("");
  const detail = useQuery({
    queryKey: ["trades", tradeId],
    queryFn: ({ signal }) =>
      api.get("/api/trades/{identity}", undefined, {
        params: { identity: tradeId },
        signal,
      }),
    refetchInterval: (query) =>
      requested && query.state.data?.state !== "CLOSED" ? 2000 : false,
  });
  const closed = detail.data?.state === "CLOSED";
  useEffect(() => {
    if (closed) {
      saveIntent(`close:${tradeId}`, null);
      void cache.invalidateQueries({
        predicate: (q) =>
          ["positions", "history", "wallet", "pnl"].includes(
            String(q.queryKey[0]),
          ),
      });
    }
  }, [closed, tradeId]);
  async function confirm() {
    if (inFlight.current || requested || closed) return;
    if (!intent.current) {
      intent.current = { key: crypto.randomUUID(), amount: tradeId };
      saveIntent(kind, intent.current);
    }
    inFlight.current = true;
    setBusy(true);
    setError(undefined);
    try {
      const result = await api.post(
        "/api/trades/{trade_id}/close",
        {},
        { key: intent.current.key, params: { trade_id: tradeId } },
      );
      setRequested(true);
      saveIntent(kind, null);
      setResponse(
        `${result.pending_closures} pending closures. Waiting for final trade state and settlement.`,
      );
      void cache.invalidateQueries({
        predicate: (q) =>
          [
            "positions",
            "trades",
            "snapshot",
            "wallet",
            "pnl",
            "history",
          ].includes(String(q.queryKey[0])),
      });
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
    <Dialog title="Close paper spread" close={close} busy={busy}>
      <p>
        Trade {tradeId}. Request closure of both legs. Stale quotes may leave
        the spread pending; a response does not prove fills or settlement.
      </p>
      <ResultState
        pending={detail.isPending}
        error={detail.error}
        retry={() => void detail.refetch()}
      />
      {detail.data && (
        <p>
          Server state: <strong>{detail.data.state}</strong>
        </p>
      )}
      {closed ? (
        <p role="status">
          Closed · exit reason {detail.data?.exit_reason ?? "Unavailable"} · net{" "}
          {money(detail.data?.net)}. Verify fills and the ledger.
        </p>
      ) : (
        <>
          {response && <p role="status">{response}</p>}
          {error != null && (
            <>
              <ErrorMessage error={error} />
              <p>Outcome uncertain. Retry reuses the original close request.</p>
            </>
          )}
          {!requested && (
            <button
              className="danger"
              onClick={() => void confirm()}
              disabled={busy || !detail.data}
            >
              {busy
                ? "Requesting close…"
                : intent.current
                  ? "Retry same close"
                  : "Confirm close"}
            </button>
          )}
        </>
      )}
    </Dialog>
  );
}
function ActiveSpreads() {
  const [closing, setClosing] = useState<string | null>(null),
    [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const q = useQuery({
    queryKey: ["positions"],
    queryFn: ({ signal }) =>
      api.get("/api/positions/open", undefined, { signal }),
    refetchInterval: 10000,
  });
  return (
    <Card title="Active paper spreads">
      <ResultState
        pending={q.isPending}
        error={q.error}
        empty={!q.data?.length ? "No active paper spread." : undefined}
        retry={() => void q.refetch()}
      />
      {q.data?.map((p) => (
        <article
          key={p.trade_id}
          className="spread"
          aria-label={`Spread ${p.trade_id}`}
        >
          <h3>
            {p.trade_id} · {p.state}
          </h3>
          <Freshness at={p.mark_at} />
          <div className="table-scroll">
            <table>
              <caption>Both spread legs; marks are server observations</caption>
              <thead>
                <tr>
                  <th>Leg</th>
                  <th>Symbol</th>
                  <th>Quantity</th>
                  <th>Entry</th>
                  <th>Mark</th>
                </tr>
              </thead>
              <tbody>
                {p.legs.map((leg) => (
                  <tr key={leg.role}>
                    <td>{leg.role}</td>
                    <td>{leg.symbol}</td>
                    <td>{leg.quantity}</td>
                    <td>{decimal(leg.entry)}</td>
                    <td>{decimal(leg.mark)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <dl className="metric-grid">
            <Datum name="MTM">{money(p.unrealised)}</Datum>
            <Datum name="Reserved margin">{money(p.margin)}</Datum>
            <Datum name="Margin return">
              {p.margin_return_pct == null
                ? "Unavailable"
                : `${p.margin_return_pct}%`}
            </Datum>
            <Datum name="Spread debit / unit">{decimal(p.spread_debit)}</Datum>
            <Datum name="Premium stop debit / unit">
              {decimal(p.stop_debit_per_unit)}
            </Datum>
            <Datum name="Target debit / unit">
              {p.profit_capture_enabled === false
                ? "Disabled"
                : decimal(p.profit_capture_debit_per_unit)}
            </Datum>
            <Datum name="Duration">
              {duration(p.created_at, p.closed_at, now)}
            </Datum>
            <Datum name="Exit reason / transition">
              {p.exit_reason ?? "None recorded"}
            </Datum>
          </dl>
          <button onClick={() => setClosing(p.trade_id)}>
            {p.state === "CLOSING" || p.state === "UNWINDING"
              ? "Review pending close"
              : "Close paper spread"}
          </button>
        </article>
      ))}
      {closing && (
        <CloseDialog tradeId={closing} close={() => setClosing(null)} />
      )}
    </Card>
  );
}
function LastClosed() {
  const q = useQuery({
    queryKey: ["history", "last-closed"],
    queryFn: ({ signal }) => api.get("/api/trades", { limit: 1 }, { signal }),
    refetchInterval: 15000,
  });
  const trade = q.data?.items[0];
  return (
    <Card title="Last closed trade">
      <ResultState
        pending={q.isPending}
        error={q.error}
        empty={!trade ? "No closed paper trade." : undefined}
        retry={() => void q.refetch()}
      />
      {trade && (
        <>
          <h3>{trade.trade_id}</h3>
          <p>
            {trade.family} · {trade.direction === 1 ? "Long" : "Short"} ·{" "}
            {ist(trade.closed_at)}
          </p>
          <dl className="metric-grid">
            <Datum name="Exit reason">{trade.reason ?? "Unavailable"}</Datum>
            <Datum name="Gross">{money(trade.gross)}</Datum>
            <Datum name="Estimated costs">{money(trade.costs)}</Datum>
            <Datum name="Realised net">{money(trade.net)}</Datum>
            <Datum name="Margin return">
              {trade.margin_return_pct == null
                ? "Unavailable"
                : `${trade.margin_return_pct}%`}
            </Datum>
            <Datum name="Capital return">
              {trade.capital_return_pct == null
                ? "Unavailable"
                : `${trade.capital_return_pct}%`}
            </Datum>
          </dl>
        </>
      )}
    </Card>
  );
}
function Today() {
  const [day, setDay] = useState(todayIST);
  useEffect(() => {
    const t = setInterval(() => setDay(todayIST()), 30000);
    return () => clearInterval(t);
  }, []);
  const q = useQuery({
    queryKey: ["pnl", "today", day],
    queryFn: ({ signal }) =>
      api.get("/api/pnl/summary", { period: "daily" }, { signal }),
    refetchInterval: 15000,
  });
  const wallet = useQuery({
    queryKey: ["wallet"],
    queryFn: ({ signal }) => api.get("/api/wallet", undefined, { signal }),
  });
  const risk = wallet.data?.risk_day === day ? wallet.data : undefined;
  return (
    <Card title="Today">
      <ResultState
        pending={q.isPending}
        error={q.error}
        retry={() => void q.refetch()}
      />
      {q.data && (
        <>
          <p className="muted">
            {q.data.start} · closed trades, net of estimated costs
          </p>
          <dl className="metric-grid">
            <Datum name="Trades / wins">
              {q.data.trades} / {q.data.wins}
            </Datum>
            <Datum name="Net P&L">{money(q.data.net)}</Datum>
            <Datum name="Capital return">
              {q.data.capital_return_pct == null
                ? "Unavailable"
                : `${q.data.capital_return_pct}%`}
            </Datum>
            <Datum name="Daily loss used / limit">
              {decimal(risk?.daily_loss_used)} /{" "}
              {decimal(risk?.daily_loss_limit)} INR
            </Datum>
            <Datum name="Daily loss utilisation">
              {risk?.daily_loss_utilisation_pct == null
                ? "Unavailable"
                : `${risk.daily_loss_utilisation_pct}%`}
            </Datum>
            <Datum name="Risk lock">
              {wallet.data
                ? wallet.data.loss_locked
                  ? "Loss locked"
                  : wallet.data.killed
                    ? "Kill locked"
                    : "Not locked"
                : "Unavailable"}
            </Datum>
          </dl>
          <p className="muted">
            Daily loss includes valid open MTM and costs. Missing marks or an
            unavailable/current-session risk basis stay unavailable. Deposits
            are not profit.
          </p>
        </>
      )}
    </Card>
  );
}
function SignalFeed() {
  const { data: source } = useSnapshot((s) => ({
    stream: s.stream,
    available: !(s.unavailable ?? []).includes("signals"),
  }));
  const stream = source?.stream;
  const q = useInfiniteQuery({
    queryKey: ["signals", stream],
    enabled: !!stream && source?.available === true,
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) =>
      api.get(
        "/api/signals",
        { stream: stream!, limit: 50, offset: pageParam },
        { signal },
      ),
    getNextPageParam: (last) => last.pagination.next_offset ?? undefined,
  });
  const items = [
    ...new Map(
      q.data?.pages.flatMap((p) => p.items).map((s) => [s.id, s]),
    ).values(),
  ].sort(
    (a, b) =>
      b.index - a.index || b.ordinal - a.ordinal || a.id.localeCompare(b.id),
  );
  if (source && !source.available) {
    return (
      <Card title="Signal feed">
        <p role="status">
          Signals are unavailable until Renko history and matching indicator
          data are ready.
        </p>
        <p>Quotes can continue. Trading entries remain blocked.</p>
      </Card>
    );
  }
  return (
    <Card title="Signal feed">
      <p className="muted">
        Indicator replay signals; indicator acceptance does not imply paper
        admission or a fill.
      </p>
      <ResultState
        pending={q.isPending}
        error={q.error}
        empty={!items.length ? "No signals for this source." : undefined}
        retry={() => void q.refetch()}
      />
      <ol className="feed">
        {items.map((s) => (
          <li key={s.id}>
            <strong>
              {s.code} · {s.direction === 1 ? "Long" : "Short"} · Grade{" "}
              {s.grade}
            </strong>
            <span className="chip">
              {s.accepted ? "Indicator accepted" : "Indicator rejected"}
            </span>
            <p>{s.explanation}</p>
            <small>
              {ist(s.at)} · brick {s.index} · risk {s.risk} · {s.reason}
            </small>
          </li>
        ))}
      </ol>
      {q.hasNextPage && (
        <button
          disabled={q.isFetchingNextPage}
          onClick={() => void q.fetchNextPage()}
        >
          Load older signals
        </button>
      )}
    </Card>
  );
}
function useAlerts() {
  return useInfiniteQuery({
    queryKey: ["alerts"],
    initialPageParam: 0,
    queryFn: ({ pageParam, signal }) =>
      api.get("/api/alerts", { limit: 50, offset: pageParam }, { signal }),
    getNextPageParam: (last) => last.pagination.next_offset ?? undefined,
    refetchInterval: 15000,
  });
}
function AlertStrip() {
  const q = useAlerts();
  const count = q.data
    ? [
        ...new Map(
          q.data.pages.flatMap((p) => p.items).map((a) => [a.id, a]),
        ).values(),
      ].filter((a) => !a.acknowledged_at).length
    : undefined;
  return (
    <div className="alert-strip" role="status">
      {q.error ? (
        "Alert status unavailable; check the alerts feed."
      ) : count ? (
        <a href="#live-alerts">
          {count} alerts need attention in loaded history
        </a>
      ) : q.isPending ? (
        "Loading alert status…"
      ) : (
        "No unacknowledged alerts in loaded history"
      )}
    </div>
  );
}
function Alerts() {
  const q = useAlerts();
  const [pending, setPending] = useState<string | null>(null),
    [error, setError] = useState<unknown>();
  const inFlight = useRef(false);
  const items = [
    ...new Map(
      q.data?.pages.flatMap((p) => p.items).map((a) => [a.id, a]),
    ).values(),
  ];
  async function acknowledge(id: string) {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(id);
    setError(undefined);
    try {
      await api.post(
        "/api/alerts/{identity}/ack",
        {},
        { params: { identity: id }, key: `ack:${id}` },
      );
      await cache.invalidateQueries({ queryKey: ["alerts"] });
    } catch (err) {
      setError(err);
      if (err instanceof ApiError && err.status === 401)
        void cache.invalidateQueries({ queryKey: ["session"] });
    } finally {
      inFlight.current = false;
      setPending(null);
    }
  }
  const unack = items.filter((a) => !a.acknowledged_at);
  return (
    <div id="live-alerts">
      <Card title="Alerts">
        <div role="status" className={unack.length ? "notice" : "muted"}>
          {unack.length
            ? `${unack.length} unacknowledged alerts in loaded history`
            : "No unacknowledged alerts in loaded history"}
        </div>
        <ResultState
          pending={q.isPending}
          error={q.error}
          empty={!items.length ? "No recorded alerts." : undefined}
          retry={() => void q.refetch()}
        />
        {error != null && <ErrorMessage error={error} />}
        <ul className="feed">
          {items.map((a) => (
            <li key={a.id}>
              <strong className={a.level === "critical" ? "warning" : ""}>
                {a.level.toUpperCase()} · {a.code}
              </strong>
              <p>{ist(a.at)}</p>
              {a.acknowledged_at ? (
                <small>Acknowledged {ist(a.acknowledged_at)}</small>
              ) : (
                <button
                  disabled={pending !== null}
                  onClick={() => void acknowledge(a.id)}
                >
                  {pending === a.id
                    ? "Acknowledging…"
                    : `Acknowledge ${a.code}`}
                </button>
              )}
            </li>
          ))}
        </ul>
        {q.hasNextPage && (
          <button
            disabled={q.isFetchingNextPage}
            onClick={() => void q.fetchNextPage()}
          >
            Load older alerts
          </button>
        )}
      </Card>
    </div>
  );
}
export function LivePage({ connection }: { connection: string }) {
  return (
    <>
      <Readiness connection={connection} />
      <div className="live-grid">
        <div className="live-main">
          <ChartPane />
          <SignalFeed />
          <Alerts />
        </div>
        <div className="live-cards">
          <DirectionCard />
          <ActiveSpreads />
          <LastClosed />
          <Today />
        </div>
      </div>
    </>
  );
}
