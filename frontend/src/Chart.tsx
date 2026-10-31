import { memo, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, cache } from "./state";
import { ApiError } from "./api/client";
import { mergeHistory, useSnapshot, type Schema } from "./live-data";
import { Card, ErrorMessage } from "./ui";
import { ist, number } from "./format";
import { readLayers, saveLayers } from "./preferences";

export type Layers = {
  trend: boolean;
  bias: boolean;
  events: boolean;
  levels: boolean;
};
export function priceLines(overlay: Schema["IndicatorOverlay"] | undefined) {
  if (!overlay) return [];
  const p = overlay.position;
  const candidates: (readonly [string, number | null])[] = [
    ...(p.posDir !== 0
      ? ([
          ["Entry", p.posEntry],
          ["T1", p.posT1],
          ["T2", p.posT2],
          ["Safety", p.posStop],
        ] as const)
      : []),
    ["Ceiling", overlay.resistance] as const,
    ["Floor", overlay.support] as const,
    ["Next up", overlay.up_trigger] as const,
    ["Next down", overlay.down_trigger] as const,
  ];
  return candidates.filter(
    (line): line is readonly [string, number] =>
      typeof line[1] === "number" && Number.isFinite(line[1]),
  );
}
const Brick = memo(function Brick({
  brick,
  x,
  y,
  step,
}: {
  brick: Schema["BrickData"];
  x: number;
  y: (n: number) => number;
  step: number;
}) {
  const open = Number(brick.open),
    close = Number(brick.close),
    high = Number(brick.wick_high ?? Math.max(open, close)),
    low = Number(brick.wick_low ?? Math.min(open, close));
  return (
    <g>
      {(high > Math.max(open, close) || low < Math.min(open, close)) && (
        <line
          data-wick-index={brick.index}
          x1={x}
          x2={x}
          y1={y(high)}
          y2={y(low)}
          stroke={
            brick.direction === 1
              ? "var(--bull, #7ce8c0)"
              : "var(--bear, #ff9a9f)"
          }
          strokeWidth="1.5"
        />
      )}
      <rect
        data-brick-index={brick.index}
        x={x - step * 0.35}
        y={y(Math.max(open, close))}
        width={Math.max(0.8, step * 0.7)}
        height={Math.max(1, Math.abs(y(open) - y(close)))}
        fill={
          brick.direction === 1
            ? "var(--bull, #7ce8c0)"
            : "var(--bear, #ff9a9f)"
        }
      >
        <title>{`Brick ${brick.index} · ${ist(brick.ts)} · ${brick.open} → ${brick.close} · High ${high} · Low ${low}`}</title>
      </rect>
    </g>
  );
});
export const RenkoChart = memo(function RenkoChart({
  history,
  layers,
  windowSize,
  endIndex,
}: {
  history: Schema["BrickHistory"];
  layers: Layers;
  windowSize: number;
  endIndex: number | null;
}) {
  const bricks = useMemo(
    () =>
      history.items
        .filter((b) => endIndex === null || b.index <= endIndex)
        .slice(-windowSize),
    [history.items, windowSize, endIndex],
  );
  const overlays = useMemo(
    () => new Map((history.overlays ?? []).map((o) => [o.index, o])),
    [history.overlays],
  );
  const last = bricks.length
    ? overlays.get(bricks[bricks.length - 1].index)
    : undefined;
  const lines = layers.levels ? priceLines(last) : [];
  const all = bricks
    .flatMap((b) => [
      Number(b.open),
      Number(b.close),
      Number(b.wick_high ?? Math.max(Number(b.open), Number(b.close))),
      Number(b.wick_low ?? Math.min(Number(b.open), Number(b.close))),
    ])
    .concat(
      layers.trend
        ? bricks.flatMap((b) => {
            const v = overlays.get(b.index)?.supertrend;
            return v == null ? [] : [v];
          })
        : [],
    )
    .filter(Number.isFinite);
  if (!bricks.length) return <p>No Renko history for this source.</p>;
  const min = Math.min(...all),
    max = Math.max(...all),
    pad = Math.max((max - min) * 0.08, 1);
  const y = (v: number) =>
    320 - ((v - min + pad) / (max - min + 2 * pad)) * 295;
  const lineY = (value: number) => Math.min(330, Math.max(15, y(value)));
  const step = 900 / Math.max(1, bricks.length),
    x = (i: number) => 25 + (i + 0.5) * step;
  let previous: { point: string; direction: number } | null = null;
  const segments: { key: number; points: string; direction: number }[] = [];
  for (const [i, b] of bricks.entries()) {
    const o = overlays.get(b.index);
    if (o?.supertrend == null) {
      previous = null;
      continue;
    }
    const point = `${x(i)},${y(o.supertrend)}`;
    if (previous && previous.direction === o.supertrend_direction)
      segments.push({
        key: b.index,
        points: `${previous.point} ${point}`,
        direction: o.supertrend_direction,
      });
    previous = { point, direction: o.supertrend_direction };
  }
  return (
    <div className="renko-frame">
      <svg
        viewBox="0 0 1060 385"
        role="img"
        aria-label={`Renko chart, ${bricks.length} bricks ordered by index; ${bricks.some((b) => Number(b.wick_high ?? b.open) > Math.max(Number(b.open), Number(b.close)) || Number(b.wick_low ?? b.close) < Math.min(Number(b.open), Number(b.close))) ? "with observed wicks" : "body-only"}`}
        data-testid="renko-chart"
      >
        <rect x="20" y="10" width="910" height="325" fill="#0d141d" />
        {layers.bias &&
          bricks.map((b, i) => {
            const o = overlays.get(b.index);
            return o && o.bias_direction !== 0 ? (
              <rect
                key={b.index}
                x={x(i) - step / 2}
                y="10"
                width={step}
                height="325"
                fill={
                  o.bias_direction === 1
                    ? "var(--bull, #7ce8c0)"
                    : "var(--bear, #ff9a9f)"
                }
                opacity={o.bias_strong ? 0.11 : 0.04}
              />
            ) : null;
          })}
        {bricks.map((b, i) => (
          <Brick key={b.index} brick={b} x={x(i)} y={y} step={step} />
        ))}
        {layers.trend &&
          segments.map((s) => (
            <polyline
              data-layer="supertrend"
              key={s.key}
              points={s.points}
              fill="none"
              stroke={s.direction === 1 ? "#b1ffd5" : "#ffb1bd"}
              strokeWidth="2"
            />
          ))}
        {layers.trend &&
          bricks.map((b, i) => {
            const o = overlays.get(b.index),
              prev = overlays.get(bricks[i - 1]?.index);
            return o?.supertrend != null &&
              prev &&
              prev.supertrend_direction !== o.supertrend_direction ? (
              <circle
                key={b.index}
                data-layer="flip"
                cx={x(i)}
                cy={y(o.supertrend)}
                r="4"
                fill="#f1d894"
              >
                <title>Supertrend flip at brick {b.index}</title>
              </circle>
            ) : null;
          })}
        {lines.map(([label, value], i) => (
          <g key={label} data-price-line={label}>
            <line
              x1="20"
              x2="930"
              y1={lineY(value)}
              y2={lineY(value)}
              stroke={label === "Safety" ? "#ff9a9f" : "#9eacc0"}
              strokeDasharray="4 5"
            />
            <text x="938" y={18 + i * 17} fill="#e5edf5" fontSize="11">
              {label} {number(value)}
            </text>
            <title>
              {label} {value}
              {value < min - pad || value > max + pad
                ? " · outside visible price range"
                : ""}
            </title>
          </g>
        ))}
        {layers.events &&
          bricks.flatMap((b, i) =>
            (overlays.get(b.index)?.events ?? []).map((e, j) => (
              <g
                key={`${b.index}:${j}:${e.trade_id}:${e.kind}`}
                data-marker={`${b.index}:${j}:${e.kind}`}
                tabIndex={0}
                role="img"
                aria-label={`${e.kind} ${e.trade_id} ${e.tooltip}`}
              >
                <circle
                  cx={x(i)}
                  cy={y(e.price)}
                  r="5"
                  fill={
                    e.kind === "EXIT"
                      ? "#f1d894"
                      : e.kind === "T1"
                        ? "#8ac5ff"
                        : "#ffffff"
                  }
                />
                <title>{`${e.kind} · ${e.direction === 1 ? "Long" : "Short"} · ${e.trade_id} · ${e.tooltip}${e.replaced_trade_id ? ` · Replaces ${e.replaced_trade_id}` : ""}`}</title>
              </g>
            )),
          )}
        {[0, 1, 2, 3].map((i) => {
          const n = Math.floor((i * (bricks.length - 1)) / 3),
            b = bricks[n];
          return (
            <text
              key={i}
              x={x(n)}
              y="355"
              textAnchor="middle"
              fontSize="10"
              fill="#a4b4c5"
            >
              #{b.index}
            </text>
          );
        })}
        <text x="25" y="378" fontSize="10" fill="#a4b4c5">
          {ist(bricks[0].ts)} — {ist(bricks[bricks.length - 1].ts)} · brick
          index axis
        </text>
      </svg>
      {!!lines.length && (
        <dl className="chart-levels">
          {lines.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>
                {number(value)}
                {value < min - pad || value > max + pad ? " (off range)" : ""}
              </dd>
            </div>
          ))}
        </dl>
      )}
      <details>
        <summary>Accessible chart data and event details</summary>
        <div className="table-scroll">
          <table>
            <caption>
              Visible bricks in index order; equal exchange times remain
              separate.
            </caption>
            <thead>
              <tr>
                <th>Brick</th>
                <th>IST</th>
                <th>Open → Close</th>
                <th>Events</th>
              </tr>
            </thead>
            <tbody>
              {bricks.map((b) => (
                <tr key={b.index}>
                  <td>{b.index}</td>
                  <td>{ist(b.ts)}</td>
                  <td>
                    {b.open} → {b.close}
                  </td>
                  <td>
                    {overlays.get(b.index)?.events.map((e, j) => (
                      <p key={j}>
                        {e.kind} · {e.direction === 1 ? "Long" : "Short"} ·{" "}
                        {e.trade_id} · {e.tooltip}
                      </p>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
});
export const ChartPane = memo(function ChartPane() {
  const { data: source } = useSnapshot((s) => ({
    stream: s.stream,
    config: s.configuration_id,
    latest: s.latest_brick,
    signals: (s.signals ?? []).map((signal) => signal.id).join(":"),
    quoteOnly: s.state === "running_quotes_only_anchor_required",
    historicalAt:
      s.context.chart_display_mode === "historical" &&
      typeof s.context.historical_as_of === "string"
        ? s.context.historical_as_of
        : undefined,
  }));
  return source?.quoteOnly ? (
    <Card title="Renko chart">
      <p role="status">
        Market data is quote-only. A verified Renko anchor is required before
        chart history can be built.
      </p>
      <p>Quotes can continue. Trading entries remain blocked.</p>
    </Card>
  ) : source ? (
    <ChartSession key={`${source.stream}:${source.config}`} source={source} />
  ) : (
    <Card title="Renko chart">
      <p>Loading chart source…</p>
    </Card>
  );
});
function ChartSession({
  source,
}: {
  source: {
    stream: string;
    config: string;
    latest: Schema["BrickData"] | null;
    signals: string;
    historicalAt?: string;
  };
}) {
  const [layers, setLayers] = useState(readLayers),
    [windowSize, setWindowSize] = useState(100),
    [endIndex, setEndIndex] = useState<number | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const key = ["chart", source.stream, source.config];
  const initialAfter = Math.max(-1, (source.latest?.index ?? 299) - 300);
  const history = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      api.get(
        "/api/bricks",
        { stream: source.stream, after: initialAfter, limit: 300 },
        { signal },
      ),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const alive = useRef(true),
    inFlight = useRef(false),
    lastRequestOlder = useRef(false),
    controller = useRef<AbortController | null>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      controller.current?.abort();
    };
  }, []);
  const first = history.data?.items[0]?.index ?? 0,
    last = history.data?.items.at(-1)?.index ?? -1;
  async function load(older: boolean) {
    const previous = cache.getQueryData<Schema["BrickHistory"]>(key);
    if (inFlight.current || !previous) return;
    lastRequestOlder.current = older;
    inFlight.current = true;
    setBusy(true);
    setError(undefined);
    controller.current = new AbortController();
    try {
      const boundary = older
        ? (previous.items[0]?.index ?? 0)
        : (previous.items.at(-1)?.index ?? -1);
      const page = await api.get(
        "/api/bricks",
        {
          stream: source.stream,
          after: older ? Math.max(-1, boundary - 301) : boundary,
          limit: 300,
          revision: previous.revision,
          indicator_source: previous.indicator_source?.source_id,
        },
        { signal: controller.current.signal },
      );
      if (!alive.current) return;
      cache.setQueryData(key, mergeHistory(previous, page));
      if (
        !older &&
        !page.items.length &&
        source.latest &&
        source.latest.index > boundary
      )
        setError(
          new ApiError(
            409,
            "history_not_published",
            null,
            "Latest brick history is not published yet. Retry after the owner publishes it.",
          ),
        );
      if (older) setEndIndex(boundary - 1);
    } catch (err) {
      if (!alive.current) return;
      if (
        (err instanceof ApiError && err.status === 409) ||
        (err instanceof Error &&
          err.message === "Chart source changed; reload history")
      ) {
        setEndIndex(null);
        setNotice(
          "Chart source changed. History and overlays were reloaded together.",
        );
        void cache.resetQueries({ queryKey: key, exact: true });
      } else setError(err);
    } finally {
      inFlight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  const loadRef = useRef(load);
  loadRef.current = load;
  const signalVersion = useRef(source.signals);
  useEffect(() => {
    if (
      error instanceof ApiError &&
      error.code === "history_not_published" &&
      source.latest &&
      source.latest.index <= last
    )
      setError(undefined);
  }, [last, source.latest, error]);
  useEffect(() => {
    if (signalVersion.current !== source.signals) {
      signalVersion.current = source.signals;
      if (history.data) void loadRef.current(false);
    }
  }, [source.signals, history.data]);
  useEffect(() => {
    if (
      ((source.latest && source.latest.index > last) ||
        (!source.latest && history.data?.next_after != null)) &&
      history.data &&
      !busy &&
      !error
    )
      void loadRef.current(false);
  }, [source.latest, last, history.data, busy, error]);
  const data =
    history.error instanceof ApiError && history.error.status === 404
      ? undefined
      : history.data;
  const visible =
    data?.items
      .filter((b) => endIndex === null || b.index <= endIndex)
      .slice(-windowSize) ?? [];
  const canOlder = (visible[0]?.index ?? 0) > 0;
  function olderPage() {
    const boundary = visible[0]?.index ?? 0;
    if (first < boundary) setEndIndex(boundary - 1);
    else void load(true);
  }
  return (
    <Card title="Renko chart">
      <div className="chart-toolbar">
        <label>
          Window
          <select
            aria-label="Brick window"
            value={windowSize}
            onChange={(e) => {
              setWindowSize(Number(e.target.value));
              setEndIndex(null);
            }}
          >
            <option value={100}>Last 100 bricks</option>
            <option value={300}>Last 300 bricks</option>
          </select>
        </label>
        <button disabled={busy || !data || !canOlder} onClick={olderPage}>
          Load older history
        </button>
        <button onClick={() => setEndIndex(null)}>Follow latest</button>
        {Object.entries(layers).map(([k, v]) => (
          <label className="check" key={k}>
            <input
              type="checkbox"
              checked={v}
              onChange={(e) => {
                const next = { ...layers, [k]: e.target.checked };
                setLayers(next);
                saveLayers(next);
              }}
            />
            {k}
          </label>
        ))}
      </div>
      {history.isPending && <p role="status">Loading Renko history…</p>}
      {busy && <p role="status">Loading chart page…</p>}
      {notice && <p role="status">{notice}</p>}
      {history.error instanceof ApiError && history.error.status === 404 ? (
        <p role="status">
          No Renko history for this source yet. Configure verified Renko
          settings and collect matching market data. Trading entries remain
          blocked.
        </p>
      ) : history.error ? (
        <ErrorMessage
          error={history.error}
          retry={() => void history.refetch()}
        />
      ) : null}{" "}
      {error !== undefined && (
        <ErrorMessage
          error={error}
          retry={() => void load(lastRequestOlder.current)}
        />
      )}
      {data && (
        <>
          <p className="source-identity">
            {source.historicalAt && (
              <>
                <strong>
                  Historical / stale · completed through{" "}
                  {ist(source.historicalAt)}
                </strong>
                <br />
              </>
            )}
            {data.configuration.source_minutes === 5 && (
              <>
                5-minute Close · wicks
                <br />
              </>
            )}
            Stream {data.stream} · revision {data.revision} · config{" "}
            <code>{data.configuration_id}</code>
            <br />
            Indicator {data.indicator_source?.mode ?? "unavailable"} · source{" "}
            <code>{data.indicator_source?.source_id ?? "unavailable"}</code> ·
            reference{" "}
            {data.indicator_source?.reference_verified
              ? "verified"
              : "unverified"}
          </p>
          {data.overlay_status !== "complete" && (
            <p className="notice">
              Overlays {data.overlay_status}: {data.overlay_reason}. Warm-up and
              missing values remain unavailable.
            </p>
          )}
          {data.configuration_id !== source.config ? (
            <p className="notice">
              Snapshot and chart configuration differ. Reload server data before
              evaluating this chart.
            </p>
          ) : (
            <RenkoChart
              history={data}
              layers={layers}
              windowSize={windowSize}
              endIndex={endIndex}
            />
          )}
        </>
      )}
    </Card>
  );
}
