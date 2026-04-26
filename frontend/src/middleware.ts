// Runs on every request (except statics/images). Refreshes the Supabase
// session cookie and redirects unauthenticated traffic to /login.

import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { updateSupabaseSession } from "@/lib/supabase/middleware";

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

export async function middleware(request: NextRequest) {
  const response = await updateSupabaseSession(request);

  const { pathname } = request.nextUrl;
  // Exact-match `/`, prefix-match for everything else.
  const isPublic =
    pathname === "/" ||
    PUBLIC_PATHS.filter((p) => p !== "/").some((p) => pathname.startsWith(p));
  if (isPublic) {
    return response;
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anon) return response;

  const supabase = createServerClient(url, anon, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll() {
        // Writes handled by updateSupabaseSession above.
      },
    },
  });
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return response;
}

export const config = {
  matcher: [
    // Skip Next internals + static files.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
