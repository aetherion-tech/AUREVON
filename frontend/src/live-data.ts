import { useQuery } from "@tanstack/react-query";
import { api } from "./state";
import type { Snapshot } from "./api/client";
import type { components } from "../../docs/api/api-v1";
export type Schema = components["schemas"];
export function useSnapshot<T>(select: (snapshot: Snapshot) => T) {
  return useQuery({
    queryKey: ["snapshot"],
    queryFn: ({ signal }) =>
      api.get("/api/live/snapshot", undefined, { signal }),
    select,
  });
}
export function todayIST(at = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(at);
}
export function decimal(value: string | number | null | undefined): string {
  return value == null ? "Unavailable" : String(value);
}
export function duration(
  from: string,
  until: string | null | undefined,
  now: number,
): string {
  const seconds = Math.max(
    0,
    Math.floor(((until ? Date.parse(until) : now) - Date.parse(from)) / 1000),
  );
  return Number.isFinite(seconds)
    ? `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m ${seconds % 60}s`
    : "Unavailable";
}
export function mergeIndexed<T extends { index: number }>(
  old: T[],
  incoming: T[],
): T[] {
  const map = new Map(old.map((item) => [item.index, item]));
  for (const item of incoming) {
    const previous = map.get(item.index);
    map.set(
      item.index,
      previous && JSON.stringify(previous) === JSON.stringify(item)
        ? previous
        : item,
    );
  }
  return [...map.values()].sort((a, b) => a.index - b.index);
}
export function mergeHistory(
  old: Schema["BrickHistory"],
  page: Schema["BrickHistory"],
): Schema["BrickHistory"] {
  if (
    old.stream !== page.stream ||
    old.revision !== page.revision ||
    old.configuration_id !== page.configuration_id ||
    old.indicator_source?.source_id !== page.indicator_source?.source_id
  )
    throw new Error("Chart source changed; reload history");
  return {
    ...page,
    items: mergeIndexed(old.items, page.items),
    overlays: mergeIndexed(old.overlays ?? [], page.overlays ?? []),
  };
}
