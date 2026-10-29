import manifest from "./settings-manifest.json";
import type { components } from "../../docs/api/api-v1";
export type Bundle = components["schemas"]["SettingsBundle-Output"];
export type SettingsView = components["schemas"]["SettingsView"];
export type SettingsUpdate = components["schemas"]["SettingsUpdate"];
export type Json =
  null | boolean | number | string | Json[] | { [key: string]: Json };
export type Rule = {
  $ref?: string;
  type?: string;
  properties?: Record<string, Rule>;
  anyOf?: Rule[];
  items?: Rule;
  enum?: Json[];
  const?: Json;
  default?: Json;
  title?: string;
  format?: string;
  minimum?: number;
  maximum?: number;
  gt?: number;
  ge?: number;
  le?: number;
  lt?: number;
  max_digits?: number;
  decimal_places?: number;
  minLength?: number;
  maxLength?: number;
};
export type PineRule = {
  kind: string;
  default: Json;
  minval?: number;
  maxval?: number;
  options?: string[];
};
export const contract = manifest as unknown as {
  schema: Rule & { $defs: Record<string, Rule> };
  pine: Record<string, PineRule>;
  ui: Record<string, { label: string; group: string; help: string }>;
};
export function resolve(rule: Rule): Rule {
  return rule.$ref ? contract.schema.$defs[rule.$ref.split("/").pop()!] : rule;
}
export function canonical(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  return `{${Object.entries(value)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`)
    .join(",")}}`;
}
export function settingsChanges(
  before: Json,
  after: Json,
  path = "",
): { path: string; before: Json; after: Json }[] {
  if (canonical(before) === canonical(after)) return [];
  if (
    before &&
    after &&
    typeof before === "object" &&
    typeof after === "object" &&
    !Array.isArray(before) &&
    !Array.isArray(after)
  )
    return Object.keys(after).flatMap((key) =>
      settingsChanges(before[key], after[key], path ? `${path}.${key}` : key),
    );
  return [{ path, before, after }];
}
export function getAt(value: Json, path: string): Json {
  return path
    .split(".")
    .reduce((v, k) => (v as Record<string, Json>)?.[k], value);
}
export function setAt(value: Json, path: string, next: Json): Json {
  const copy = structuredClone(value),
    keys = path.split(".");
  const parent = keys
    .slice(0, -1)
    .reduce((v, k) => (v as Record<string, Json>)[k], copy);
  (parent as Record<string, Json>)[keys.at(-1)!] = next;
  // Pine and Renko must always refer to the same grid.
  if (
    path === "data.box" &&
    typeof next === "string" &&
    /^\d+(\.\d+)?$/.test(next) &&
    Number.isFinite(Number(next))
  )
    (copy as { pine: Record<string, Json> }).pine.boxSize = Number(next);
  if (path === "pine.boxSize" && typeof next === "number")
    (copy as { data: Record<string, Json> }).data.box = String(next);
  return copy;
}
function decimalCompare(a: string, b: string): number {
  const parse = (v: string) => {
    const [whole, fraction = ""] = v.replace(/^[+-]/, "").split(".");
    return {
      value: BigInt((whole || "0") + fraction) * (v.startsWith("-") ? -1n : 1n),
      scale: fraction.length,
    };
  };
  const x = parse(a),
    y = parse(b),
    scale = Math.max(x.scale, y.scale);
  const left = x.value * 10n ** BigInt(scale - x.scale),
    right = y.value * 10n ** BigInt(scale - y.scale);
  return left < right ? -1 : left > right ? 1 : 0;
}
export function validateSettings(
  value: unknown,
  pineRules = contract.pine,
): Record<string, string> {
  const errors: Record<string, string> = {};
  function visit(v: unknown, input: Rule, path: string) {
    const rule = resolve(input);
    const fail = (message: string) => {
      errors[path] = message;
    };
    if (rule.anyOf) {
      if (v === null && rule.anyOf.some((r) => r.type === "null")) return;
      return visit(
        v,
        rule.anyOf.find((r) => r.type !== "null")!,
        path,
      );
    }
    if (rule.const !== undefined && v !== rule.const)
      return fail("Unsupported schema version or constant.");
    if (rule.enum && !rule.enum.includes(v as Json))
      return fail("Choose a supported option.");
    if (rule.type === "object") {
      if (!v || typeof v !== "object" || Array.isArray(v))
        return fail("A complete settings object is required.");
      const props = rule.properties ?? {};
      for (const key of Object.keys(v))
        if (!Object.hasOwn(props, key) && path !== "pine")
          errors[`${path}.${key}`.replace(/^\./, "")] = "Unknown field.";
      for (const [key, child] of Object.entries(props))
        visit(
          (v as Record<string, unknown>)[key],
          child,
          path ? `${path}.${key}` : key,
        );
      return;
    }
    if (rule.type === "array") {
      if (!Array.isArray(v)) return fail("Choose a list of supported values.");
      v.forEach((x, i) => visit(x, rule.items!, `${path}.${i}`));
      if (!v.length || new Set(v).size !== v.length)
        fail("Choose unique nonempty values.");
      return;
    }
    if (rule.type === "boolean") {
      if (typeof v !== "boolean") fail("Use true or false.");
      return;
    }
    if (rule.type === "integer") {
      if (typeof v !== "number" || !Number.isSafeInteger(v))
        return fail("Enter a whole number.");
      if (
        (rule.minimum !== undefined && v < rule.minimum) ||
        (rule.maximum !== undefined && v > rule.maximum)
      )
        fail("Outside the allowed bounds.");
      return;
    }
    if (rule.type !== "string") return;
    if (typeof v !== "string") return fail("Enter an exact string value.");
    if (rule.minLength !== undefined && v.length < rule.minLength)
      fail("Value is too short.");
    if (rule.maxLength !== undefined && v.length > rule.maxLength)
      fail("Value is too long.");
    if (
      rule.format === "time" &&
      !/^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d(\.\d{1,6})?)?$/.test(v)
    )
      fail("Use local IST HH:MM or HH:MM:SS, without a timezone.");
    if (
      rule.format === "date" &&
      (!/^\d{4}-\d{2}-\d{2}$/.test(v) ||
        !Number.isFinite(Date.parse(v)) ||
        new Date(v).toISOString().slice(0, 10) !== v)
    )
      fail("Use a valid YYYY-MM-DD date.");
    const decimal =
      rule.gt !== undefined ||
      rule.ge !== undefined ||
      rule.le !== undefined ||
      rule.lt !== undefined ||
      path === "data.anchor";
    if (decimal) {
      if (v.length > 100 || !/^[+-]?\d+(\.\d+)?$/.test(v))
        return fail(
          "Enter an exact finite decimal; exponent notation is not supported.",
        );
      const [whole, fraction = ""] = v.replace(/^[+-]/, "").split(".");
      if (
        rule.decimal_places !== undefined &&
        fraction.replace(/0+$/, "").length > rule.decimal_places
      )
        fail(`At most ${rule.decimal_places} decimal places.`);
      if (
        rule.max_digits !== undefined &&
        whole.replace(/^0+/, "").length + fraction.length > rule.max_digits
      )
        fail("Amount exceeds storage precision.");
      for (const bound of ["gt", "ge", "le", "lt"] as const)
        if (rule[bound] !== undefined) {
          const cmp = decimalCompare(v, String(rule[bound]));
          if (
            (bound === "gt" && cmp <= 0) ||
            (bound === "ge" && cmp < 0) ||
            (bound === "le" && cmp > 0) ||
            (bound === "lt" && cmp >= 0)
          )
            fail(`Must be ${bound} ${rule[bound]}.`);
        }
    }
  }
  visit(value, contract.schema, "");
  if (!value || typeof value !== "object" || Array.isArray(value))
    return errors;
  const root = value as Record<string, unknown>,
    pine = root.pine;
  if (!pine || typeof pine !== "object" || Array.isArray(pine))
    errors.pine = "Complete Pine inputs required.";
  else {
    for (const key of Object.keys(pine))
      if (!Object.hasOwn(pineRules, key))
        errors[`pine.${key}`] = "Unknown Pine input.";
    for (const [key, rule] of Object.entries(pineRules)) {
      const v = (pine as Record<string, unknown>)[key];
      if (
        (rule.kind === "bool" && typeof v !== "boolean") ||
        (["int", "float"].includes(rule.kind) &&
          (typeof v !== "number" ||
            !Number.isFinite(v) ||
            (rule.kind === "int" && !Number.isSafeInteger(v)) ||
            (rule.minval !== undefined && v < rule.minval) ||
            (rule.maxval !== undefined && v > rule.maxval))) ||
        (!["bool", "int", "float"].includes(rule.kind) &&
          (typeof v !== "string" || !v.length)) ||
        (rule.options && !rule.options.includes(v as string))
      )
        errors[`pine.${key}`] = "Invalid Pine type, option or bounds.";
    }
    const p = pine as Record<string, unknown>;
    if (typeof p.orbUntil === "number" && p.orbUntil % 100 >= 60)
      errors["pine.orbUntil"] = "Invalid HHMM minutes.";
    const data = root.data as Record<string, unknown> | undefined;
    if (
      data &&
      String(p.boxSize) !== String(data.box) &&
      Number(p.boxSize) !== Number(data.box)
    )
      errors["data.box"] = "Data box must match Pine boxSize.";
  }
  for (const section of ["strategy", "risk"]) {
    const v = root[section] as Record<string, unknown> | undefined;
    if (!v) continue;
    const seconds = (t: unknown) =>
      typeof t === "string"
        ? t.split(":").reduce((sum, x) => sum * 60 + Number(x), 0) *
          (t.split(":").length === 2 ? 60 : 1)
        : NaN;
    if (!(seconds(v.entry_start) < seconds(v.entry_end)))
      errors[`${section}.entry_end`] = "Entry end must follow entry start.";
    if (section === "risk" && !(seconds(v.entry_end) < seconds(v.square_off)))
      errors["risk.square_off"] = "Square-off must follow the entry window.";
    if (section === "risk")
      for (const key of ["daily_loss_pct", "max_trade_loss_pct"])
        if (
          typeof v[key] === "string" &&
          !errors[`risk.${key}`] &&
          decimalCompare(v[key], "100") > 0
        )
          errors[`risk.${key}`] = "Risk cannot exceed 100% of capital.";
  }
  const fills = root.fills as Record<string, unknown> | undefined;
  if (
    fills?.cost_schedule &&
    (Number(fills.fee_per_order) !== 0 || Number(fills.fee_bps) !== 0)
  )
    errors["fills.cost_schedule"] =
      "Choose a dated cost schedule or legacy fees, not both.";
  const costs = fills?.cost_schedule as Record<string, string> | undefined;
  if (costs && costs.effective_to < costs.effective_from)
    errors["fills.cost_schedule.effective_to"] =
      "End date must follow start date.";
  return errors;
}
export function importSettings(text: string): Json {
  if (text.length > 200000) throw new Error("Settings file exceeds 200 KB.");
  const value: unknown = JSON.parse(text),
    errors = validateSettings(value);
  if (Object.keys(errors).length)
    throw new Error(
      Object.entries(errors)
        .map(([k, v]) => `${k || "settings"}: ${v}`)
        .join("\n"),
    );
  return value as Json;
}
export function dependency(path: string, draft: Json): string | undefined {
  const pineParents: Record<string, string[]> = {
    stopCapBx: ["exitOnStop"],
    pbMinAge: ["pbOn"],
    brkAge: ["brkOn"],
    trapBars: ["trapOn"],
    oiMinPct: ["flowOn", "useOI"],
    flowBars: ["flowOn"],
    flowTf: ["flowOn"],
    futSym: ["flowOn"],
    useOI: ["flowOn"],
    pxMinPct: ["flowOn"],
    volMult: ["flowOn"],
    srgMin: ["srgOn", "flowOn"],
    srgNeedVol: ["srgOn", "flowOn"],
    orbUntil: ["orbOn"],
    orbMinBx: ["orbOn"],
  };
  const key = path.split(".").at(-1)!;
  if (path.startsWith("pine.")) {
    const parents = pineParents[key] ?? [];
    if (parents.some((p) => getAt(draft, `pine.${p}`) === false))
      return `Enable ${parents.join(" and ")} to use this input.`;
  }
  if (
    path === "strategy.fixed_lots" &&
    getAt(draft, "strategy.sizing") !== "fixed_lots"
  )
    return "Used only for fixed-lot sizing.";
  if (
    path === "strategy.risk_pct" &&
    getAt(draft, "strategy.sizing") !== "risk_pct"
  )
    return "Used only for risk-percentage sizing.";
  if (
    path === "strategy.hedge_target_premium" &&
    getAt(draft, "strategy.hedge_mode") !== "premium"
  )
    return "Used only for premium hedge selection.";
  if (
    path === "strategy.profit_capture_pct" &&
    !getAt(draft, "strategy.profit_capture_enabled")
  )
    return "Enable profit capture first.";
  return undefined;
}
export type PendingSettings = { key: string; body: SettingsUpdate };
let memory: PendingSettings | null = null;
export function pendingSettings(
  value?: PendingSettings | null,
): PendingSettings | null {
  if (value !== undefined) {
    memory = value;
    try {
      if (value)
        sessionStorage.setItem(
          "aurevon.pending.settings",
          JSON.stringify(value),
        );
      else sessionStorage.removeItem("aurevon.pending.settings");
    } catch {
      /* memory fallback */
    }
    return value;
  }
  if (memory) return memory;
  try {
    const saved = JSON.parse(
      sessionStorage.getItem("aurevon.pending.settings") || "null",
    ) as PendingSettings | null;
    if (
      saved &&
      typeof saved.key === "string" &&
      Number.isSafeInteger(saved.body.expected_revision) &&
      typeof saved.body.rebuild === "boolean" &&
      !Object.keys(validateSettings(saved.body.settings)).length
    )
      memory = saved;
  } catch {
    /* corrupted storage is not an executable request */
  }
  return memory;
}
