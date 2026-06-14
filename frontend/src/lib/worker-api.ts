"use client";

// Typed HTTP helpers for the worker REST API. Replaces the former
// direct-to-Supabase queries. Auth is the worker's httpOnly session cookie
// (`cogni_session`), so every request sends `credentials: "include"` — there
// is NO Authorization header / bearer token anymore.
//
// Base URL is `${NEXT_PUBLIC_API_URL}/api/v1`. On a non-2xx response we throw
// an ApiError carrying the status + parsed body so React Query surfaces it.

const workerUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";
export const API_BASE = workerUrl ? `${workerUrl}/api/v1` : "/api/v1";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

// Thrown specifically on 404 so callers can treat "not found yet" as null
// (e.g. a transcript that hasn't been produced) without re-checking
// `e.status === 404` in every hook.
export class NotFoundError extends ApiError {
  constructor(message: string, body: unknown) {
    super(404, message, body);
    this.name = "NotFoundError";
  }
}

// Thrown when no response arrived at all (connection refused, dropped TCP,
// timeout) — after the one automatic retry below. Distinct from ApiError so
// callers can tell "the worker said no" from "the worker isn't reachable".
export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

// 60s ceiling so a hung connection (cold start, dropped TCP) surfaces as a
// real error instead of a silent forever-spinner. QA is the longest
// legitimate request (~15-25s) so 60s is plenty of headroom.
const REQUEST_TIMEOUT_MS = 60_000;
// When no response was received (cold start, transient TCP blip, brief CORS
// preflight failure), retry once after a short pause.
const NETWORK_RETRY_DELAY_MS = 800;

type QueryValue = string | number | boolean | null | undefined;

// Build a `?a=1&b=2` string, skipping null/undefined/"" values.
export function buildQuery(params?: Record<string, QueryValue>): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === "") continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  init?: RequestInit
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const doFetch = () =>
    fetch(`${API_BASE}${path}`, {
      method,
      credentials: "include",
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      ...init,
      signal: init?.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });

  let res: Response;
  try {
    res = await doFetch();
  } catch (e) {
    // A caller-supplied signal aborting is a deliberate cancellation — let it
    // propagate. Anything else means no response arrived; retry once.
    if (init?.signal?.aborted) throw e;
    await new Promise((r) => setTimeout(r, NETWORK_RETRY_DELAY_MS));
    try {
      res = await doFetch();
    } catch {
      throw new NetworkError(`${method} ${path}: worker unreachable`);
    }
  }

  // 401 → bounce to login so a dropped/expired cookie doesn't leave the user
  // staring at perpetual error toasts. Exempt the /auth/* endpoints: a 401
  // there is an expected, caller-handled outcome (the session probe returning
  // "not signed in", or a wrong password on /auth/login) — hard-redirecting
  // would clobber the login screen and swallow its error message.
  if (
    res.status === 401 &&
    typeof window !== "undefined" &&
    !path.startsWith("/auth/")
  ) {
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }

  if (!res.ok) {
    let parsed: unknown = null;
    let message = `${res.status} ${res.statusText}`;
    try {
      parsed = await res.json();
      const detail =
        parsed && typeof parsed === "object" && "detail" in parsed
          ? (parsed as { detail?: unknown }).detail
          : undefined;
      if (typeof detail === "string") message = detail;
    } catch {
      /* non-JSON body */
    }
    if (res.status === 404) throw new NotFoundError(message, parsed);
    throw new ApiError(res.status, message, parsed);
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>("GET", path, undefined, init);
}

export function apiPost<T>(
  path: string,
  body?: unknown,
  init?: RequestInit
): Promise<T> {
  return request<T>("POST", path, body, init);
}

export function apiPatch<T>(
  path: string,
  body?: unknown,
  init?: RequestInit
): Promise<T> {
  return request<T>("PATCH", path, body, init);
}

export function apiDelete<T>(
  path: string,
  body?: unknown,
  init?: RequestInit
): Promise<T> {
  return request<T>("DELETE", path, body, init);
}

// Best-effort warm-up: wakes a sleeping Railway container before the user
// submits anything expensive. Safe to call repeatedly; failures swallowed.
export function warmWorker(): void {
  if (typeof window === "undefined") return;
  fetch(`${API_BASE}/health`, { credentials: "include" }).catch(() => {
    /* swallow — warm-up is best-effort */
  });
}
