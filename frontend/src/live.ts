import { useEffect, useState } from "react";
import { api, cache, reduceEvent } from "./state";
import { ApiError, LiveCursor, type Frame } from "./api/client";
export function useLive(enabled: boolean, expired: () => void) {
  const [connection, setConnection] = useState("Disconnected");
  useEffect(() => {
    if (!enabled) return;
    let stopped = false,
      socket: WebSocket | undefined,
      timer: ReturnType<typeof setTimeout> | undefined,
      attempts = 0;
    const controller = new AbortController(),
      cursor = new LiveCursor();
    const schedule = () => {
      if (!stopped) {
        setConnection("Disconnected · reconnecting");
        timer = setTimeout(
          () => void connect(),
          Math.min(30000, 1000 * 2 ** attempts++) + Math.random() * 250,
        );
      }
    };
    async function connect() {
      try {
        setConnection("Loading snapshot");
        const snapshot = await api.get("/api/live/snapshot", undefined, {
          signal: controller.signal,
        });
        if (stopped) return;
        cursor.reset(snapshot);
        cache.setQueryData(["snapshot"], snapshot);
        await cache.invalidateQueries({
          predicate: (q) =>
            !["snapshot", "session"].includes(String(q.queryKey[0])),
        });
        if (stopped) return;
        socket = new WebSocket(api.liveUrl(cursor));
        socket.onopen = () => {
          attempts = 0;
          setConnection("Connected");
        };
        socket.onmessage = (message) => {
          if (stopped) return;
          try {
            const frame = JSON.parse(String(message.data)) as Frame;
            const accepted = cursor.accept(frame);
            if (accepted.resync) {
              socket?.close();
              return;
            }
            if (frame.type === "snapshot")
              cache.setQueryData(["snapshot"], frame.snapshot);
            else if (accepted.events.length) {
              cache.setQueryData(
                ["snapshot"],
                (old: typeof snapshot | undefined) =>
                  old && accepted.events.reduce(reduceEvent, old),
              );
              if (
                accepted.events.some((e) =>
                  ["trade", "position", "signal", "alert", "status"].includes(
                    e.kind,
                  ),
                )
              )
                void cache.invalidateQueries({
                  predicate: (q) =>
                    [
                      "wallet",
                      "positions",
                      "signals",
                      "trades",
                      "history",
                      "alerts",
                      "pnl",
                    ].includes(String(q.queryKey[0])),
                });
            }
          } catch {
            socket?.close();
          }
        };
        socket.onclose = (event) => {
          if (stopped) return;
          if (event.code === 1008) {
            expired();
            return;
          }
          schedule();
        };
        socket.onerror = () => socket?.close();
      } catch (error) {
        if (stopped) return;
        if (error instanceof ApiError && error.status === 401) expired();
        else schedule();
      }
    }
    void connect();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
      socket?.close();
    };
  }, [enabled, expired]);
  return connection;
}
