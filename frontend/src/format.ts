export function money(value: string | null | undefined): string {
  if (value == null || !/^-?\d+(\.\d{1,2})?$/.test(value)) return "Unavailable";
  const negative = value.startsWith("-");
  const [whole, fraction = ""] = value.replace("-", "").split(".");
  return `${negative ? "−" : ""}₹${BigInt(whole).toLocaleString("en-IN")}.${fraction.padEnd(2, "0")}`;
}
export function number(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value)
    ? "Unavailable"
    : value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}
export function percent(value: number | null): string {
  return value == null ? "Unavailable" : `${number(value)}%`;
}
export function ist(value: string | Date): string {
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? "Unavailable"
    : new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        dateStyle: "medium",
        timeStyle: "medium",
      }).format(d) + " IST";
}
export function depositAmount(value: string): boolean {
  if (!/^\d+(\.\d{1,2})?$/.test(value)) return false;
  const [w, f = ""] = value.split(".");
  const paise = BigInt(w) * 100n + BigInt(f.padEnd(2, "0"));
  return paise > 0n && paise <= 99999999999999n;
}
