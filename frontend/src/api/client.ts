// Typed fetch wrapper for the FastAPI backend. Errors follow the server format:
// { "error": { "code", "message", "fields", "request_id" } }

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string>;
  readonly requestId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    fields: Record<string, string> = {},
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.requestId = requestId;
  }
}

type ErrorBody = {
  error?: { code?: unknown; message?: unknown; fields?: unknown; request_id?: unknown };
};

function isStringRecord(value: unknown): value is Record<string, string> {
  return (
    typeof value === "object" &&
    value !== null &&
    Object.values(value as Record<string, unknown>).every((v) => typeof v === "string")
  );
}

export async function toApiError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-ID");
  let body: ErrorBody | null = null;
  try {
    body = (await response.json()) as ErrorBody;
  } catch {
    body = null;
  }
  const err = body?.error;
  if (err && typeof err.code === "string" && typeof err.message === "string") {
    return new ApiError(
      response.status,
      err.code,
      err.message,
      isStringRecord(err.fields) ? err.fields : {},
      typeof err.request_id === "string" ? err.request_id : requestId,
    );
  }
  return new ApiError(response.status, "http_error", `Request failed (${response.status})`, {}, requestId);
}

export type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  /** HTTP statuses that should resolve (with the parsed body) instead of throwing. */
  acceptStatuses?: number[];
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, acceptStatuses = [] } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
      signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, "network_error", "Cannot reach the server. Check your connection.");
  }

  if (!response.ok && !acceptStatuses.includes(response.status)) {
    throw await toApiError(response);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
