import { Fragment, useEffect, useRef, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api, cache } from "./state";
import { ApiError } from "./api/client";
import { Card, ErrorMessage } from "./ui";
import { decimal, type Schema } from "./live-data";
import { ist, money } from "./format";
import {
  historyFilters,
  pnlSeries,
  winRate,
  type TradeQuery,
} from "./history-data";
import { RenkoChart } from "./Chart";

function SummaryCards() {
  const periods = ["daily", "weekly", "monthly", "all"] as const;
  const queries = useQueries({
    queries: periods.map((period) => ({
      queryKey: ["pnl", "history", "summary", period],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        api.get("/api/pnl/summary", { period }, { signal }),
    })),
  });
  return (
    <section aria-label="Account summary cards">
      <p className="muted">
        Account-wide PAPER summaries. Trade filters below apply to the table and
        CSV; these fixed-period totals include all families.
      </p>
      <div className="summary-cards">
        {queries.map((q, i) => (
          <Card
            key={periods[i]}
            title={["Today", "This week", "This month", "All time"][i]}
          >
            {q.isPending ? (
              <p role="status">Loading summary…</p>
            ) : q.error ? (
              <ErrorMessage error={q.error} retry={() => void q.refetch()} />
            ) : (
              q.data && (
                <>
                  <p className="metric">{money(q.data.net)}</p>
                  <dl className="metric-grid">
                    <div>
                      <dt>Capital return</dt>
                      <dd>
                        {q.data.capital_return_pct == null
                          ? "Unavailable"
                          : `${q.data.capital_return_pct}%`}
                      </dd>
                    </div>
                    <div>
                      <dt>Trades</dt>
                      <dd>{q.data.trades}</dd>
                    </div>
                    <div>
                      <dt>Win rate</dt>
                      <dd>{winRate(q.data.wins, q.data.trades)}</dd>
                    </div>
                  </dl>
                  <small>
                    {q.data.start} → {q.data.end} IST
                  </small>
                  {q.data.trades === 0 && (
                    <p>No closed trades in this period.</p>
                  )}
                </>
              )
            )}
          </Card>
        ))}
      </div>
    </section>
  );
}
export function PnlChart({
  rows,
  title,
}: {
  rows: Schema["PnlSummary"][];
  title: string;
}) {
  const values = pnlSeries(rows);
  if (!values.length) return <p>No reporting buckets available.</p>;
  const points = values.map((row) => ({
    net: Number(row.net),
    cumulative: Number(row.cumulative),
  }));
  const min = Math.min(0, ...points.flatMap((p) => [p.net, p.cumulative])),
    max = Math.max(0, ...points.flatMap((p) => [p.net, p.cumulative])),
    range = Math.max(max - min, 1);
  const y = (v: number) => 210 - ((v - min) / range) * 185,
    x = (i: number) => 35 + ((i + 0.5) * 840) / values.length;
  return (
    <>
      <svg
        viewBox="0 0 940 260"
        role="img"
        aria-label={`${title}: net bars and cumulative net line`}
        className="pnl-chart"
      >
        <line x1="25" x2="890" y1={y(0)} y2={y(0)} stroke="#697b90" />
        {values.map((row, i) => (
          <rect
            key={row.day}
            data-pnl-day={row.day}
            x={x(i) - Math.min(18, 330 / values.length)}
            y={Math.min(y(0), y(points[i].net))}
            width={Math.min(36, 660 / values.length)}
            height={Math.max(1, Math.abs(y(points[i].net) - y(0)))}
            fill={points[i].net >= 0 ? "#7ce8c0" : "#ff9a9f"}
          >
            <title>
              {row.day} IST · Net {money(row.net)} · Cumulative{" "}
              {money(row.cumulative)}
            </title>
          </rect>
        ))}
        <polyline
          fill="none"
          stroke="#8ac5ff"
          strokeWidth="2"
          points={points.map((p, i) => `${x(i)},${y(p.cumulative)}`).join(" ")}
        />
        {[0, Math.floor((values.length - 1) / 2), values.length - 1]
          .filter((v, i, a) => a.indexOf(v) === i)
          .map((i) => (
            <text
              key={i}
              x={x(i)}
              y="245"
              textAnchor="middle"
              fill="#a4b4c5"
              fontSize="12"
            >
              {values[i].day}
            </text>
          ))}
      </svg>
      <p className="muted">
        Green/red: net P&L. Blue: cumulative net from the first displayed
        bucket, excluding deposits. Geometry uses approximate numbers; labels
        and totals retain exact paise.
      </p>
      <details>
        <summary>{title} exact values</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>IST bucket</th>
                <th>Net</th>
                <th>Cumulative net</th>
              </tr>
            </thead>
            <tbody>
              {values.map((row) => (
                <tr key={row.day}>
                  <td>{row.day}</td>
                  <td>{money(row.net)}</td>
                  <td>{money(row.cumulative)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
function Reporting({
  start,
  end,
  valid,
}: {
  start: string;
  end: string;
  valid: boolean;
}) {
  const withinLimit = Date.parse(end) - Date.parse(start) <= 366 * 86400000;
  const daily = useQuery({
    queryKey: ["pnl", "history", "daily", start, end],
    enabled: valid && withinLimit,
    queryFn: ({ signal }) =>
      api.get("/api/pnl/daily", { start, end }, { signal }),
  });
  const monthly = useQuery({
    queryKey: ["pnl", "history", "periods", "monthly"],
    queryFn: ({ signal }) =>
      api.get("/api/pnl/periods", { period: "monthly", count: 12 }, { signal }),
  });
  const weekly = useQuery({
    queryKey: ["pnl", "history", "periods", "weekly"],
    queryFn: ({ signal }) =>
      api.get("/api/pnl/periods", { period: "weekly", count: 8 }, { signal }),
  });
  return (
    <>
      <div className="history-chart-grid">
        <Card title="Daily net and cumulative P&L">
          <p>
            Account-wide PAPER totals for {start} → {end} IST;
            family/result/strength table filters do not alter these charts.
          </p>
          {!valid ? (
            <p>Choose valid dates first.</p>
          ) : !withinLimit ? (
            <p>
              Choose at most 367 calendar days for the daily chart. The trade
              table can use a longer range.
            </p>
          ) : daily.error ? (
            <ErrorMessage
              error={daily.error}
              retry={() => void daily.refetch()}
            />
          ) : daily.isPending ? (
            <p role="status">Loading daily series…</p>
          ) : (
            daily.data && <PnlChart rows={daily.data} title="Daily P&L" />
          )}
        </Card>
        <Card title="Monthly P&L">
          <p>Last 12 account-wide calendar months in IST.</p>
          {monthly.error ? (
            <ErrorMessage
              error={monthly.error}
              retry={() => void monthly.refetch()}
            />
          ) : monthly.isPending ? (
            <p role="status">Loading monthly series…</p>
          ) : (
            monthly.data && <PnlChart rows={monthly.data} title="Monthly P&L" />
          )}
        </Card>
      </div>
      <PeriodTable title="Weekly summaries" query={weekly} />
      <PeriodTable title="Monthly summaries" query={monthly} />
    </>
  );
}
function PeriodTable({
  title,
  query: q,
}: {
  title: string;
  query: ReturnType<typeof useQuery<Schema["PnlSummary"][]>>;
}) {
  return (
    <Card title={title}>
      {q.isPending ? (
        <p role="status">Loading periods…</p>
      ) : q.error ? (
        <ErrorMessage error={q.error} retry={() => void q.refetch()} />
      ) : (
        <div className="table-scroll">
          <table>
            <caption>
              Account-wide PAPER totals; returns use actual period-start
              capital, excluding external flows from profit.
            </caption>
            <thead>
              <tr>
                <th>IST period</th>
                <th>Trades / wins</th>
                <th>Gross</th>
                <th>Costs</th>
                <th>Net</th>
                <th>Capital return</th>
                <th>Best trade (net)</th>
                <th>Worst trade (net)</th>
              </tr>
            </thead>
            <tbody>
              {q.data?.map((row) => (
                <tr key={row.start}>
                  <td>
                    {row.start} → {row.end}
                  </td>
                  <td>
                    {row.trades} / {row.wins}
                  </td>
                  <td>{money(row.gross)}</td>
                  <td>{money(row.costs)}</td>
                  <td>{money(row.net)}</td>
                  <td>
                    {row.capital_return_pct == null
                      ? "Unavailable"
                      : `${row.capital_return_pct}%`}
                  </td>
                  <td>
                    {row.best_trade_id ?? "Unavailable"} ·{" "}
                    {money(row.best_trade_net)}
                  </td>
                  <td>
                    {row.worst_trade_id ?? "Unavailable"} ·{" "}
                    {money(row.worst_trade_net)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
function TradeChart({ trade }: { trade: Schema["PositionView"] }) {
  const linked = trade.signal_stream != null && trade.signal_index != null;
  const q = useQuery({
    queryKey: [
      "history",
      "trade-chart",
      trade.trade_id,
      trade.signal_stream,
      trade.signal_index,
    ],
    enabled: linked,
    queryFn: ({ signal }) =>
      api.get(
        "/api/bricks",
        {
          stream: trade.signal_stream!,
          after: Math.max(-1, trade.signal_index! - 31),
          limit: 100,
        },
        { signal },
      ),
  });
  return (
    <section>
      <h4>Underlying Renko around the signal</h4>
      <p>
        Indicator replay around {trade.indicator_trade_id ?? "unavailable"}.
        This is not an option fill-price chart. Publication identity below may
        be newer than the trade; it is not proof of the original reference
        settings.
      </p>
      {!linked ? (
        <p>Trade chart source unavailable for this record.</p>
      ) : q.error ? (
        <ErrorMessage error={q.error} retry={() => void q.refetch()} />
      ) : q.isPending ? (
        <p role="status">Loading trade chart…</p>
      ) : (
        q.data && (
          <>
            <p className="source-identity">
              Stream {q.data.stream} · revision {q.data.revision} · config{" "}
              {q.data.configuration_id} · indicator source{" "}
              {q.data.indicator_source?.source_id ?? "unavailable"} · reference
              unverified
            </p>
            <RenkoChart
              history={q.data}
              layers={{ trend: true, bias: true, events: true, levels: false }}
              windowSize={100}
              endIndex={null}
            />
          </>
        )
      )}
    </section>
  );
}
function TradeDetails({ id }: { id: string }) {
  const q = useQuery({
    queryKey: ["trades", id],
    queryFn: ({ signal }) =>
      api.get("/api/trades/{identity}", undefined, {
        params: { identity: id },
        signal,
      }),
  });
  const p = q.data;
  return q.isPending ? (
    <p role="status">Loading trade details…</p>
  ) : q.error ? (
    <ErrorMessage error={q.error} retry={() => void q.refetch()} />
  ) : p ? (
    <div className="trade-details">
      <h4>
        {p.trade_id} · {p.state}
      </h4>
      <p>
        Signal explanation:{" "}
        {p.signal_explanation ?? "Unavailable for this trade."}
      </p>
      <p>
        Exit reason: {p.exit_reason ?? "Unavailable"} · realised gross{" "}
        {money(p.gross)} · estimated costs {money(p.costs)} · net {money(p.net)}
      </p>
      <div className="table-scroll">
        <table>
          <caption>Persisted legs and fills</caption>
          <thead>
            <tr>
              <th>Leg</th>
              <th>Symbol</th>
              <th>Quantity</th>
              <th>Entry price</th>
              <th>Last mark</th>
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
      <h4>Order timeline</h4>
      <ol className="order-timeline">
        {[...p.orders]
          .sort(
            (a, b) =>
              (a.created_at ?? a.filled_at ?? "").localeCompare(
                b.created_at ?? b.filled_at ?? "",
              ) || a.id.localeCompare(b.id),
          )
          .map((o) => (
            <li key={o.id}>
              <strong>
                {o.id} · {o.side} · {o.status}
              </strong>
              <p>
                Created {o.created_at ? ist(o.created_at) : "Unavailable"} ·
                eligible {o.eligible_at ? ist(o.eligible_at) : "Unavailable"} ·
                filled {o.filled_at ? ist(o.filled_at) : "Unavailable"}
              </p>
              <p>
                Token {o.token} · quantity {o.quantity} · fill{" "}
                {decimal(o.fill_price)} · costs {money(o.costs)} · reason{" "}
                {o.reason ?? "Unavailable"}
              </p>
            </li>
          ))}
      </ol>
      <TradeChart trade={p} />
    </div>
  ) : null;
}
function ExpandedTrade({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  return (
    <details onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>Details {id}</summary>
      {open && <TradeDetails id={id} />}
    </details>
  );
}
function TradeTable({
  filters,
  onSort,
}: {
  filters: TradeQuery;
  onSort: (sort: "net" | "closed_at") => void;
}) {
  const [cursors, setCursors] = useState<(string | undefined)[]>([undefined]),
    [page, setPage] = useState(0),
    [exporting, setExporting] = useState(false),
    [exportError, setExportError] = useState<unknown>();
  const exporter = useRef<AbortController | null>(null),
    exportLock = useRef(false);
  useEffect(() => () => exporter.current?.abort(), []);
  const q = useQuery({
    queryKey: ["history", "table", filters, cursors[page]],
    queryFn: ({ signal }) =>
      api.get(
        "/api/trades",
        { ...filters, limit: 25, cursor: cursors[page] },
        { signal },
      ),
  });
  async function download() {
    if (exportLock.current) return;
    exportLock.current = true;
    setExporting(true);
    setExportError(undefined);
    exporter.current = new AbortController();
    try {
      const csv = await api.exportTrades(
        { ...filters, limit: 50 },
        exporter.current.signal,
      );
      if (exporter.current.signal.aborted) return;
      const url = URL.createObjectURL(
        new Blob([csv], { type: "text/csv;charset=utf-8" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = `aurevon-paper-trades-${filters.start}-${filters.end}.csv`;
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      if (exporter.current?.signal.aborted) return;
      setExportError(error);
      if (error instanceof ApiError && error.status === 401)
        void cache.invalidateQueries({ queryKey: ["session"] });
    } finally {
      exportLock.current = false;
      if (!exporter.current?.signal.aborted) setExporting(false);
    }
  }
  function reload() {
    setCursors([undefined]);
    setPage(0);
    void cache.invalidateQueries({ queryKey: ["history", "table", filters] });
  }
  const rows = q.error ? [] : (q.data?.items ?? []);
  return (
    <Card title="Closed paper trades">
      <div className="history-actions">
        <button onClick={() => void download()} disabled={exporting}>
          {exporting ? "Preparing CSV…" : "Export matching CSV"}
        </button>
        <button onClick={reload}>Reload first page</button>
        <span>
          Page {page + 1} · {rows.length} rows · revision{" "}
          {q.data?.revision ?? "Unavailable"}
        </span>
      </div>
      <p className="muted">
        Table and CSV share the active filters and sort. CSV exports all
        matching trades, up to 10,000, using stable server field names. Net
        sorting also requires at most 10,000 matches; narrow dates for larger
        histories.
      </p>
      {exportError != null && (
        <ErrorMessage error={exportError} retry={() => void download()} />
      )}{" "}
      {q.error && (
        <>
          <ErrorMessage error={q.error} retry={() => void q.refetch()} />
          {q.error instanceof ApiError && q.error.status === 409 && (
            <p>
              History changed or its cursor is stale. Reload the first page; no
              pages from different revisions are combined.
            </p>
          )}
        </>
      )}
      {q.isPending && <p role="status">Loading trades…</p>}
      {!q.isPending && !q.error && !rows.length && (
        <p>No closed trades match these filters.</p>
      )}
      {!!rows.length && (
        <div className="table-scroll">
          <table className="history-trades">
            <caption>
              Exact server amounts. Times are IST; missing legacy fields stay
              unavailable.
            </caption>
            <thead>
              <tr>
                <th
                  aria-sort={
                    filters.sort === "closed_at"
                      ? filters.order === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  <button onClick={() => onSort("closed_at")}>
                    Closed time
                  </button>
                </th>
                <th>Signal / strength</th>
                <th>Spread / quantity</th>
                <th>Entry → Exit prices (short / hedge)</th>
                <th>Gross</th>
                <th>Costs</th>
                <th
                  aria-sort={
                    filters.sort === "net"
                      ? filters.order === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  <button onClick={() => onSort("net")}>Net P&L</button>
                </th>
                <th>Margin / capital return</th>
                <th>Duration</th>
                <th>Result / reason</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <Fragment key={t.trade_id}>
                  <tr>
                    <td>
                      {ist(t.closed_at)}
                      <br />
                      {t.trade_id}
                    </td>
                    <td>
                      {t.family} · {t.direction === 1 ? "Long" : "Short"} ·
                      Grade {t.grade}
                      <br />
                      {t.signal_id ?? "Source unavailable"}
                    </td>
                    <td>
                      {t.short_symbol} / {t.hedge_symbol}
                      <br />
                      Quantity {t.quantity ?? "Unavailable"}
                    </td>
                    <td>
                      {decimal(t.short_entry)} / {decimal(t.hedge_entry)} →{" "}
                      {decimal(t.short_exit)} / {decimal(t.hedge_exit)}
                    </td>
                    <td>{money(t.gross)}</td>
                    <td>{money(t.costs)}</td>
                    <td>{money(t.net)}</td>
                    <td>
                      {t.margin_return_pct == null
                        ? "Unavailable"
                        : `${t.margin_return_pct}%`}{" "}
                      /{" "}
                      {t.capital_return_pct == null
                        ? "Unavailable"
                        : `${t.capital_return_pct}%`}
                    </td>
                    <td>
                      {t.duration_seconds == null
                        ? "Unavailable"
                        : `${Math.floor(t.duration_seconds / 60)}m ${t.duration_seconds % 60}s`}
                    </td>
                    <td>
                      {t.result} · {t.reason ?? "Unavailable"}
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={10}>
                      <ExpandedTrade id={t.trade_id} />
                    </td>
                  </tr>
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="history-actions">
        <button
          disabled={page === 0 || q.isFetching}
          onClick={() => setPage(page - 1)}
        >
          Previous trades
        </button>
        <button
          disabled={!q.data?.next_cursor || q.isFetching || !!q.error}
          onClick={() => {
            setCursors([...cursors.slice(0, page + 1), q.data!.next_cursor!]);
            setPage(page + 1);
          }}
        >
          Next trades
        </button>
      </div>
    </Card>
  );
}
export function HistoryPage() {
  const [params, setParams] = useSearchParams();
  const { query, error, start, end } = historyFilters(params);
  function change(name: string, value: string) {
    const next = new URLSearchParams(params);
    if (value || name === "start" || name === "end") next.set(name, value);
    else next.delete(name);
    setParams(next);
  }
  function sort(name: "closed_at" | "net") {
    const next = new URLSearchParams(params);
    next.set("sort", name);
    next.set(
      "order",
      query.sort === name && query.order === "desc" ? "asc" : "desc",
    );
    setParams(next);
  }
  return (
    <>
      <h1>History and P&L</h1>
      <SummaryCards />
      <Card title="Trade filters">
        <form className="history-filters" onSubmit={(e) => e.preventDefault()}>
          <label>
            From (IST)
            <input
              type="date"
              value={start}
              onChange={(e) => change("start", e.target.value)}
            />
          </label>
          <label>
            Through (IST)
            <input
              type="date"
              value={end}
              onChange={(e) => change("end", e.target.value)}
            />
          </label>
          {[
            { name: "mode", label: "Mode", options: [["PAPER", "PAPER"]] },
            {
              name: "family",
              label: "Signal family",
              options: [
                ["", "All families"],
                ["CO", "CO"],
                ["DIV", "DIV"],
                ["OT", "OT"],
              ],
            },
            {
              name: "direction",
              label: "Direction",
              options: [
                ["", "All directions"],
                ["1", "Long"],
                ["-1", "Short"],
              ],
            },
            {
              name: "result",
              label: "Result",
              options: [
                ["", "All results"],
                ["WIN", "Win"],
                ["LOSS", "Loss"],
                ["FLAT", "Flat"],
              ],
            },
            {
              name: "grade",
              label: "Strength",
              options: [
                ["", "All strengths"],
                ["1", "Weak (1)"],
                ["2", "Medium (2)"],
                ["3", "Strong (3)"],
              ],
            },
          ].map((field) => (
            <label key={field.name}>
              {field.label}
              <select
                aria-label={field.label}
                value={
                  params.get(field.name) ??
                  (field.name === "mode" ? "PAPER" : "")
                }
                onChange={(e) => change(field.name, e.target.value)}
              >
                {field.options.map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <button type="button" onClick={() => setParams({})}>
            Reset filters
          </button>
        </form>
        <p className="muted">
          Filters and sorting persist in this page's URL. Live-money history is
          unavailable.
        </p>
        {error && (
          <p role="alert" className="notice error">
            {error}
          </p>
        )}
      </Card>
      <Reporting start={start} end={end} valid={!error} />
      {!error && (
        <TradeTable key={JSON.stringify(query)} filters={query} onSort={sort} />
      )}
    </>
  );
}
