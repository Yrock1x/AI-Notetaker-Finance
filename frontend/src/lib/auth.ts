import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

let supabase: SupabaseClient | null = null;

function getSupabase(): SupabaseClient | null {
  if (!supabaseUrl || !supabaseAnonKey) return null;
  if (!supabase) {
    supabase = createClient(supabaseUrl, supabaseAnonKey);
  }
  return supabase;
}

export { getSupabase };

export async function signIn(
  email: string,
  password: string
): Promise<{ error: string | null }> {
  const client = getSupabase();
  if (!client) {
    console.warn("Supabase not configured: signIn() is a no-op");
    return { error: "Auth not configured" };
  }

  const { error } = await client.auth.signInWithPassword({ email, password });
  return { error: error?.message ?? null };
}

export async function signInWithOAuth(
  provider: "google" | "github" | "azure"
): Promise<void> {
  const client = getSupabase();
  if (!client) {
    console.warn("Supabase not configured: signInWithOAuth() is a no-op");
    return;
  }

  await client.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo: `${window.location.origin}/callback`,
    },
  });
}

export async function signOut(): Promise<void> {
  const client = getSupabase();
  if (client) {
    await client.auth.signOut();
  }
  if (typeof window !== "undefined") {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("org_id");
  }
}

export async function getAccessToken(): Promise<string | null> {
  const client = getSupabase();
  if (client) {
    const {
      data: { session },
    } = await client.auth.getSession();
    return session?.access_token ?? null;
  }
  // Fallback: read from localStorage (demo mode)
  if (typeof window !== "undefined") {
    return localStorage.getItem("access_token");
  }
  return null;
}

export async function signUp(
  email: string,
  password: string,
  fullName: string
): Promise<{ error: string | null }> {
  const client = getSupabase();
  if (!client) {
    return { error: "Auth not configured" };
  }

  const { error } = await client.auth.signUp({
    email,
    password,
    options: {
      data: { full_name: fullName },
    },
  });
  return { error: error?.message ?? null };
}
