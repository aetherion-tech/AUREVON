import { afterEach, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { mergeHistory, mergeIndexed, duration, type Schema } from "./live-data";
import { priceLines, RenkoChart } from "./Chart";
afterEach(cleanup);
const brick = (index: number): Schema["BrickData"] => ({
  index,
  open: "100",
  close: "150",
  direction: 1,
  ts: "2026-10-29T09:30:00+05:30",
  volume: "0",
});
const overlay = (index: number): Schema["IndicatorOverlay"] => ({
  index,
  at: brick(index).ts,
  atr: null,
  rsi: null,
  supertrend: null,
  supertrend_direction: 1,
  bias_direction: 1,
  bias_score: 3,
  bias_strong: false,
  factors: {},
  support: null,
  resistance: null,
  up_probability: null,
  up_trigger: 200,
  down_trigger: 50,
  position: {
    posDir: 1,
    posEntry: 100,
    posT1: 150,
    posT2: 200,
    posStop: 50,
    posId: "CO-L",
    posBar: 0,
    posT1Hit: false,
    posType: "CO",
    posGrade: 3,
  },
  events: [
    {
      kind: "ENTRY",
      trade_id: "CO-L",
      direction: 1,
      price: 100,
      tooltip: "CO Long Grade 3",
    },
  ],
});
const history = (): Schema["BrickHistory"] => ({
  indicators_available: false,
  overlay_reason: "not_published",
  overlay_status: "unavailable",
  stream: "s",
  revision: 1,
  configuration_id: "config",
  configuration: {},
  indicator_source: null,
  items: [brick(0), brick(1)],
  overlays: [overlay(0), overlay(1)],
  next_after: null,
});
it("merges by index without collapsing equal timestamps and preserves unchanged objects", () => {
  const old = [brick(1), brick(0)];
  const result = mergeIndexed(old, [brick(1), brick(2)]);
  expect(result.map((b) => b.index)).toEqual([0, 1, 2]);
  expect(result[1]).toBe(old[0]);
  expect(result[0].ts).toBe(result[2].ts);
});
it("rejects cross-revision and cross-source pages atomically", () => {
  const old = history();
  expect(() => mergeHistory(old, { ...old, revision: 2 })).toThrow(
    /source changed/,
  );
  expect(() =>
    mergeHistory(old, { ...old, configuration_id: "new" }),
  ).toThrow();
  expect(old.items).toHaveLength(2);
});
it("deduplicates history and event overlays when a page repeats", () => {
  const old = history(),
    next = mergeHistory(old, old);
  expect(next.items).toHaveLength(2);
  expect(next.overlays).toHaveLength(2);
  expect(next.overlays?.[0].events).toHaveLength(1);
});
it("removes active levels when the indicator position is flat and never invents null levels", () => {
  const o = overlay(1);
  expect(priceLines(o).map((l) => l[0])).toContain("Entry");
  const flat = { ...o, position: { ...o.position, posDir: 0 as const } };
  expect(priceLines(flat).map((l) => l[0])).toEqual(["Next up", "Next down"]);
  expect(priceLines(undefined)).toEqual([]);
});
it("draws separate no-wick bricks and accessible event details for repeated timestamps", () => {
  const { container } = render(
    <RenkoChart
      history={history()}
      layers={{ trend: true, bias: true, events: true, levels: true }}
      windowSize={100}
      endIndex={null}
    />,
  );
  expect(container.querySelectorAll("[data-brick-index]")).toHaveLength(2);
  expect(container.querySelectorAll("[data-marker]")).toHaveLength(2);
  expect(
    container.querySelectorAll("line:not([stroke-dasharray])"),
  ).toHaveLength(0);
  expect(container.querySelectorAll('[data-price-line="Entry"]')).toHaveLength(
    1,
  );
});
it("keeps missing supertrend values empty and terminates segments across flips", () => {
  const h = history();
  h.overlays = [
    { ...overlay(0), supertrend: 80 },
    { ...overlay(1), supertrend: 180, supertrend_direction: -1 },
  ];
  const { container } = render(
    <RenkoChart
      history={h}
      layers={{ trend: true, bias: false, events: false, levels: false }}
      windowSize={300}
      endIndex={null}
    />,
  );
  expect(container.querySelectorAll('[data-layer="supertrend"]')).toHaveLength(
    0,
  );
  expect(container.querySelectorAll('[data-layer="flip"]')).toHaveLength(1);
});
it("uses the fixed final timestamp for closed duration and rejects invalid timestamps", () => {
  expect(
    duration("2026-10-29T00:00:00Z", "2026-10-29T01:01:01Z", Date.now()),
  ).toBe("1h 1m 1s");
  expect(duration("invalid", null, Date.now())).toBe("Unavailable");
});
