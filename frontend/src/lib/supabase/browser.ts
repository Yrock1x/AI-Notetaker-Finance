"use client";

// TODO: remove once all consumers migrated — the data hooks + auth now use the
// worker REST API (src/lib/worker-api.ts). A few not-yet-migrated areas (qa,
// analysis, deliverables, admin, integrations) may still import this.
//
// Browser-side Supabase client. Safe to import from any Client Component.
// Uses httpOnly cookies via @supabase/ssr so the session is shared with
// Server Components + Route Handlers without any JS-accessible refresh token.

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

export function getBrowserSupabase(): SupabaseClient {
  if (client) return client;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anon) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set"
    );
  }
  client = createBrowserClient(url, anon);
  return client;
}
