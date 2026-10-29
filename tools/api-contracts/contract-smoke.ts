import type { components, paths } from "../../docs/api/api-v1";
import { ApiClient, LiveCursor } from "../../frontend/src/api/client";

function domainClientContracts(client: ApiClient, cursor: LiveCursor) {
  void client.get("/api/wallet");
  void client.post("/api/wallet/deposit", { amount: "100.00" }, { key: "one-intended-deposit" });
  // @ts-expect-error exact INR input is a decimal string, never a floating number.
  void client.post("/api/wallet/deposit", { amount: 100.1 }, { key: "bad" });
  // @ts-expect-error client mutations require a stable idempotency key.
  void client.post("/api/kill", {}, {});
  void client.get("/api/signals", { stream: "NIFTY-paper", limit: 50 });
  void client.liveUrl(cursor);
}
void domainClientContracts;

type Snapshot = components["schemas"]["LiveSnapshot"];
type Frames = components["schemas"]["WebSocketMessage"];
type Login = paths["/api/auth/dashboard/login"]["post"]["requestBody"]["content"]["application/json"];

function sequence(frame: Frames): number {
  if (frame.type === "snapshot") return frame.snapshot.sequence;
  return frame.sequence;
}

const password: Login = { password: "local-fixture-only" };
const paper: Snapshot["mode"] = "PAPER";
// @ts-expect-error live mode is unavailable in the funded paper contract.
const live: Snapshot["mode"] = "LIVE";
void [sequence, password, paper, live];

type Preview = paths["/api/settings/preview-strikes"]["post"]["responses"][200]["content"]["application/json"];
type Plan = components["schemas"]["TradePlan"];
const nonexecuting: Preview["executable"] = false;
const marginSource: Plan["margin_source"] = "PAPER_ESTIMATE";
const exactCredit: Plan["credit"] = "6712.50";
// @ts-expect-error a preview can never authorize execution.
const executing: Preview["executable"] = true;
// @ts-expect-error wire amounts are exact strings.
const floatingCredit: Plan["credit"] = 6712.5;
void [nonexecuting, marginSource, exactCredit, executing, floatingCredit];

type ChartPage = paths["/api/bricks"]["get"]["responses"][200]["content"]["application/json"];
type ChartPoint = components["schemas"]["IndicatorOverlay"];
const warmup: Pick<ChartPoint, "index" | "rsi"> = { index: 0, rsi: null };
const partial: ChartPage["overlay_status"] = "partial";
const noReferenceClaim: components["schemas"]["IndicatorHistorySource"]["reference_verified"] = false;
// @ts-expect-error a replay publication does not assert TradingView acceptance.
const inventedParity: components["schemas"]["IndicatorHistorySource"]["reference_verified"] = true;
void [warmup, partial, noReferenceClaim, inventedParity];
