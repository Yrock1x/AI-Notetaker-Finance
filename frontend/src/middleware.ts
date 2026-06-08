// Runs on every request (except statics/images). Gates authenticated routes
// on the worker's `cogni_session` cookie and redirects unauthenticated
// traffic to /login.
//
// Auth is now owned by the worker (httpOnly cookie); there is no Supabase
// session to refresh here anymore.

import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "cogni_session";

// Paths that don't require a session. Everything else gets redirected to
// /login. Root `/` is public because it renders the marketing landing page.
const PUBLIC_PATHS = [
  "/",
  "/login",
  "/auth/callback",
  "/api/inngest",
  "/cogniscribe",
  "/cognivault",
  "/landing-v1",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Exact-match `/`, prefix-match for everything else.
  const isPublic =
    pathname === "/" ||
    PUBLIC_PATHS.filter((p) => p !== "/").some((p) => pathname.startsWith(p));
  if (isPublic) {
    return NextResponse.next();
  }

  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);
  if (!hasSession) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Skip Next internals + static files.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
