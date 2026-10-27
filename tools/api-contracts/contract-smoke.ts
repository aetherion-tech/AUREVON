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
