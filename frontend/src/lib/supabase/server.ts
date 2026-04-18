// Server-side Supabase client. Use from Server Components, Route Handlers,
// and Server Actions. Reads the session from the incoming request's cookies
// and writes any refresh-rotated tokens back via Next's async cookies API.

import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

export async function getServerSupabase(): Promise<SupabaseClient> {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anon) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set"
    );
  }

  const cookieStore = await cookies();
  return createServerClient(url, anon, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(
        newCookies: { name: string; value: string; options?: Record<string, unknown> }[]
      ) {
        try {
          newCookies.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        } catch {
          // setAll is a no-op in Server Components that are rendered without
          // a response — only Route Handlers + Server Actions can write.
        }
      },
    },
  });
}
