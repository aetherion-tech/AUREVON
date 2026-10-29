import type { paths } from "../../docs/api/api-v1";
import type { Schema } from "./live-data";
import { todayIST } from "./live-data";
export type TradeQuery = NonNullable<
  paths["/api/trades"]["get"]["parameters"]["query"]
>;
export function shiftDay(day: string, amount: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + amount);
  return d.toISOString().slice(0, 10);
}
export function validDay(day: string): boolean {
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(day) &&
    Number.isFinite(Date.parse(day)) &&
    new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10) === day
  );
}
export function historyFilters(
  params: URLSearchParams,
  today = todayIST(),
): { query: TradeQuery; error: string; start: string; end: string } {
  const start = params.get("start") ?? shiftDay(today, -30),
    end = params.get("end") ?? today;
  let error = "";
  if (!validDay(start) || !validDay(end) || end < start || end > today)
    error = "Choose valid ordered IST dates, ending no later than today.";
  const allowed: Record<string, string[]> = {
    mode: ["PAPER"],
    family: ["CO", "DIV", "OT"],
    direction: ["1", "-1"],
    result: ["WIN", "LOSS", "FLAT"],
    grade: ["1", "2", "3"],
    sort: ["closed_at", "net"],
    order: ["asc", "desc"],
  };
  for (const [name, values] of Object.entries(allowed)) {
    const raw = params.get(name);
    if (raw && !values.includes(raw))
      error = `Unsupported ${name} filter. Reset the filters.`;
  }
  const query: TradeQuery = {
    mode: "PAPER",
    start,
    end,
    sort: params.get("sort") === "net" ? "net" : "closed_at",
    order: params.get("order") === "asc" ? "asc" : "desc",
  };
  const family = params.get("family");
  if (family === "CO" || family === "DIV" || family === "OT")
    query.family = family;
  const direction = params.get("direction");
  if (direction === "1" || direction === "-1")
    query.direction = direction === "1" ? 1 : -1;
  const result = params.get("result");
  if (result === "WIN" || result === "LOSS" || result === "FLAT")
    query.result = result;
  const grade = params.get("grade");
  if (grade && ["1", "2", "3"].includes(grade)) query.grade = Number(grade);
  return { query, error, start, end };
}
export function paise(value: string): bigint {
  if (!/^-?\d+(\.\d{1,2})?$/.test(value))
    throw new Error("Invalid exact money");
  const sign = value.startsWith("-") ? -1n : 1n;
  const [whole, frac = ""] = value.replace("-", "").split(".");
  return sign * (BigInt(whole) * 100n + BigInt(frac.padEnd(2, "0")));
}
export function rupees(value: bigint): string {
  const n = value < 0n ? -value : value;
  return `${value < 0n ? "-" : ""}${n / 100n}.${String(n % 100n).padStart(2, "0")}`;
}
export function winRate(wins: number, trades: number): string {
  return trades === 0
    ? "Unavailable"
    : `${Number((BigInt(wins) * 10000n) / BigInt(trades)) / 100}%`;
}
export function pnlSeries(rows: Schema["PnlSummary"][]) {
  let cumulative = 0n;
  return [...rows]
    .sort((a, b) => a.start.localeCompare(b.start))
    .map((row) => {
      cumulative += paise(row.net);
      return { day: row.start, net: row.net, cumulative: rupees(cumulative) };
    });
}
