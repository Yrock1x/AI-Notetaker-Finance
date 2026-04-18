"use client";

// Thin helpers over the Supabase browser client. All auth state lives in
// httpOnly cookies via @supabase/ssr — don't add any localStorage shims.

import { getBrowserSupabase } from "@/lib/supabase/browser";

export async function signInWithOAuth(
  provider: "google" | "azure",
  redirectPath = "/dashboard"
): Promise<void> {
  const supabase = getBrowserSupabase();
  await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(redirectPath)}`,
    },
  });
}

export async function signOut(): Promise<void> {
  const supabase = getBrowserSupabase();
  await supabase.auth.signOut();
  if (typeof window !== "undefined") {
    localStorage.removeItem("org_id");
  }
}

export async function getAccessToken(): Promise<string | null> {
  const supabase = getBrowserSupabase();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}
