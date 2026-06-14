// Shared client helper for firing events through the same-origin Inngest relay
// (`/api/inngest/send`). The relay validates the event name against an allowlist
// and authorizes ownership, then forwards to Inngest.
//
// It THROWS on a non-2xx response so callers surface the failure (toast, retry,
// stuck-row recovery) instead of silently no-op'ing — a dropped event otherwise
// leaves a meeting/document stuck in its initial status while the UI reports
// success. `fetch` only rejects on network errors, never on HTTP 4xx/5xx, so the
// explicit `res.ok` check is required.

export async function sendInngestEvent(
  name: string,
  data: Record<string, unknown> = {}
): Promise<void> {
  const res = await fetch("/api/inngest/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, data }),
  });
  if (!res.ok) {
    let detail = `Inngest relay rejected '${name}' (HTTP ${res.status})`;
    try {
      const body = (await res.json()) as { error?: string };
      if (body?.error) detail = body.error;
    } catch {
      /* keep the default message */
    }
    throw new Error(detail);
  }
}
