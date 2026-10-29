import { useEffect, useRef, useState, type FormEvent } from "react";
import type { components } from "../../docs/api/api-v1";
import { api } from "./state";
import { Card, ErrorMessage } from "./ui";
import { money, ist } from "./format";
type Decision = components["schemas"]["PlanDecision"];
export function StrikePreview({ dirty }: { dirty: boolean }) {
  const [direction, setDirection] = useState<1 | -1>(1),
    [family, setFamily] = useState<"CO" | "DIV" | "OT">("CO"),
    [grade, setGrade] = useState(2);
  const [spot, setSpot] = useState(""),
    [target1, setTarget1] = useState(""),
    [target2, setTarget2] = useState(""),
    [capital, setCapital] = useState("");
  const [risk, setRisk] = useState<"Low" | "Medium" | "High">("Low"),
    [bias, setBias] = useState<-1 | 0 | 1>(0);
  const [result, setResult] = useState<Decision>(),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null),
    generation = useRef(0);
  useEffect(() => () => controller.current?.abort(), []);
  const positive = (v: string) =>
    v.length <= 30 &&
    /^\d+(\.\d{1,6})?$/.test(v) &&
    Number(v) > 0 &&
    Number.isFinite(Number(v));
  // This directional check only enables preview; exact plan economics are computed by the server.
  const valid =
    [spot, target1, target2].every(positive) &&
    direction * (Number(target1) - Number(spot)) > 0 &&
    direction * (Number(target2) - Number(spot)) > 0 &&
    (!capital || /^\d+(\.\d{1,2})?$/.test(capital));
  function changed() {
    generation.current++;
    controller.current?.abort();
    setBusy(false);
    setResult(undefined);
    setError(undefined);
  }
  async function preview(e: FormEvent) {
    e.preventDefault();
    if (!valid || dirty || busy) return;
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    const current = ++generation.current;
    setBusy(true);
    setResult(undefined);
    setError(undefined);
    try {
      const response = await api.post(
        "/api/strikes/preview",
        {
          signal: {
            version: 1,
            signal_id: "ui-hypothetical-preview",
            trade_id: "[PREV1]",
            direction,
            family,
            grade,
            risk,
            bias_direction: bias,
            at: new Date().toISOString(),
            spot,
            index_target_1: target1,
            index_target_2: target2,
            replaced_trade_id: null,
          },
          free_capital: capital || null,
        },
        { key: crypto.randomUUID(), signal: request.signal },
      );
      if (current === generation.current && !request.signal.aborted)
        setResult(response);
    } catch (err) {
      if (current === generation.current && !request.signal.aborted)
        setError(err);
    } finally {
      if (current === generation.current) setBusy(false);
    }
  }
  return (
    <Card title="Read-only strike preview">
      <p>
        Hypothetical signal using the saved server strategy, current catalog and
        available quotes. Preview cannot subscribe to quotes, reserve funds,
        save a trading decision or place orders. Capital below is an explicit
        assumption, not wallet or project cash.
      </p>
      {dirty && (
        <p className="warning">
          Save or discard settings edits before previewing; unsaved settings are
          not used.
        </p>
      )}
      <form onSubmit={(e) => void preview(e)} onChange={changed}>
        <div className="settings-fields">
          <label>
            Preview direction
            <select
              value={direction}
              onChange={(e) => setDirection(Number(e.target.value) as 1 | -1)}
            >
              <option value={1}>Long index / bull put spread</option>
              <option value={-1}>Short index / bear call spread</option>
            </select>
          </label>
          <label>
            Signal family
            <select
              value={family}
              onChange={(e) => setFamily(e.target.value as typeof family)}
            >
              {["CO", "DIV", "OT"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Signal grade
            <select
              value={grade}
              onChange={(e) => setGrade(Number(e.target.value))}
            >
              {[1, 2, 3].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Signal risk
            <select
              value={risk}
              onChange={(e) => setRisk(e.target.value as typeof risk)}
            >
              {["Low", "Medium", "High"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Index bias
            <select
              value={bias}
              onChange={(e) => setBias(Number(e.target.value) as typeof bias)}
            >
              <option value={0}>Neutral</option>
              <option value={1}>Long</option>
              <option value={-1}>Short</option>
            </select>
          </label>
          <label>
            Index spot
            <input
              inputMode="decimal"
              value={spot}
              onChange={(e) => setSpot(e.target.value)}
            />
          </label>
          <label>
            Index target 1
            <input
              inputMode="decimal"
              value={target1}
              onChange={(e) => setTarget1(e.target.value)}
            />
          </label>
          <label>
            Index target 2
            <input
              inputMode="decimal"
              value={target2}
              onChange={(e) => setTarget2(e.target.value)}
            />
          </label>
          <label>
            Assumed free capital INR (optional)
            <input
              inputMode="decimal"
              value={capital}
              onChange={(e) => setCapital(e.target.value)}
            />
          </label>
        </div>
        <p>
          Targets must agree with the index direction. Missing live catalog,
          quotes or capital remain explicit rejection reasons.
        </p>
        <button disabled={!valid || dirty || busy}>
          {busy ? "Loading preview…" : "Preview strikes without execution"}
        </button>
      </form>
      {error !== undefined && <ErrorMessage error={error} />}
      {!dirty && result && (
        <div role="status">
          <p>
            {result.accepted ? "Preview accepted" : "Preview rejected"}:{" "}
            {result.reason}. Executable: {String(result.executable)}.
          </p>
          {result.plan && (
            <>
              <p>
                {result.plan.structure} · expiry {result.plan.expiry} ·{" "}
                {result.plan.lots} lots
              </p>
              <p>
                Short {result.plan.short.contract.symbol} · strike{" "}
                {result.plan.short.contract.strike} · quantity{" "}
                {result.plan.short.quantity} · limit{" "}
                {money(result.plan.short.limit_price)}
              </p>
              <p>
                Hedge {result.plan.hedge.contract.symbol} · strike{" "}
                {result.plan.hedge.contract.strike} · quantity{" "}
                {result.plan.hedge.quantity} · limit{" "}
                {money(result.plan.hedge.limit_price)}
              </p>
              <p>
                Credit {money(result.plan.credit)} · estimated margin{" "}
                {money(result.plan.required_margin)} · maximum gross loss{" "}
                {money(result.plan.maximum_loss)} · {result.plan.margin_source}
              </p>
              <p>
                Short quote {ist(result.plan.short_quote_at)} · hedge quote{" "}
                {ist(result.plan.hedge_quote_at)}. Values are paper estimates
                before fees.
              </p>
            </>
          )}
          {result.attempts?.map((a, i) => (
            <p key={i}>
              {a.short_symbol ?? "Short unavailable"} /{" "}
              {a.hedge_symbol ?? "Hedge unavailable"}: {a.reason}
            </p>
          ))}
          {!!result.candidates?.length && (
            <p>
              Candidate contracts:{" "}
              {result.candidates.map((c) => c.symbol).join(", ")}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
