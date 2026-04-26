import type { NextConfig } from "next";

const backendUrl =
  process.env.API_BACKEND_URL || "http://localhost:8000";

// Conservative security headers. CSP intentionally NOT set yet — Next.js +
// Tailwind + Supabase + Sentry need a tuned policy and a misconfigured CSP
// breaks every page. Adding CSP is a tracked P2 follow-up that needs
// staging-mode tuning + Report-Only rollout.
const securityHeaders = [
  // Block the app from being framed anywhere — no legitimate embed use case.
  { key: "X-Frame-Options", value: "DENY" },
  // Reinforces X-Frame-Options for browsers that honour CSP frame-ancestors;
  // the rest of the CSP comes later.
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
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
