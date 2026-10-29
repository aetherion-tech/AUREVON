import { QueryClient } from "@tanstack/react-query";
import { ApiClient, type Event, type Snapshot } from "./api/client";
import type { components } from "../../docs/api/api-v1";
export const api = new ApiClient();
export const cache = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5000, retry: false, refetchOnWindowFocus: true },
    mutations: { retry: false },
  },
});
export function reduceEvent(state: Snapshot, event: Event): Snapshot {
  switch (event.kind) {
    case "tick": {
      const tick = event.payload as components["schemas"]["TickData"];
      return {
        ...state,
        ticks: [...state.ticks.filter((t) => t.token !== tick.token), tick],
        sequence: event.sequence,
      };
    }
    case "brick":
      return {
        ...state,
        latest_brick: event.payload as components["schemas"]["BrickData"],
        sequence: event.sequence,
      };
    case "status":
      return {
        ...state,
        ...(event.payload as components["schemas"]["StatusData"]),
        sequence: event.sequence,
      };
    case "signal": {
      const signal = event.payload as components["schemas"]["SignalData"];
      return {
        ...state,
        signals: [
          ...(state.signals ?? []).filter((s) => s.id !== signal.id),
          signal,
        ].slice(-200),
        sequence: event.sequence,
      };
    }
    case "position": {
      const p = event.payload as components["schemas"]["PositionData"];
      return p.detail
        ? {
            ...state,
            positions: [
              ...(state.positions ?? []).filter(
                (x) => x.trade_id !== p.trade_id,
              ),
              p.detail,
            ],
            sequence: event.sequence,
          }
        : { ...state, sequence: event.sequence };
    }
    // Durable domains are reloaded from their canonical REST projections.
    default:
      return { ...state, sequence: event.sequence };
  }
}
