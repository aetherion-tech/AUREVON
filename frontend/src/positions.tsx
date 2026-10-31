import { money } from "./format";
import type { Schema } from "./live-data";

export function totalOpenPnl(
  positions: Schema["PositionView"][],
): string | null {
  let total = 0n;
  for (const p of positions) {
    if (p.unrealised == null || !/^-?\d+(\.\d{1,2})?$/.test(p.unrealised))
      return null;
    const [whole, fraction = ""] = p.unrealised.replace("-", "").split(".");
    total +=
      (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"))) *
      (p.unrealised.startsWith("-") ? -1n : 1n);
  }
  const absolute = total < 0n ? -total : total;
  return `${total < 0n ? "-" : ""}${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
}

export function PnlValue({
  value,
  prominent = false,
}: {
  value: string | null | undefined;
  prominent?: boolean;
}) {
  const formatted = money(value);
  const tone =
    formatted === "Unavailable"
      ? ""
      : value?.startsWith("-") && !/^-0(\.0+)?$/.test(value)
        ? "pnl-loss"
        : /^0(\.0+)?$/.test(value ?? "")
          ? ""
          : "pnl-profit";
  return (
    <strong className={`${prominent ? "pnl-total " : ""}${tone}`}>
      {formatted}
    </strong>
  );
}
