/** Framework-independent frontend contract integration. No UI or trading activation. */
import type { components, paths } from "../../../docs/api/api-v1";

type GetPath = {
  [P in keyof paths]: paths[P] extends { get: unknown } ? P : never;
}[keyof paths];
type PostPath = {
  [P in keyof paths]: paths[P] extends { post: unknown } ? P : never;
}[keyof paths];
type PutPath = {
  [P in keyof paths]: paths[P] extends { put: unknown } ? P : never;
}[keyof paths];
type Op<P extends keyof paths, M extends PropertyKey> = M extends keyof paths[P]
  ? NonNullable<paths[P][M]>
  : never;
type Result<O> = O extends {
  responses: { 200: { content: { "application/json": infer R } } };
}
  ? R
  : never;
type Body<O> = O extends {
  requestBody: { content: { "application/json": infer B } };
}
  ? B
  : Record<string, never>;
type Query<O> = O extends { parameters: { query?: infer Q } } ? Q : never;
type Options = { params?: Record<string, string>; signal?: AbortSignal };
type MutateOptions = Options & { key: string };
export type Frame = components["schemas"]["WebSocketMessage"];
export type Snapshot = components["schemas"]["LiveSnapshot"];
export type Event = components["schemas"]["LiveEvent"];

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly requestId: string | null,
    message: string,
    public readonly details: components["schemas"]["ErrorDetail"][] = [],
  ) {
    super(message);
  }
}

export class ApiClient {
  private csrf: string | null = null;
  constructor(
    private readonly base = "",
    private readonly transport: typeof fetch = (...args) =>
      globalThis.fetch(...args),
  ) {}

  private url(
    path: string,
    params?: Record<string, string>,
    query?: object,
  ): string {
    for (const [name, value] of Object.entries(params ?? {})) {
      path = path.replace(`{${name}}`, encodeURIComponent(value));
    }
    if (path.includes("{")) throw new Error("Missing route parameter");
    const url = new URL(path, this.base || globalThis.location.origin);
    for (const [name, value] of Object.entries(query ?? {})) {
      if (value !== undefined && value !== null)
        url.searchParams.set(name, String(value));
    }
    return url.toString();
  }

  private async request(
    path: string,
    method: string,
    body: unknown,
    options: Options,
    key?: string,
    query?: object,
    login = false,
  ): Promise<Response> {
    const headers = new Headers();
    if (body !== undefined) headers.set("Content-Type", "application/json");
    if (method !== "GET" && !login) {
      if (!this.csrf)
        throw new ApiError(
          401,
          "authentication_required",
          null,
          "Sign in first",
        );
      headers.set("X-CSRF-Token", this.csrf);
      if (!key) throw new Error("Keep one idempotency key per intended action");
      headers.set("Idempotency-Key", key);
    }
    const response = await this.transport(
      this.url(path, options.params, query),
      {
        method,
        headers,
        credentials: "same-origin",
        signal: options.signal,
        body: body === undefined ? undefined : JSON.stringify(body),
      },
    );
    if (!response.ok) {
      if (response.status === 401) this.csrf = null;
      let envelope: components["schemas"]["ErrorEnvelope"] | undefined;
      try {
        envelope = await response.json();
      } catch {
        /* no proxy HTML or secrets in errors */
      }
      throw new ApiError(
        response.status,
        envelope?.error.code ?? "http_error",
        response.headers.get("X-Request-ID"),
        envelope?.error.message ?? "Request failed",
        envelope?.error.details ?? [],
      );
    }
    const token = response.headers.get("X-CSRF-Token");
    if (token) this.csrf = token;
    return response;
  }

  async login(
    password: string,
  ): Promise<Result<Op<"/api/auth/dashboard/login", "post">>> {
    const response = await this.request(
      "/api/auth/dashboard/login",
      "POST",
      { password },
      {},
      undefined,
      undefined,
      true,
    );
    return response.json();
  }

  async session(): Promise<Result<Op<"/api/auth/dashboard/status", "get">>> {
    const status = await this.get("/api/auth/dashboard/status");
    if (!status.authenticated) this.csrf = null;
    return status;
  }

  async logout(key: string): Promise<void> {
    await this.request("/api/auth/dashboard/logout", "POST", {}, {}, key);
    this.csrf = null;
  }

  async get<P extends GetPath>(
    path: P,
    query?: Query<Op<P, "get">>,
    options: Options = {},
  ): Promise<Result<Op<P, "get">>> {
    const response = await this.request(
      path,
      "GET",
      undefined,
      options,
      undefined,
      query as object | undefined,
    );
    return response.json();
  }

  async post<P extends PostPath>(
    path: P,
    body: Body<Op<P, "post">>,
    options: MutateOptions,
  ): Promise<Result<Op<P, "post">>> {
    const response = await this.request(
      path,
      "POST",
      body,
      options,
      options.key,
    );
    return response.json();
  }

  async put<P extends PutPath>(
    path: P,
    body: Body<Op<P, "put">>,
    options: MutateOptions,
  ): Promise<Result<Op<P, "put">>> {
    const response = await this.request(
      path,
      "PUT",
      body,
      options,
      options.key,
    );
    return response.json();
  }

  async exportTrades(
    query?: Query<Op<"/api/trades", "get">>,
    signal?: AbortSignal,
  ): Promise<string> {
    return (
      await this.request(
        "/api/trades/export",
        "GET",
        undefined,
        { signal },
        undefined,
        query,
      )
    ).text();
  }

  liveUrl(cursor: LiveCursor): string {
    const url = new URL("/ws/live", this.base || globalThis.location.origin);
    if (url.protocol !== "https:")
      throw new Error("Use the local HTTPS/WSS proxy");
    url.protocol = "wss:";
    if (cursor.run !== null) {
      url.searchParams.set("run_id", cursor.run);
      url.searchParams.set("after", String(cursor.sequence));
    }
    return url.toString();
  }
}

/** Reconnect with this cursor; on resync_required fetch a fresh snapshot first.
 * Never advance on a heartbeat or apply a partial/gapped event batch.
 */
export class LiveCursor {
  run: string | null = null;
  sequence = 0;
  snapshot: Snapshot | null = null;

  reset(snapshot: Snapshot): void {
    this.run = snapshot.run_id;
    this.sequence = snapshot.sequence;
    this.snapshot = snapshot;
  }

  accept(frame: Frame): { resync: boolean; events: Event[] } {
    if (frame.type === "snapshot") {
      this.reset(frame.snapshot);
      return { resync: false, events: [] };
    }
    if (frame.type === "resync_required" || frame.run_id !== this.run)
      return { resync: true, events: [] };
    if (frame.type === "heartbeat") return { resync: false, events: [] };
    let next = this.sequence;
    const events: Event[] = [];
    for (const event of frame.events) {
      if (event.run_id !== this.run || !Number.isSafeInteger(event.sequence))
        return { resync: true, events: [] };
      if (event.sequence <= next) continue;
      if (event.sequence !== next + 1) return { resync: true, events: [] };
      next = event.sequence;
      events.push(event);
    }
    if (next !== frame.sequence) return { resync: true, events: [] };
    this.sequence = next;
    return { resync: false, events };
  }
}
