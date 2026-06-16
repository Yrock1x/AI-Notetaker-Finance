// OBSOLETE — OAuth now runs entirely through the worker:
//   GET ${NEXT_PUBLIC_API_URL}/api/v1/auth/login/<slug>  → provider consent
//   GET ${NEXT_PUBLIC_API_URL}/api/v1/auth/callback       → sets the httpOnly
//                                                            `cogni_session`
//                                                            cookie + redirects
//
// The browser never lands on this Next route anymore. We keep it as a thin
// safe redirect (rather than deleting it) so any stale provider/redirect-URI
// configuration still pointing at `/auth/callback` lands the user on the app
// instead of a 404. We forward `?next=` (open-redirect-guarded) and surface
// any `?error*` to the login page.

import { NextResponse, type NextRequest } from "next/server";

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
  const next = safeNextPath(url.searchParams.get("next"));
  const errorDescription =
    url.searchParams.get("error_description") || url.searchParams.get("error");

  if (errorDescription) {
    const login = new URL("/login", url.origin);
    login.searchParams.set("error", errorDescription);
    return NextResponse.redirect(login);
  }

  // No session exchange happens here anymore — the worker already set the
  // cookie. Just bounce to the requested destination (or the app home).
  return NextResponse.redirect(new URL(next, url.origin));
}
