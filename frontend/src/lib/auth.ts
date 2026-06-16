"use client";

// Auth helpers over the worker REST API. Auth state lives in the worker's
// httpOnly `cogni_session` cookie. OAuth sign-in is a full-page navigation to
// the worker, which performs the provider dance and sets the cookie before
// redirecting back.
//
// TODO: remove once all consumers migrated — src/lib/supabase/* is no longer
// used here.

import { API_BASE, apiPost } from "@/lib/worker-api";

// Map the app's provider labels to the worker's OAuth routes. The Microsoft
// login was historically labelled "azure" in the UI.
function providerSlug(provider: "google" | "azure" | "microsoft"): string {
  return provider === "azure" ? "microsoft" : provider;
}

export function signInWithOAuth(
  provider: "google" | "azure" | "microsoft",
  redirectPath = "/dashboard"
): void {
  if (typeof window === "undefined") return;
  const slug = providerSlug(provider);
  const next = encodeURIComponent(redirectPath);
  window.location.href = `${API_BASE}/auth/login/${slug}?next=${next}`;
}

// The worker's email/password endpoints return the session user and set the
// `cogni_session` cookie on the response. They're plain fetch() POSTs (unlike
// OAuth, which is a full-page navigation). A 401/409/403 surfaces as an
// ApiError the login form renders inline; worker-api exempts /auth/* from its
// global redirect-on-401 so the error reaches the caller.
export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
}

export function signInWithPassword(email: string, password: string): Promise<AuthUser> {
  return apiPost<AuthUser>("/auth/login", { email, password });
}

export function registerWithPassword(
  email: string,
  password: string,
  fullName?: string
): Promise<AuthUser> {
  return apiPost<AuthUser>("/auth/register", {
    email,
    password,
    full_name: fullName?.trim() || undefined,
  });
}

export async function signOut(): Promise<void> {
  try {
    await apiPost("/auth/signout");
  } catch {
    // Even if the call fails (network blip), drop local state and continue.
  }
  if (typeof window !== "undefined") {
    localStorage.removeItem("org_id");
  }
}
