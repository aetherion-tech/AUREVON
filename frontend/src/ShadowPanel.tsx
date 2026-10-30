import { useQuery } from "@tanstack/react-query";
import { api } from "./state";
import { Card, ErrorMessage } from "./ui";

export function ShadowPanel() {
  const status = useQuery({
    queryKey: ["shadow-status"],
    queryFn: ({ signal }) =>
      api.get("/api/shadow/status", undefined, { signal }),
    refetchInterval: 15000,
  });
  const last = status.data?.latest_index;
  const comparison = useQuery({
    queryKey: ["shadow-comparison", status.data?.source_id, last],
    enabled: !!status.data?.enabled && !!status.data.source_id && last != null,
    queryFn: ({ signal }) =>
      api.get(
        "/api/shadow/comparison",
        {
          start: Math.max(0, (last ?? 0) - 200),
          end: last ?? 0,
        },
        { signal },
      ),
    refetchInterval: 15000,
  });
  const result = comparison.data;
  const missing = result
    ? result.missing_backend.length + result.missing_tradingview.length
    : 0;
  return (
    <Card title="TradingView shadow comparison">
      <p>Observation only. Alerts never place or close trades.</p>
      {status.error && (
        <ErrorMessage
          error={status.error}
          retry={() => void status.refetch()}
        />
      )}
      {status.isPending && <p role="status">Loading shadow configuration…</p>}
      {status.data && !status.data.enabled && (
        <p>
          Shadow ingestion is disabled. No TradingView comparison evidence is
          available.
        </p>
      )}
      {status.data?.enabled && !status.data.source_id && (
        <p role="alert">
          Matching indicator source unavailable. Shadow acceptance is blocked.
        </p>
      )}
      {comparison.error && (
        <ErrorMessage
          error={comparison.error}
          retry={() => void comparison.refetch()}
        />
      )}
      {result && (
        <>
          <p>
            Bricks {result.start}–{result.end} · {result.matched} matched ·{" "}
            {result.pending} awaiting the two-brick window
          </p>
          {missing > 0 ? (
            <p role="alert" className="notice error">
              Shadow mismatch: {result.missing_tradingview.length} missing from
              TradingView; {result.missing_backend.length} missing from backend.
            </p>
          ) : (
            <p>
              No mismatch in this bounded window. This does not establish
              reference or burn-in acceptance.
            </p>
          )}
          {missing > 0 && (
            <details>
              <summary>Mismatch event identifiers</summary>
              <ul>
                {result.missing_tradingview.map((id) => (
                  <li key={`tv:${id}`}>TradingView missing: {id}</li>
                ))}
                {result.missing_backend.map((id) => (
                  <li key={`be:${id}`}>Backend missing: {id}</li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </Card>
  );
}
