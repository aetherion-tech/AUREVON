import type { components, paths } from "../../docs/api/api-v1";

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
