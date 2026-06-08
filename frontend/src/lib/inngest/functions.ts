import "server-only";

// Inngest orchestration. step.run blocks are small HTTP calls to the Python
// worker (Deepgram, LLM routing, docx rendering, and meeting-status writes).
// All meeting-status updates now go through the worker's internal API instead
// of a direct service-role Supabase write, so this runtime no longer needs the
// Supabase service-role key.

import { inngest } from "./client";

const WORKER_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

// Push a meeting's pipeline status to the worker, which owns the DB write.
// Replaces the former `serviceSupabase().from("meetings").update(...)` calls.
//
// TODO(backend): add POST /api/v1/internal/meeting-status accepting
//   { meeting_id, status, error_message? } and authenticated by X-Internal-Token,
//   writing meetings.status (+ error_message). Until that endpoint ships these
//   calls will 404 and the surrounding step.run will retry — the status write is
//   NOT silently dropped.
async function setMeetingStatus(
  meetingId: string,
  status: string,
  errorMessage?: string
): Promise<void> {
  const r = await fetch(`${WORKER_URL}/api/v1/internal/meeting-status`, {
    method: "POST",
    headers: internalHeaders(),
    body: JSON.stringify({
      meeting_id: meetingId,
      status,
      error_message: errorMessage ?? null,
    }),
  });
  if (!r.ok) throw new Error(`meeting-status (${status}) failed: ${r.status}`);
}

// ---------------------------------------------------------------------------
// meeting/uploaded — the main post-meeting pipeline.
// transcribe -> diarize -> parallel(embed, analyze) -> notify
// ---------------------------------------------------------------------------
export const processMeeting = inngest.createFunction(
  // Concurrency: 20 lets a busy 5pm-end-of-day burst drain in <1 min instead
  // of queueing for 5+. Inngest free tier caps at 5 per function — this
  // limit is aspirational until the workspace is on a paid plan.
  { id: "process-meeting", concurrency: { limit: 20 } },
  { event: "meeting/uploaded" },
  async ({ event, step }) => {
    const { meeting_id } = event.data;

    await step.run("mark-transcribing", async () => {
      await setMeetingStatus(meeting_id, "transcribing");
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
      await setMeetingStatus(meeting_id, "diarizing");
    });

    // Diarization is part of Deepgram's response; the worker parses it in
    // the same endpoint above. This step is kept as a placeholder for
    // future providers that require a separate pass.
    await step.run("diarize", async () => ({ transcript_id }));

    // Parallel fan-out: embed + analyze.
    await step.run("mark-analyzing", async () => {
      await setMeetingStatus(meeting_id, "analyzing");
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
      await setMeetingStatus(meeting_id, "analyzed");
    });

    return { meeting_id, status: "analyzed" };
  }
);

// ---------------------------------------------------------------------------
// document/uploaded — extract + embed.
// ---------------------------------------------------------------------------
export const processDocument = inngest.createFunction(
  { id: "process-document", concurrency: { limit: 10 } },
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
  // Inngest free tier caps concurrency at 5 per function; the ceiling here
  // is aspirational for paid plans where 15 lets a burst of meetings
  // starting at the same minute spawn bots without queue lag.
  { id: "start-bot", concurrency: { limit: 15 } },
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
// auto-schedule-due-bots — every 5 min, ask the worker which synced
// meetings are about to start (next 10 min) with bot_enabled=true. For
// each, the worker has already pre-created a meeting_bot_sessions row; we
// just fan out a `bot/scheduled` event per session so the existing
// start-bot handler does the Recall call. Keeps bot launches a single
// code path regardless of whether the user scheduled manually or via
// auto-join.
// ---------------------------------------------------------------------------
// Cron trigger: sweeps every 5 min for meetings about to start.
// Fan-out is capped at 500 per tick to stay under Inngest's per-call event
// batch ceiling. Anything beyond that is picked up by the next 5-min run —
// a single user/org can't realistically have >500 meetings starting in the
// same 10-min window.
const AUTO_SCHEDULE_FANOUT_CAP = 500;

export const autoScheduleDueBots = inngest.createFunction(
  { id: "auto-schedule-due-bots" },
  { cron: "TZ=UTC */5 * * * *" },
  async ({ step }) => {
    const scheduled = await step.run("find-due", async () => {
      const r = await fetch(
        `${WORKER_URL}/api/v1/internal/bot/auto-schedule-due`,
        { method: "POST", headers: internalHeaders() }
      );
      if (!r.ok) throw new Error(`auto-schedule-due failed: ${r.status}`);
      const body = (await r.json()) as {
        scheduled: { session_id: string; meeting_id: string; deal_id: string }[];
      };
      return body.scheduled;
    });
    if (scheduled.length === 0) return { scheduled: 0 };
    const batch = scheduled.slice(0, AUTO_SCHEDULE_FANOUT_CAP);
    await step.sendEvent(
      "fanout-bot-scheduled",
      batch.map((s) => ({
        name: "bot/scheduled" as const,
        data: { session_id: s.session_id },
      }))
    );
    return {
      scheduled: batch.length,
      deferred: scheduled.length - batch.length,
    };
  }
);

// On-demand twin: fires the same logic immediately when a user assigns
// a calendar-synced meeting to a deal. Without this, the bot wouldn't
// spawn until the next 5-min cron tick — easy to miss a meeting that's
// about to start.
export const autoScheduleDueBotsOnDemand = inngest.createFunction(
  { id: "auto-schedule-due-bots-on-demand", concurrency: { limit: 4 } },
  { event: "bot/auto-schedule.requested" },
  async ({ step }) => {
    const scheduled = await step.run("find-due", async () => {
      const r = await fetch(
        `${WORKER_URL}/api/v1/internal/bot/auto-schedule-due`,
        { method: "POST", headers: internalHeaders() }
      );
      if (!r.ok) throw new Error(`auto-schedule-due failed: ${r.status}`);
      const body = (await r.json()) as {
        scheduled: { session_id: string; meeting_id: string; deal_id: string }[];
      };
      return body.scheduled;
    });
    if (scheduled.length === 0) return { scheduled: 0 };
    const batch = scheduled.slice(0, AUTO_SCHEDULE_FANOUT_CAP);
    await step.sendEvent(
      "fanout-bot-scheduled",
      batch.map((s) => ({
        name: "bot/scheduled" as const,
        data: { session_id: s.session_id },
      }))
    );
    return {
      scheduled: batch.length,
      deferred: scheduled.length - batch.length,
    };
  }
);

// ---------------------------------------------------------------------------
// meeting/bot-completed — post-call pipeline for bot-recorded meetings.
// Pulls transcript + participants from Recall's recording shortcuts (Deepgram
// ran during the call, so we skip /internal/transcribe), then runs embed +
// analyze using the existing workers.
// ---------------------------------------------------------------------------
export const processBotMeeting = inngest.createFunction(
  { id: "process-bot-meeting", concurrency: { limit: 4 } },
  { event: "meeting/bot-completed" },
  async ({ event, step }) => {
    const { session_id, meeting_id } = event.data;

    await step.run("finalize", async () => {
      const r = await fetch(`${WORKER_URL}/api/v1/internal/bot/finalize`, {
        method: "POST",
        headers: internalHeaders(),
        body: JSON.stringify({ session_id }),
      });
      if (!r.ok) throw new Error(`bot finalize failed: ${r.status}`);
    });

    await step.run("mark-analyzing", async () => {
      await setMeetingStatus(meeting_id, "analyzing");
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
      await setMeetingStatus(meeting_id, "analyzed");
    });

    return { meeting_id, status: "analyzed" };
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
// calendar/refresh.requested — user-triggered refresh from the Calendar
// page's "Refresh" button. Looks up only the invoking user's active
// integrations and fans out a `calendar/sync.requested` per platform so
// the existing syncCalendarForUser handler does the pull. Scoped to one
// user so a single button press doesn't re-sync the whole workspace.
// ---------------------------------------------------------------------------
export const refreshCalendarForUser = inngest.createFunction(
  {
    id: "refresh-calendar-for-user",
    concurrency: { limit: 8 },
    // Debounce so a frantic Refresh-button-clicker collapses to one sync
    // per user every 30s. Without this, 5 clicks fan out to 5 worker calls
    // and 5 outbound provider hits — wasted quota for zero new data.
    debounce: { period: "30s", key: "event.data.user_id" },
  },
  { event: "calendar/refresh.requested" },
  async ({ event, step }) => {
    const { org_id, user_id } = event.data;

    const integrations = await step.run("list-user-integrations", async () => {
      const r = await fetch(
        `${WORKER_URL}/api/v1/internal/calendar/list-active-integrations`,
        { headers: internalHeaders() }
      );
      if (!r.ok) throw new Error(`list failed: ${r.status}`);
      const body = (await r.json()) as {
        integrations: { org_id: string; user_id: string; platform: string }[];
      };
      return body.integrations.filter(
        (i) => i.org_id === org_id && i.user_id === user_id
      );
    });

    if (integrations.length === 0) return { platforms: 0 };

    await step.sendEvent(
      "fan-out-user-sync",
      integrations.map((i) => ({
        name: "calendar/sync.requested" as const,
        data: { org_id: i.org_id, user_id: i.user_id, platform: i.platform },
      }))
    );

    return { platforms: integrations.length };
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
  processBotMeeting,
  processDocument,
  startBotSession,
  cancelBotSession,
  autoScheduleDueBots,
  autoScheduleDueBotsOnDemand,
  ingestZoomRecording,
  processTeamsCallRecord,
  syncCalendars,
  syncCalendarForUser,
  refreshCalendarForUser,
  renewMicrosoftSubscriptions,
  ensureMicrosoftSubscription,
];
