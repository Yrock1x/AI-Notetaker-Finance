// Thin server-side relay for sending Inngest events from client code.
// The client can't hold an INNGEST_EVENT_KEY — so the browser posts here,
// we verify the caller is authenticated + that the event payload looks
// sane, and then we forward to Inngest.

import { NextResponse, type NextRequest } from "next/server";
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

  // The event-name union is narrowed by ALLOWED_EVENTS above, and inngest.send's
  // overload resolution needs a literal for the `data` shape — cast through
  // `never` to let the runtime validator do its work.
  await inngest.send({
    name,
    data: (body.data ?? {}) as never,
    user: { external_id: user.id },
  });

  return NextResponse.json({ ok: true });
}
