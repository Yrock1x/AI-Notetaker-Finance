// Thin server-side relay for sending Inngest events from client code.
// The client can't hold an INNGEST_EVENT_KEY — so the browser posts here,
// we verify the caller is authenticated AND owns the referenced rows,
// and then we forward to Inngest.
//
// Ownership checks now go through the worker REST API instead of a direct
// Supabase RLS read: we forward the caller's `cogni_session` cookie to the
// worker and GET the referenced resource. The worker enforces org scoping, so
// a 2xx is the membership proof and a non-2xx (401/403/404) means the caller
// can't touch that row. Without these checks any logged-in user could fire
// pipeline events targeting another tenant's meetings/documents/sessions.

import { NextResponse, type NextRequest } from "next/server";
import { inngest } from "@/lib/inngest/client";

const WORKER_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
const API_BASE = `${WORKER_URL}/api/v1`;

// Events the BROWSER fires through this relay. bot/scheduled + bot/cancelled
// are NOT here: scheduling/cancelling now goes through the worker REST API
// (use-bot-sessions), and those events are produced server-side (cron fanout +
// worker). The on-demand calendar refresh and bot auto-schedule nudges DO come
// from the client and must be allowlisted or they silently 400.
type AllowedEventName =
  | "meeting/uploaded"
  | "document/uploaded"
  | "calendar/refresh.requested"
  | "bot/auto-schedule.requested";

const ALLOWED_EVENTS: ReadonlySet<AllowedEventName> = new Set<AllowedEventName>([
  "meeting/uploaded",
  "document/uploaded",
  "calendar/refresh.requested",
  "bot/auto-schedule.requested",
]);

function isUuid(v: unknown): v is string {
  return typeof v === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
}

// GET a worker resource using the caller's session cookie. Returns the HTTP
// status so the caller can distinguish "exists & authorized" (2xx) from
// "forbidden / not found" (4xx). Network/worker errors surface as 502.
async function workerGet(path: string, cookie: string): Promise<number> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "GET",
      headers: { Accept: "application/json", cookie },
      // Server-to-server: don't follow redirects to login pages, etc.
      redirect: "manual",
      cache: "no-store",
    });
    return res.status;
  } catch {
    return 502;
  }
}

async function authorizeEvent(
  cookie: string,
  name: AllowedEventName,
  data: Record<string, unknown>,
  userId: string | undefined
): Promise<{ ok: true } | { ok: false; status: number; error: string }> {
  switch (name) {
    case "meeting/uploaded": {
      const meetingId = data.meeting_id;
      if (!isUuid(meetingId)) {
        return { ok: false, status: 400, error: "meeting_id required" };
      }
      const status = await workerGet(`/meetings/${meetingId}`, cookie);
      if (status < 200 || status >= 300) {
        return { ok: false, status: 403, error: "meeting not accessible" };
      }
      return { ok: true };
    }
    case "document/uploaded": {
      const documentId = data.document_id;
      if (!isUuid(documentId)) {
        return { ok: false, status: 400, error: "document_id required" };
      }
      const status = await workerGet(`/documents/${documentId}`, cookie);
      if (status < 200 || status >= 300) {
        return { ok: false, status: 403, error: "document not accessible" };
      }
      return { ok: true };
    }
    case "calendar/refresh.requested": {
      // refreshCalendarForUser re-scopes integrations to the invoking user
      // server-side; just confirm the event targets the session's own user.
      if (data.user_id !== userId) {
        return { ok: false, status: 403, error: "user_id mismatch" };
      }
      return { ok: true };
    }
    case "bot/auto-schedule.requested": {
      // Empty payload; the worker function is fully org-scoped via the
      // forwarded session cookie. A valid session (checked below) is enough.
      return { ok: true };
    }
  }
}

export async function POST(request: NextRequest) {
  // The worker session cookie travels with the browser's request to this
  // same-origin route; forward it verbatim to the worker for the auth +
  // ownership checks below.
  const cookie = request.headers.get("cookie") ?? "";
  if (!cookie) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Confirm the session is valid (and grab the user id for Inngest's user
  // attribution) before doing anything else.
  let userId: string | undefined;
  try {
    const res = await fetch(`${API_BASE}/auth/session`, {
      method: "GET",
      headers: { Accept: "application/json", cookie },
      redirect: "manual",
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    const session = (await res.json()) as { id?: string };
    userId = session.id;
  } catch {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: { name?: string; data?: Record<string, unknown> };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const name = body.name as AllowedEventName | undefined;
  if (!name || !ALLOWED_EVENTS.has(name)) {
    return NextResponse.json(
      { error: `Event '${body.name}' not allowed from client` },
      { status: 400 }
    );
  }

  const data = body.data ?? {};
  const decision = await authorizeEvent(cookie, name, data, userId);
  if (!decision.ok) {
    return NextResponse.json({ error: decision.error }, { status: decision.status });
  }

  // The event-name union is narrowed by ALLOWED_EVENTS above, and inngest.send's
  // overload resolution needs a literal for the `data` shape — cast through
  // `never` to let the runtime validator do its work.
  await inngest.send({
    name,
    data: data as never,
    ...(userId ? { user: { external_id: userId } } : {}),
  });

  return NextResponse.json({ ok: true });
}
