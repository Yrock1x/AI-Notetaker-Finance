// OAuth callback — Supabase redirects here after the Hosted UI consent.
// We exchange the ?code=... for a session cookie and redirect to ?next=...
// The session is written as httpOnly cookies by @supabase/ssr, so no client
// JS ever touches a refresh token.

import { NextResponse, type NextRequest } from "next/server";
import { getServerSupabase } from "@/lib/supabase/server";

const FALLBACK_NEXT = "/dashboard";

// Block open-redirect via ?next=. WHATWG `new URL(next, origin)` returns the
// absolute URL when `next` is absolute — `origin` is ignored. We must accept
// only same-site relative paths: must start with `/`, must not start with
// `//` (protocol-relative) or `/\` (backslash variant browsers normalise),
// and must not embed control characters that proxies may strip-then-rewrite.
function safeNextPath(raw: string | null): string {
  if (!raw) return FALLBACK_NEXT;
  if (!raw.startsWith("/")) return FALLBACK_NEXT;
  if (raw.startsWith("//") || raw.startsWith("/\\")) return FALLBACK_NEXT;
  // eslint-disable-next-line no-control-regex
  if (/[\x00-\x1f\x7f]/.test(raw)) return FALLBACK_NEXT;
  return raw;
}

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const next = safeNextPath(url.searchParams.get("next"));
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
