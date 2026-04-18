// Optional Sentry init. No-op if NEXT_PUBLIC_SENTRY_DSN is unset or
// @sentry/nextjs isn't installed yet. Import @sentry/nextjs lazily so builds
// don't fail when the package is absent.

let initialized = false;

export async function initSentry(): Promise<void> {
  if (initialized) return;
  initialized = true;

  if (typeof window === "undefined") return;
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;

  try {
    // Dynamic import so the build doesn't fail if @sentry/nextjs isn't yet
    // installed. Kept as a variable expression (not a string literal) so
    // TypeScript and webpack don't try to resolve it at build time.
    const pkg = "@sentry/nextjs";
    const Sentry = (await import(/* webpackIgnore: true */ pkg)) as {
      init: (cfg: Record<string, unknown>) => void;
    };
    Sentry.init({
      dsn,
      environment: process.env.NODE_ENV,
      tracesSampleRate: 0.1,
    });
  } catch {
    // Package not installed or runtime error — skip silently.
  }
}
