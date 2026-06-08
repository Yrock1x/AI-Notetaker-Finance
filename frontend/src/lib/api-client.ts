// Worker HTTP client (axios). Auth is now the worker's httpOnly session
// cookie (`cogni_session`) — we send it via `withCredentials: true` and no
// longer inject a Supabase bearer token.
//
// Most data hooks use the lighter fetch-based helpers in `worker-api.ts`.
// This axios instance remains for the synchronous LLM endpoints (Q&A,
// analysis, deliverables) and admin/integration calls that already depend on
// its retry + timeout behaviour.

import axios, { type AxiosRequestConfig } from "axios";

const workerUrl =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

const apiClient = axios.create({
  baseURL: workerUrl ? `${workerUrl}/api/v1` : "/api/v1",
  headers: { "Content-Type": "application/json" },
  // Send the session cookie cross-origin (worker is on a different domain).
  withCredentials: true,
  // 60s ceiling so a hung connection (Railway cold start, dropped TCP)
  // surfaces as a real error instead of a silent forever-spinner. QA is
  // the longest legitimate request (~15-25s) so 60s is plenty of headroom.
  timeout: 60_000,
});

// On 401, the cookie is gone or expired — bounce to login. (No client-side
// refresh: the worker owns the session cookie now.)
//
// On ERR_NETWORK / ECONNABORTED (no response received — Railway cold start,
// transient TCP blip, brief CORS preflight failure), retry once after 800ms.
apiClient.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config as AxiosRequestConfig & {
      _netRetry?: boolean;
    };
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    const isNetworkError =
      !error.response &&
      (error.code === "ERR_NETWORK" || error.code === "ECONNABORTED");
    if (isNetworkError && original && !original._netRetry) {
      original._netRetry = true;
      await new Promise((r) => setTimeout(r, 800));
      return apiClient(original);
    }
    return Promise.reject(error);
  }
);

// Best-effort warm-up: wakes a sleeping Railway container before the user
// submits anything expensive. Safe to call repeatedly; failures swallowed.
export function warmWorker(): void {
  if (typeof window === "undefined") return;
  apiClient.get("/health", { timeout: 5_000 }).catch(() => {
    /* swallow — warm-up is best-effort */
  });
}

export default apiClient;
