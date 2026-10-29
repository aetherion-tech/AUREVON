import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useBeforeUnload, useBlocker } from "react-router-dom";
import { api, cache } from "./state";
import { ApiError } from "./api/client";
import { Card, Dialog, ErrorMessage } from "./ui";
import { DisplayPreferences } from "./preferences";
import { StrikePreview } from "./StrikePreview";
import {
  canonical,
  contract,
  dependency,
  getAt,
  importSettings,
  pendingSettings,
  resolve,
  setAt,
  settingsChanges,
  validateSettings,
  type Bundle,
  type Json,
  type PendingSettings,
  type Rule,
  type SettingsView,
} from "./settings-data";

function fieldHint(rule: Rule): string {
  return [
    rule.format === "time" ? "Local IST time, without timezone." : "",
    rule.gt !== undefined ? `Greater than ${rule.gt}.` : "",
    rule.ge !== undefined ? `At least ${rule.ge}.` : "",
    rule.le !== undefined ? `At most ${rule.le}.` : "",
    rule.minimum !== undefined ? `Minimum ${rule.minimum}.` : "",
    rule.maximum !== undefined ? `Maximum ${rule.maximum}.` : "",
    rule.decimal_places !== undefined
      ? `At most ${rule.decimal_places} decimal places.`
      : "",
  ]
    .filter(Boolean)
    .join(" ");
}
function objectDefault(input: Rule): Json {
  const rule = resolve(input);
  if (rule.default !== undefined && rule.default !== null)
    return structuredClone(rule.default);
  if (rule.type === "object")
    return Object.fromEntries(
      Object.entries(rule.properties ?? {}).map(([key, r]) => [
        key,
        objectDefault(r),
      ]),
    );
  if (rule.type === "boolean") return false;
  if (rule.type === "integer") return rule.minimum ?? 1;
  return "";
}
function SettingField({
  path,
  input,
  draft,
  edit,
  errors,
  defaults,
  label,
  help,
}: {
  path: string;
  input: Rule;
  draft: Json;
  edit: (path: string, value: Json) => void;
  errors: Record<string, string>;
  defaults: Json;
  label?: string;
  help?: string;
}) {
  const rule = resolve(input),
    value = getAt(draft, path),
    hint = `${help ?? ""} ${fieldHint(rule)}`.trim(),
    inactive = dependency(path, draft);
  if (rule.const !== undefined) return null;
  const title = label ?? rule.title ?? path;
  if (rule.anyOf) {
    const child = rule.anyOf.find((r) => r.type !== "null")!;
    return (
      <div className="setting-field">
        <label className="check">
          <input
            type="checkbox"
            checked={value !== null}
            onChange={(e) =>
              edit(path, e.target.checked ? objectDefault(child) : null)
            }
          />
          Use {title}
        </label>
        {value !== null && (
          <SettingField
            path={path}
            input={{ ...resolve(child), title }}
            draft={draft}
            edit={edit}
            errors={errors}
            defaults={defaults}
          />
        )}
        {path === "fills.cost_schedule" && (
          <small>
            Dated PAPER_ESTIMATE assumptions only; never measured broker fees.
            Disable legacy fee fields before saving a schedule.
          </small>
        )}
        {errors[path] && <p role="alert">{errors[path]}</p>}
      </div>
    );
  }
  if (rule.type === "object")
    return (
      <fieldset>
        <legend>{title}</legend>
        <div className="settings-fields">
          {Object.entries(rule.properties ?? {}).map(([key, r]) => (
            <SettingField
              key={key}
              path={`${path}.${key}`}
              input={r}
              draft={draft}
              edit={edit}
              errors={errors}
              defaults={defaults}
            />
          ))}
        </div>
      </fieldset>
    );
  const id = `setting-${path}`,
    error = errors[path];
  const described = `${id}-hint${error ? ` ${id}-error` : ""}`;
  const common = {
    id,
    "aria-describedby": described,
    "aria-invalid": !!error,
    disabled: !!inactive,
    title: hint,
  };
  const options = rule.enum;
  return (
    <div className="setting-field">
      {rule.type === "boolean" ? (
        <label className="check" htmlFor={id}>
          <input
            {...common}
            type="checkbox"
            checked={value === true}
            onChange={(e) => edit(path, e.target.checked)}
          />
          {title}
        </label>
      ) : rule.type === "array" ? (
        <fieldset
          id={id}
          tabIndex={-1}
          aria-describedby={described}
          aria-invalid={!!error}
        >
          <legend>{title}</legend>
          {rule.items?.enum?.map((option) => (
            <label className="check" key={String(option)}>
              <input
                type="checkbox"
                checked={Array.isArray(value) && value.includes(option)}
                onChange={(e) =>
                  edit(
                    path,
                    e.target.checked
                      ? [...(value as Json[]), option]
                      : (value as Json[]).filter((x) => x !== option),
                  )
                }
              />
              {String(option)}
            </label>
          ))}
        </fieldset>
      ) : (
        <>
          <label htmlFor={id}>{title}</label>
          {options ? (
            <select
              {...common}
              value={String(value ?? "")}
              onChange={(e) => edit(path, e.target.value)}
            >
              {options.map((option) => (
                <option key={String(option)} value={String(option)}>
                  {String(option)}
                </option>
              ))}
            </select>
          ) : (
            <input
              {...common}
              type={rule.format === "date" ? "date" : "text"}
              inputMode={
                rule.type === "integer"
                  ? "numeric"
                  : rule.gt !== undefined || rule.ge !== undefined
                    ? "decimal"
                    : undefined
              }
              value={
                typeof value === "string" || typeof value === "number"
                  ? value
                  : ""
              }
              onChange={(e) =>
                edit(
                  path,
                  rule.type === "integer" && /^-?\d+$/.test(e.target.value)
                    ? Number(e.target.value)
                    : e.target.value,
                )
              }
            />
          )}
        </>
      )}
      <small id={`${id}-hint`}>
        {hint} Default: {String(getAt(defaults, path) ?? "none")}.
        {inactive ? ` ${inactive}` : ""}
      </small>
      {error && (
        <p role="alert" id={`${id}-error`}>
          {error}
        </p>
      )}
    </div>
  );
}
function download(bundle: Bundle) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(bundle, null, 2) + "\n"], {
      type: "application/json",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "aurevon-settings-v1.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function SettingsEditor({
  initial,
  defaults,
  remote,
}: {
  initial: SettingsView;
  defaults: Bundle;
  remote: SettingsView;
}) {
  const [pending, setPending] = useState<PendingSettings | null>(() =>
    pendingSettings(),
  );
  const [base, setBase] = useState(initial);
  const [draft, setDraft] = useState<Json>(() =>
    structuredClone((pending?.body.settings ?? initial.settings) as Json),
  );
  const [error, setError] = useState<unknown>(),
    [serverFields, setServerFields] = useState<Record<string, string>>({}),
    [result, setResult] = useState("");
  const [review, setReview] = useState(false),
    [confirmed, setConfirmed] = useState(false),
    [rebuildAck, setRebuildAck] = useState(false),
    [busy, setBusy] = useState(false);
  const [importText, setImportText] = useState(""),
    [importError, setImportError] = useState("");
  const inFlight = useRef(false);
  const errors = { ...validateSettings(draft), ...serverFields };
  const dirty = canonical(draft) !== canonical(base.settings);
  const blocked = dirty || !!pending || busy;
  const blocker = useBlocker(blocked);
  useBeforeUnload((e) => {
    if (blocked) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
  const stale = remote.revision !== base.revision;
  const gridChanged =
    canonical(getAt(draft, "data")) !== canonical(base.settings.data) ||
    canonical(getAt(draft, "pine")) !== canonical(base.settings.pine);
  const changedSections = Object.keys(contract.schema.properties ?? {}).filter(
    (key) =>
      canonical(getAt(draft, key)) !==
      canonical((base.settings as unknown as Record<string, Json>)[key]),
  );
  function edit(path: string, value: Json) {
    setDraft((old) => setAt(old, path, value));
    setServerFields({});
    setResult("");
    setError(undefined);
  }
  function importDraft() {
    try {
      setDraft(importSettings(importText));
      setImportError("");
      setServerFields({});
      setResult("Imported into local edits. Review and save to persist.");
    } catch (err) {
      setImportError(
        err instanceof Error ? err.message : "Invalid settings JSON.",
      );
    }
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    if (
      inFlight.current ||
      (!pending &&
        (stale ||
          !dirty ||
          Object.keys(errors).length ||
          !confirmed ||
          (gridChanged && !rebuildAck)))
    )
      return;
    const request = pending ?? {
      key: crypto.randomUUID(),
      body: {
        expected_revision: base.revision,
        settings: structuredClone(draft) as Bundle,
        rebuild: gridChanged && rebuildAck,
      },
    };
    pendingSettings(request);
    setPending(request);
    inFlight.current = true;
    setBusy(true);
    setError(undefined);
    try {
      const view = await api.put("/api/settings", request.body, {
        key: request.key,
      });
      pendingSettings(null);
      setPending(null);
      setBase(view);
      setDraft(structuredClone(view.settings as Json));
      cache.setQueryData(["settings"], view);
      void cache.invalidateQueries({ queryKey: ["settings"] });
      void cache.invalidateQueries({ queryKey: ["wallet"] });
      setServerFields({});
      setReview(false);
      setConfirmed(false);
      setRebuildAck(false);
      setResult(
        `Saved revision ${view.revision}. ${view.requires_rebuild ? "Rebuild required; no rebuild has been started." : "No grid rebuild requested."} Activation: ${view.activation}. Saving does not change .env or enable paper entries.`,
      );
    } catch (err) {
      setError(err);
      if (err instanceof ApiError)
        setServerFields(
          Object.fromEntries(
            err.details.map((d) => [
              d.location
                .filter((x) => x !== "body" && x !== "settings")
                .join("."),
              d.message + ` (${d.code})`,
            ]),
          ),
        );
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  const groups = [...new Set(Object.values(contract.ui).map((u) => u.group))];
  return (
    <>
      <Card title="Versioned paper settings">
        <p>
          Desired revision {base.revision} · Activation: {remote.activation} ·{" "}
          {remote.requires_rebuild
            ? "Rebuild required"
            : "No pending grid rebuild reported"}
          .
        </p>
        <p>
          Saving records desired settings. The owner must stop safely, prepare
          any rebuild, rebind the matching version and reattach the runtime.
          This screen never starts a rebuild, restarts the feed or enables
          entries.
        </p>
        {stale && (
          <p role="alert">
            Server revision changed to {remote.revision}. Your edits are
            preserved. Review or discard them and reload the server version
            before a new save.
          </p>
        )}
        {result && <p role="status">{result}</p>}
        {error !== undefined && (
          <>
            <ErrorMessage error={error} />
            <p>
              For 409 conflicts, check the server revision, running feed,
              pending positions and rebuild acknowledgement. Retry keeps the
              original request; rejected keys keep their original outcome.
            </p>
          </>
        )}
        {pending && (
          <div className="notice">
            <p>
              A saved request needs review. Editing is frozen; retry preserves
              its amount-independent settings payload, revision and key,
              including after reload. Check the server version before
              discarding.
            </p>
            <button
              disabled={busy}
              onClick={(e) => void save(e as unknown as FormEvent)}
            >
              Retry same settings request
            </button>
            <button
              disabled={busy}
              onClick={() => {
                pendingSettings(null);
                setPending(null);
                setReview(false);
                setConfirmed(false);
                setRebuildAck(false);
                setError(undefined);
                setServerFields({});
              }}
            >
              I reviewed the server outcome; discard pending request
            </button>
          </div>
        )}
        <div className="history-actions">
          <strong>{dirty ? "Unsaved changes" : "No unsaved changes"}</strong>
          <button
            disabled={
              !!pending ||
              busy ||
              !dirty ||
              stale ||
              !!Object.keys(errors).length
            }
            onClick={() => {
              setReview(true);
              setConfirmed(false);
              setRebuildAck(false);
            }}
          >
            Review and save
          </button>
          <button
            disabled={!!pending || busy}
            onClick={() => {
              setBase(remote);
              setDraft(structuredClone(remote.settings as Json));
              setServerFields({});
              setError(undefined);
              setResult(
                "Loaded the current server version; local edits discarded.",
              );
            }}
          >
            Discard edits and load server
          </button>
          <button
            disabled={!!pending || busy}
            onClick={() => {
              setDraft(structuredClone(defaults as Json));
              setServerFields({});
              setResult("Defaults staged locally. Review and save to persist.");
            }}
          >
            Restore defaults locally
          </button>
          <button
            onClick={async () => {
              try {
                const data = await api.get("/api/settings/export");
                download(data);
              } catch (err) {
                setError(err);
              }
            }}
          >
            Export saved settings JSON
          </button>
        </div>
        {!!Object.keys(errors).length && (
          <div role="alert">
            <p>Correct these fields before saving:</p>
            <ul>
              {Object.entries(errors).map(([path, message]) => (
                <li key={path}>
                  <a
                    href={`#setting-${path}`}
                    onClick={() => {
                      const node = document.getElementById(`setting-${path}`);
                      node?.closest("details")?.setAttribute("open", "");
                      node?.focus();
                    }}
                  >
                    {path}: {message}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>
      <fieldset
        className="settings-editor"
        disabled={!!pending || busy}
        aria-busy={busy}
      >
        <legend>Local settings edits</legend>
        {groups.map((group) => (
          <details
            className="card settings-group"
            key={group}
            open={group === "Supertrend"}
          >
            <summary>{group}</summary>
            <div className="settings-fields">
              {Object.entries(contract.ui)
                .filter(([, u]) => u.group === group)
                .map(([name, ui]) => {
                  const r = contract.pine[name];
                  const rule: Rule = {
                    type:
                      r.kind === "bool"
                        ? "boolean"
                        : r.kind === "int"
                          ? "integer"
                          : "string",
                    minimum: r.minval,
                    maximum: r.maxval,
                    enum: r.options,
                  };
                  // Pine floats are numeric inputs; their draft may temporarily be an invalid string.
                  return (
                    <SettingField
                      key={name}
                      path={`pine.${name}`}
                      input={rule}
                      draft={draft}
                      edit={(path, v) =>
                        edit(
                          path,
                          r.kind === "float" &&
                            typeof v === "string" &&
                            /^-?\d+(\.\d+)?$/.test(v)
                            ? Number(v)
                            : v,
                        )
                      }
                      errors={errors}
                      defaults={defaults as Json}
                      label={ui.label}
                      help={ui.help}
                    />
                  );
                })}
            </div>
          </details>
        ))}
        {Object.entries(contract.schema.properties ?? {})
          .filter(([name]) => !["pine", "version"].includes(name))
          .map(([name, rule]) => (
            <details className="card settings-group" key={name}>
              <summary>
                {
                  (
                    {
                      strategy: "Strategy, sizing and strikes",
                      risk: "Risk and square-off",
                      fills: "Paper fills and cost assumptions",
                      wallet: "Wallet funding policy",
                      data: "Data and Renko grid",
                      display: "Saved display settings",
                    } as Record<string, string>
                  )[name]
                }
              </summary>
              {name === "data" && (
                <p>
                  Tick and minute-close are distinct streams. Changing grid,
                  anchor, lookback or Pine inputs requires rebuild
                  acknowledgement and separate owner work; no progress is
                  invented.
                </p>
              )}
              <SettingField
                path={name}
                input={rule}
                draft={draft}
                edit={edit}
                errors={errors}
                defaults={defaults as Json}
              />
            </details>
          ))}
        <Card title="Import settings JSON">
          <p>
            Import a complete version 1 export. Import validates locally and
            stages edits; it does not save or activate anything. Unknown fields
            and unsupported versions are rejected.
          </p>
          <label htmlFor="settings-file">Settings JSON file</label>
          <input
            id="settings-file"
            type="file"
            accept=".json,application/json"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              if (file.size > 200000) {
                setImportError("Settings file exceeds 200 KB.");
                return;
              }
              try {
                setImportText(await file.text());
              } catch {
                setImportError("Unable to read the selected file.");
              }
            }}
          />
          <label htmlFor="settings-json">Settings JSON</label>
          <textarea
            id="settings-json"
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            maxLength={200000}
            rows={7}
          />
          <button onClick={importDraft}>Validate and stage import</button>
          {importError && (
            <pre className="setup-command" role="alert">
              {importError}
            </pre>
          )}
        </Card>
      </fieldset>
      <DisplayPreferences />
      <StrikePreview
        key={`${remote.revision}:${dirty || !!pending}`}
        dirty={dirty || !!pending}
      />
      {review && !pending && (
        <Dialog
          title="Confirm paper settings change"
          close={() => setReview(false)}
          busy={busy}
        >
          <form onSubmit={(e) => void save(e)}>
            <p>
              Save revision {base.revision} → {base.revision + 1}. Changed
              groups: {changedSections.join(", ")}. Risk/funding/data changes
              may be rejected while the feed or positions are active. The server
              records the audit outcome.
            </p>
            <ul className="settings-change-review" aria-label="Changes to save">
              {settingsChanges(base.settings as Json, draft).map((change) => (
                <li key={change.path}>
                  <strong>{change.path}</strong>:{" "}
                  {JSON.stringify(change.before)} →{" "}
                  {JSON.stringify(change.after)}
                </li>
              ))}
            </ul>
            <label className="check">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              I confirm these paper settings changes
            </label>
            {gridChanged && (
              <label className="check">
                <input
                  type="checkbox"
                  checked={rebuildAck}
                  onChange={(e) => setRebuildAck(e.target.checked)}
                />
                I acknowledge a separate indicator/data rebuild is required
              </label>
            )}
            <button
              disabled={
                !confirmed || (gridChanged && !rebuildAck) || stale || busy
              }
            >
              Confirm save
            </button>
          </form>
        </Dialog>
      )}
      {blocker.state === "blocked" && (
        <Dialog title="Leave unsaved settings?" close={() => blocker.reset()}>
          <p>
            Local edits will be lost. Any pending request keeps its recovery key
            for your next visit.
          </p>
          <button onClick={() => blocker.reset()}>Keep editing</button>
          <button className="danger" onClick={() => blocker.proceed()}>
            Leave settings
          </button>
        </Dialog>
      )}
    </>
  );
}
export function SettingsPage() {
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: ({ signal }) => api.get("/api/settings", undefined, { signal }),
    refetchInterval: 15000,
  });
  const defaults = useQuery({
    queryKey: ["settings-defaults"],
    queryFn: ({ signal }) =>
      api.get("/api/settings/defaults", undefined, { signal }),
  });
  const schema = useQuery({
    queryKey: ["settings-schema"],
    queryFn: ({ signal }) =>
      api.get("/api/settings/schema", undefined, { signal }),
  });
  // The stable editor instance preserves edits when polling discovers a newer revision.
  const ready = settings.data && defaults.data && schema.data;
  const mismatch =
    schema.data &&
    canonical(schema.data.pine_inputs) !== canonical(contract.pine);
  useEffect(() => {
    document.title = "Settings | AUREVON paper desk";
    return () => {
      document.title = "AUREVON";
    };
  }, []);
  return (
    <>
      <div className="readiness">
        <div className="eyebrow">PAPER CONFIGURATION / VERSION 1</div>
        <h1>Settings</h1>
        <p>
          Review desired settings, then confirm changes. Original Pine defaults
          and source labels are preserved.
        </p>
      </div>
      {[settings, defaults, schema].map((q, i) =>
        q.error ? (
          <ErrorMessage
            key={i}
            error={q.error}
            retry={() => void q.refetch()}
          />
        ) : null,
      )}
      {!ready && ![settings, defaults, schema].some((q) => q.error) && (
        <p role="status">Loading settings and validation rules…</p>
      )}
      {mismatch && (
        <p role="alert">
          Server Pine rules differ from this build. Update the generated
          settings contract before editing.
        </p>
      )}
      {ready && !mismatch && (
        <SettingsEditor
          initial={settings.data!}
          remote={settings.data!}
          defaults={defaults.data!}
        />
      )}
    </>
  );
}
