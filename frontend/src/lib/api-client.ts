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
apiClient.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };
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
    return Promise.reject(error);
  }
);

export default apiClient;
