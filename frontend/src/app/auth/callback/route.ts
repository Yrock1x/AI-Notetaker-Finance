// OAuth callback — Supabase redirects here after the Hosted UI consent.
// We exchange the ?code=... for a session cookie and redirect to ?next=...
// The session is written as httpOnly cookies by @supabase/ssr, so no client
// JS ever touches a refresh token.

import { NextResponse, type NextRequest } from "next/server";
import { getServerSupabase } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const next = url.searchParams.get("next") || "/dashboard";
  const errorDescription = url.searchParams.get("error_description");

  if (errorDescription) {
    const login = new URL("/login", url.origin);
    login.searchParams.set("error", errorDescription);
    return NextResponse.redirect(login);
  }

  if (!code) {
    const login = new URL("/login", url.origin);
    login.searchParams.set("error", "Missing authorization code");
    return NextResponse.redirect(login);
  }

  const supabase = await getServerSupabase();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    const login = new URL("/login", url.origin);
    login.searchParams.set("error", error.message);
    return NextResponse.redirect(login);
  }

  return NextResponse.redirect(new URL(next, url.origin));
}
