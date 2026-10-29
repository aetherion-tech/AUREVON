// Separate pending command recovery from server cache and display preferences.
export type Intent = { key: string; amount: string };
const pending = new Map<string, Intent>();
export function readIntent(kind: string): Intent | null {
  if (pending.has(kind)) return pending.get(kind)!;
  try {
    const value = JSON.parse(
      sessionStorage.getItem(`aurevon.pending.${kind}`) || "null",
    ) as Intent | null;
    if (
      value &&
      typeof value.key === "string" &&
      typeof value.amount === "string"
    ) {
      pending.set(kind, value);
      return value;
    }
  } catch {
    /* memory retains recovery if storage is unavailable */
  }
  return null;
}
export function saveIntent(kind: string, value: Intent | null) {
  if (value) pending.set(kind, value);
  else pending.delete(kind);
  try {
    if (value)
      sessionStorage.setItem(`aurevon.pending.${kind}`, JSON.stringify(value));
    else sessionStorage.removeItem(`aurevon.pending.${kind}`);
  } catch {
    /* retain in memory for this page */
  }
}
