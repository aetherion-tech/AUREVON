import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, cache } from "./state";
import { useSnapshot } from "./live-data";
import { ErrorMessage } from "./ui";

export function FeedControls() {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const state = useSnapshot((s) => ({ desired: s.desired, state: s.state }));
  const kite = useQuery({
    queryKey: ["kite"],
    queryFn: ({ signal }) =>
      api.get("/api/auth/kite/status", undefined, { signal }),
    refetchInterval: 30000,
  });
  async function change(start: boolean) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    try {
      const snapshot = await api.post(
        start ? "/api/market/service/start" : "/api/market/service/stop",
        {},
        { key: crypto.randomUUID() },
      );
      cache.setQueryData(["snapshot"], snapshot);
    } catch (issue) {
      setError(issue);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="feed-controls">
      <p>
        After Kite login, saved Renko history loads automatically. Start market
        data for live updates. Chart display and starting data do not enable
        paper entries.
      </p>
      <button
        disabled={busy || !kite.data?.authenticated || !!state.data?.desired}
        onClick={() => void change(true)}
      >
        {busy ? "Updating market data…" : "Start market data"}
      </button>{" "}
      <button
        disabled={busy || !state.data?.desired}
        onClick={() => void change(false)}
      >
        Stop market data
      </button>
      {!kite.data?.authenticated && (
        <p>
          Complete Kite login until the status says Verified to load chart
          history. Previously saved history can remain visible while the feed is
          stopped.
        </p>
      )}
      {state.data?.desired && (
        <p role="status">
          Data service requested · {state.data.state}. Warm-up/recovery can take
          time; entries remain blocked.
        </p>
      )}
      {state.data?.state === "running_quotes_only_anchor_required" && (
        <p>
          Quotes only: live prices can display, but the Renko chart needs a
          verified anchor. Trading entries remain blocked.
        </p>
      )}
      {error != null && <ErrorMessage error={error} />}
    </div>
  );
}
