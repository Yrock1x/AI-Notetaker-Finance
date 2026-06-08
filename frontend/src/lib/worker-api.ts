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

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: "include",
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...init,
  });

  // 401 → bounce to login so a dropped/expired cookie doesn't leave the user
  // staring at perpetual error toasts.
  if (res.status === 401 && typeof window !== "undefined") {
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
