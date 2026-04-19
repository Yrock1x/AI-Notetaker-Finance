import "server-only";

// Inngest orchestration. step.run blocks are small HTTP calls: either to the
// Python worker (Deepgram, LLM routing, docx rendering) or straight to
// Supabase via the service-role client for status updates.

import { createClient } from "@supabase/supabase-js";
import { inngest } from "./client";

const WORKER_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

function serviceSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    throw new Error(
      "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for Inngest functions"
    );
  }
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

// ---------------------------------------------------------------------------
// meeting/uploaded — the main post-meeting pipeline.
// transcribe -> diarize -> parallel(embed, analyze) -> notify
// ---------------------------------------------------------------------------
export const processMeeting = inngest.createFunction(
  { id: "process-meeting", concurrency: { limit: 4 } },
  { event: "meeting/uploaded" },
  async ({ event, step }) => {
    const { meeting_id } = event.data;
    const sb = serviceSupabase();

    await step.run("mark-transcribing", async () => {
      await sb
        .from("meetings")
        .update({ status: "transcribing" })
        .eq("id", meeting_id);
    });

    // Deepgram call lives on the Python worker — too much SDK ergonomics
    // to rewrite in TS. The worker writes the transcript row directly via
    // service-role client and returns the transcript id.
    const { transcript_id } = await step.run("deepgram-transcribe", async () => {
      const resp = await fetch(`${WORKER_URL}/api/v1/internal/transcribe`, {
        method: "POST",
        headers: internalHeaders(),
        body: JSON.stringify({ meeting_id }),
      });
      if (!resp.ok) throw new Error(`transcribe failed: ${resp.status}`);
      return (await resp.json()) as { transcript_id: string };
    });

    await step.run("mark-diarizing", async () => {
      await sb
        .from("meetings")
        .update({ status: "diarizing" })
        .eq("id", meeting_id);
    });

    // Diarization is part of Deepgram's response; the worker parses it in
    // the same endpoint above. This step is kept as a placeholder for
    // future providers that require a separate pass.
    await step.run("diarize", async () => ({ transcript_id }));

    // Parallel fan-out: embed + analyze.
    await step.run("mark-analyzing", async () => {
      await sb
        .from("meetings")
        .update({ status: "analyzing" })
        .eq("id", meeting_id);
    });

    await Promise.all([
      step.run("embed", async () => {
        const r = await fetch(`${WORKER_URL}/api/v1/internal/embed`, {
          method: "POST",
          headers: internalHeaders(),
          body: JSON.stringify({ meeting_id }),
        });
        if (!r.ok) throw new Error(`embed failed: ${r.status}`);
      }),
      step.run("analyze-summarization", async () => {
        const r = await fetch(`${WORKER_URL}/api/v1/internal/analyze`, {
          method: "POST",
          headers: internalHeaders(),
          body: JSON.stringify({ meeting_id, call_type: "summarization" }),
        });
        if (!r.ok) throw new Error(`analyze failed: ${r.status}`);
      }),
    ]);

    await step.run("mark-analyzed", async () => {
      await sb
        .from("meetings")
        .update({ status: "analyzed" })
        .eq("id", meeting_id);
    });

    return { meeting_id, status: "analyzed" };
  }
);

// ---------------------------------------------------------------------------
// document/uploaded — extract + embed.
// ---------------------------------------------------------------------------
export const processDocument = inngest.createFunction(
  { id: "process-document", concurrency: { limit: 4 } },
  { event: "document/uploaded" },
  async ({ event, step }) => {
    const { document_id } = event.data;
    await step.run("extract-and-embed", async () => {
      const r = await fetch(
        `${WORKER_URL}/api/v1/internal/process-document`,
        {
          method: "POST",
          headers: internalHeaders(),
          body: JSON.stringify({ document_id }),
        }
      );
      if (!r.ok) throw new Error(`process-document failed: ${r.status}`);
    });
    return { document_id };
  }
);

// ---------------------------------------------------------------------------
// bot/scheduled — ask Recall.ai to create a bot for the session.
// ---------------------------------------------------------------------------
export const startBotSession = inngest.createFunction(
  // Inngest free tier caps concurrency at 5 per function. Bump this if you
  // move to a paid plan and want bot starts to parallelise more aggressively.
  { id: "start-bot", concurrency: { limit: 5 } },
  { event: "bot/scheduled" },
  async ({ event, step }) => {
    const { session_id } = event.data;
    await step.run("create-recall-bot", async () => {
      const r = await fetch(`${WORKER_URL}/api/v1/internal/bot/start`, {
        method: "POST",
        headers: internalHeaders(),
        body: JSON.stringify({ session_id }),
      });
      if (!r.ok) throw new Error(`bot start failed: ${r.status}`);
    });
    return { session_id };
  }
);

// ---------------------------------------------------------------------------
// bot/cancelled — tell Recall.ai to kick the bot.
// ---------------------------------------------------------------------------
export const cancelBotSession = inngest.createFunction(
  { id: "cancel-bot" },
  { event: "bot/cancelled" },
  async ({ event, step }) => {
    const { session_id } = event.data;
    await step.run("stop-recall-bot", async () => {
      const r = await fetch(`${WORKER_URL}/api/v1/internal/bot/stop`, {
        method: "POST",
        headers: internalHeaders(),
        body: JSON.stringify({ session_id }),
      });
      if (!r.ok) throw new Error(`bot stop failed: ${r.status}`);
    });
    return { session_id };
  }
);

// ---------------------------------------------------------------------------
// teams/call_record.created — fetch the record via Graph API, log info.
// ---------------------------------------------------------------------------
export const processTeamsCallRecord = inngest.createFunction(
  { id: "process-teams-call-record", concurrency: { limit: 4 } },
  { event: "teams/call_record.created" },
  async ({ event, step }) => {
    const { call_record_id, tenant_id } = event.data;
    await step.run("fetch-and-log", async () => {
      const r = await fetch(
        `${WORKER_URL}/api/v1/internal/teams/ingest-call-record`,
        {
          method: "POST",
          headers: internalHeaders(),
          body: JSON.stringify({ call_record_id, tenant_id }),
        }
      );
      if (!r.ok) throw new Error(`teams ingest failed: ${r.status}`);
    });
    return { call_record_id };
  }
);

// ---------------------------------------------------------------------------
// zoom/recording.completed — download + enqueue meeting/uploaded.
// ---------------------------------------------------------------------------
export const ingestZoomRecording = inngest.createFunction(
  { id: "ingest-zoom-recording" },
  { event: "zoom/recording.completed" },
  async ({ event, step }) => {
    const { zoom_meeting_id, download_url } = event.data;
    const meeting_id = await step.run("download-and-store", async () => {
      const r = await fetch(`${WORKER_URL}/api/v1/internal/zoom/ingest`, {
        method: "POST",
        headers: internalHeaders(),
        body: JSON.stringify({ zoom_meeting_id, download_url }),
      });
      if (!r.ok) throw new Error(`zoom ingest failed: ${r.status}`);
      return ((await r.json()) as { meeting_id: string }).meeting_id;
    });
    await step.sendEvent("meeting-uploaded", {
      name: "meeting/uploaded",
      data: { meeting_id, deal_id: "" },
    });
    return { meeting_id };
  }
);

function internalHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-Internal-Token": process.env.WORKER_INTERNAL_TOKEN || "",
  };
}

// ---------------------------------------------------------------------------
// calendar sync — cron fan-out + per-user sync
// ---------------------------------------------------------------------------

// Runs every 30 min; fans out one `calendar/sync.requested` event per active
// integration so each user's calendar gets pulled independently.
export const syncCalendars = inngest.createFunction(
  { id: "sync-calendars" },
  { cron: "TZ=UTC */30 * * * *" },
  async ({ step }) => {
    const integrations = await step.run("list-active-integrations", async () => {
      const r = await fetch(
        `${WORKER_URL}/api/v1/internal/calendar/list-active-integrations`,
        { headers: internalHeaders() }
      );
      if (!r.ok) throw new Error(`list-active-integrations failed: ${r.status}`);
      const body = (await r.json()) as {
        integrations: { org_id: string; user_id: string; platform: string }[];
      };
      return body.integrations;
    });

    if (integrations.length === 0) return { integrations: 0 };

    await step.sendEvent(
      "fan-out-calendar-sync",
      integrations.map((i) => ({
        name: "calendar/sync.requested",
        data: i,
      }))
    );

    return { integrations: integrations.length };
  }
);

export const syncCalendarForUser = inngest.createFunction(
  { id: "sync-calendar-for-user", concurrency: { limit: 4 } },
  { event: "calendar/sync.requested" },
  async ({ event, step }) => {
    const { org_id, user_id, platform } = event.data as {
      org_id: string;
      user_id: string;
      platform: string;
    };
    const result = await step.run("worker-sync", async () => {
      const r = await fetch(`${WORKER_URL}/api/v1/internal/calendar/sync`, {
        method: "POST",
        headers: internalHeaders(),
        body: JSON.stringify({ org_id, user_id, platform }),
      });
      if (!r.ok) throw new Error(`calendar sync failed: ${r.status}`);
      return (await r.json()) as {
        events_seen: number;
        meetings_upserted: number;
      };
    });
    return { platform, user_id, ...result };
  }
);

// ---------------------------------------------------------------------------
// Microsoft Graph subscription renewal — runs every 12h. For each active
// 'microsoft' integration, asks the worker to create or renew the callRecords
// subscription. Graph's max lifetime for that resource is ~2.9 days, so we
// renew well before the 24h-before-expiry cutoff the worker enforces.
// ---------------------------------------------------------------------------

export const renewMicrosoftSubscriptions = inngest.createFunction(
  { id: "renew-microsoft-subscriptions" },
  { cron: "TZ=UTC 0 */12 * * *" },
  async ({ step }) => {
    const integrations = await step.run("list-microsoft", async () => {
      const r = await fetch(
        `${WORKER_URL}/api/v1/internal/calendar/list-active-integrations`,
        { headers: internalHeaders() }
      );
      if (!r.ok) throw new Error(`list failed: ${r.status}`);
      const body = (await r.json()) as {
        integrations: { org_id: string; user_id: string; platform: string }[];
      };
      return body.integrations.filter((i) => i.platform === "microsoft");
    });

    if (integrations.length === 0) return { integrations: 0 };

    await step.sendEvent(
      "fan-out-renew",
      integrations.map((i) => ({
        name: "microsoft/subscription.ensure",
        data: { org_id: i.org_id, user_id: i.user_id },
      }))
    );
    return { integrations: integrations.length };
  }
);

export const ensureMicrosoftSubscription = inngest.createFunction(
  { id: "ensure-microsoft-subscription", concurrency: { limit: 4 } },
  { event: "microsoft/subscription.ensure" },
  async ({ event, step }) => {
    const { org_id, user_id } = event.data as {
      org_id: string;
      user_id: string;
    };
    const result = await step.run("worker-ensure", async () => {
      const r = await fetch(
        `${WORKER_URL}/api/v1/internal/microsoft/ensure-subscription`,
        {
          method: "POST",
          headers: internalHeaders(),
          body: JSON.stringify({ org_id, user_id }),
        }
      );
      if (!r.ok) throw new Error(`ensure failed: ${r.status}`);
      return (await r.json()) as {
        subscription_id: string;
        expiration: string;
        action: string;
      };
    });
    return { user_id, ...result };
  }
);

export const functions = [
  processMeeting,
  processDocument,
  startBotSession,
  cancelBotSession,
  ingestZoomRecording,
  processTeamsCallRecord,
  syncCalendars,
  syncCalendarForUser,
  renewMicrosoftSubscriptions,
  ensureMicrosoftSubscription,
];
