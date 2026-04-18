// Inngest function definitions. Each function is the TypeScript port of
// one of the old Celery chains — except the heavy Python work (Deepgram
// SDK call, LLM routing, docx rendering) is still done by the FastAPI
// worker. Inngest is pure orchestration: step.run() blocks are tiny HTTP
// calls that either hit the worker or write to Supabase directly.
//
// Why not do it all in TypeScript? We'd lose the prompt library, guardrails
// module, and grounding checks that already work in Python. Keeping one
// HTTP hop lets us keep Python code that doesn't need to move.

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

// ---------------------------------------------------------------------------
// Scheduled: sync Outlook calendars every 15 min.
// ---------------------------------------------------------------------------
export const syncOutlookCalendars = inngest.createFunction(
  { id: "sync-outlook-calendars" },
  { cron: "*/15 * * * *" },
  async ({ step }) => {
    await step.run("fanout", async () => {
      const r = await fetch(
        `${WORKER_URL}/api/v1/internal/outlook/sync-all`,
        { method: "POST", headers: internalHeaders() }
      );
      if (!r.ok) throw new Error(`outlook sync failed: ${r.status}`);
    });
  }
);

function internalHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-Internal-Token": process.env.WORKER_INTERNAL_TOKEN || "",
  };
}

export const functions = [
  processMeeting,
  processDocument,
  startBotSession,
  cancelBotSession,
  ingestZoomRecording,
  processTeamsCallRecord,
  syncOutlookCalendars,
];
