// Auth is owned by the worker via an httpOnly `cogni_session` cookie set on the
// worker's domain (cognisuite-worker.fly.dev). The frontend runs on a DIFFERENT
// domain (*.vercel.app), so that cookie is NOT sent to Next.js
// middleware/SSR requests here — it only rides the client's credentialed
// fetches to the worker. Therefore route gating cannot happen in middleware;
// it's done client-side in the (app) layout's AuthGuard, which calls the
// worker's /auth/session. This middleware is intentionally a pass-through.

import { NextResponse, type NextRequest } from "next/server";

export function middleware(_request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
