import type { NextConfig } from "next";

const backendUrl =
  process.env.API_BACKEND_URL || "http://localhost:8000";

// Full Content-Security-Policy. Shipped in Report-Only mode: browsers log
// violations to the console (and to report-uri if configured) but don't
// block — so we can tune the policy from real-world usage before flipping
// to enforced. Switch to "Content-Security-Policy" once the console is
// quiet for a week of normal usage.
//
// Tightening notes:
//  - script-src needs 'unsafe-inline' because Next.js emits inline hydration
//    scripts. Replace with per-request nonces (middleware-injected) when
//    we want to drop 'unsafe-inline'.
//  - 'unsafe-eval' is required by Next dev HMR and a few client libs that
//    use eval for JSON parsing. Most apps tolerate this.
//  - img-src is intentionally permissive (https:) because the landing page
//    pulls Unsplash photos and Supabase Storage signed URLs are arbitrary
//    https hosts in practice.
//  - connect-src includes Sentry origins forward-looking; @sentry/nextjs
//    isn't installed today (frontend/src/lib/sentry.ts is a guarded no-op)
//    but installing it later shouldn't require a CSP change.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' data: https://fonts.gstatic.com",
  "img-src 'self' data: blob: https:",
  "connect-src 'self' https://*.supabase.co wss://*.supabase.co https://*.railway.app https://*.sentry.io https://*.ingest.sentry.io",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const securityHeaders = [
  // Block the app from being framed anywhere — no legitimate embed use case.
  { key: "X-Frame-Options", value: "DENY" },
  // Enforced CSP: only the framing directive. The full policy ships
  // Report-Only below until we've tuned it from violation reports.
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
  // Full CSP in Report-Only mode for tuning. Promote to enforced
  // (Content-Security-Policy header) once console is clean.
  { key: "Content-Security-Policy-Report-Only", value: csp },
  // Stop browsers from MIME-sniffing — particularly important for files
  // served from Supabase Storage via signed URLs we redirect to.
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Trim the Referer header on cross-origin nav so deal IDs / paths don't
  // leak to third parties (analytics, embedded iframes, OAuth bounces).
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Force HTTPS for a year and pre-load. Vercel terminates TLS so this is
  // safe in prod; in local dev browsers ignore HSTS over http.
  {
    key: "Strict-Transport-Security",
    value: "max-age=31536000; includeSubDomains; preload",
  },
  // Lock down browser features the app doesn't use. Recall.ai bots run
  // server-side, so we never need camera/microphone/geolocation in the
  // first-party origin.
  {
    key: "Permissions-Policy",
    value: [
      "camera=()",
      "microphone=()",
      "geolocation=()",
      "payment=()",
      "usb=()",
      "interest-cohort=()",
    ].join(", "),
  },
];

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
