// Worker-only HTTP client. Used for the few endpoints that still require a
// Python-side secret (Fireworks/Claude/Deepgram keys, Supabase service role).
// Everything else in the app talks to Supabase directly via supabase-js.
//
// The Authorization header is the user's live Supabase access token, pulled
// from the browser client on every request so it's always fresh.

import axios, { type AxiosRequestConfig } from "axios";
import { getBrowserSupabase } from "@/lib/supabase/browser";

const workerUrl =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

const apiClient = axios.create({
  baseURL: workerUrl ? `${workerUrl}/api/v1` : "/api/v1",
  headers: { "Content-Type": "application/json" },
  // 60s ceiling so a hung connection (Railway cold start, dropped TCP)
  // surfaces as a real error instead of a silent forever-spinner. QA is
  // the longest legitimate request (~15-25s) so 60s is plenty of headroom.
  timeout: 60_000,
});

apiClient.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    const supabase = getBrowserSupabase();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  }
  return config;
});

// On 401, force a session refresh and retry once. Supabase's browser client
// handles actual refresh on its own; we just give it a nudge.
//
// On ERR_NETWORK (no response received — Railway cold start, transient TCP
// blip, brief CORS preflight failure), retry once after 800ms. A single
// retry is cheap and almost always resolves the issue without the user
// having to re-type their question.
apiClient.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config as AxiosRequestConfig & {
      _retry?: boolean;
      _netRetry?: boolean;
    };
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const supabase = getBrowserSupabase();
        const { data } = await supabase.auth.refreshSession();
        if (data.session?.access_token && original.headers) {
          original.headers.Authorization = `Bearer ${data.session.access_token}`;
          return apiClient(original);
        }
      } catch {
        // fall through
      }
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    const isNetworkError =
      !error.response &&
      (error.code === "ERR_NETWORK" || error.code === "ECONNABORTED");
    if (isNetworkError && !original._netRetry) {
      original._netRetry = true;
      await new Promise((r) => setTimeout(r, 800));
      return apiClient(original);
    }
    return Promise.reject(error);
  }
);

// Best-effort warm-up: fires a HEAD-style request to wake a sleeping
// Railway container before the user submits anything expensive. Safe to
// call repeatedly; failures are swallowed.
export function warmWorker(): void {
  if (typeof window === "undefined") return;
  apiClient.get("/health", { timeout: 5_000 }).catch(() => {
    /* swallow — warm-up is best-effort */
  });
}

export default apiClient;
