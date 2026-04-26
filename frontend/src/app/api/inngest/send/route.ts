// Thin server-side relay for sending Inngest events from client code.
// The client can't hold an INNGEST_EVENT_KEY — so the browser posts here,
// we verify the caller is authenticated AND owns the referenced rows,
// and then we forward to Inngest.
//
// Ownership checks use the user-scoped Supabase client; RLS filters to
// only rows the caller can see, so a successful single-row read is itself
// the membership proof. Without these checks any logged-in user can fire
// pipeline events targeting another tenant's meetings/documents/sessions.

import { NextResponse, type NextRequest } from "next/server";
import type { SupabaseClient } from "@supabase/supabase-js";
import { inngest } from "@/lib/inngest/client";
import { getServerSupabase } from "@/lib/supabase/server";

type AllowedEventName =
  | "meeting/uploaded"
  | "document/uploaded"
  | "bot/scheduled"
  | "bot/cancelled";

const ALLOWED_EVENTS: ReadonlySet<AllowedEventName> = new Set<AllowedEventName>([
  "meeting/uploaded",
  "document/uploaded",
  "bot/scheduled",
  "bot/cancelled",
]);

function isUuid(v: unknown): v is string {
  return typeof v === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
}

async function rowExists(
  supabase: SupabaseClient,
  table: string,
  id: string
): Promise<boolean> {
  const { data, error } = await supabase
    .from(table)
    .select("id")
    .eq("id", id)
    .maybeSingle();
  if (error) return false;
  return data != null;
}

async function authorizeEvent(
  supabase: SupabaseClient,
  name: AllowedEventName,
  data: Record<string, unknown>
): Promise<{ ok: true } | { ok: false; status: number; error: string }> {
  switch (name) {
    case "meeting/uploaded": {
      const meetingId = data.meeting_id;
      if (!isUuid(meetingId)) {
        return { ok: false, status: 400, error: "meeting_id required" };
      }
      if (!(await rowExists(supabase, "meetings", meetingId))) {
        return { ok: false, status: 403, error: "meeting not accessible" };
      }
      return { ok: true };
    }
    case "document/uploaded": {
      const documentId = data.document_id;
      if (!isUuid(documentId)) {
        return { ok: false, status: 400, error: "document_id required" };
      }
      if (!(await rowExists(supabase, "documents", documentId))) {
        return { ok: false, status: 403, error: "document not accessible" };
      }
      return { ok: true };
    }
    case "bot/scheduled":
    case "bot/cancelled": {
      const sessionId = data.session_id;
      if (!isUuid(sessionId)) {
        return { ok: false, status: 400, error: "session_id required" };
      }
      if (!(await rowExists(supabase, "meeting_bot_sessions", sessionId))) {
        return { ok: false, status: 403, error: "bot session not accessible" };
      }
      return { ok: true };
    }
  }
}

export async function POST(request: NextRequest) {
  const supabase = await getServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
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
  const decision = await authorizeEvent(supabase, name, data);
  if (!decision.ok) {
    return NextResponse.json({ error: decision.error }, { status: decision.status });
  }

  // The event-name union is narrowed by ALLOWED_EVENTS above, and inngest.send's
  // overload resolution needs a literal for the `data` shape — cast through
  // `never` to let the runtime validator do its work.
  await inngest.send({
    name,
    data: data as never,
    user: { external_id: user.id },
  });

  return NextResponse.json({ ok: true });
}
