// Zod schemas for the worker's /api/v1/internal/* responses consumed by the
// Inngest pipelines — the runtime contract with the Python worker. Shapes
// mirror the Pydantic response models in backend/app/api/v1/internal/; keep
// the two in sync when either side changes.
//
// Validation failures throw inside step.run, so Inngest retries loudly
// instead of carrying a malformed payload (e.g. a missing id) into event
// fan-outs.

import { z } from "zod";

// POST /internal/transcribe — backend TranscribeResponse
export const transcribeResponseSchema = z.object({
  transcript_id: z.string(),
});

// POST /internal/bot/auto-schedule-due — backend AutoScheduleDueResponse.
// deal_id rides along for observability; only session_id feeds the fan-out.
// It is null for calendar-synced meetings not yet assigned to a deal.
export const autoScheduleDueResponseSchema = z.object({
  scheduled: z.array(
    z.object({
      session_id: z.string(),
      meeting_id: z.string(),
      deal_id: z.string().nullable(),
    })
  ),
});

// POST /internal/zoom/ingest — backend ZoomIngestResponse. meeting_id is
// null when no stored Zoom credential could download the recording; the
// pipeline must NOT fire meeting/uploaded in that case.
export const zoomIngestResponseSchema = z.object({
  meeting_id: z.string().nullable(),
  status: z.string(),
});

// GET /internal/calendar/list-active-integrations
export const activeIntegrationsResponseSchema = z.object({
  integrations: z.array(
    z.object({
      org_id: z.string(),
      user_id: z.string(),
      platform: z.string(),
    })
  ),
});

// POST /internal/calendar/sync — backend CalendarSyncResponse
export const calendarSyncResponseSchema = z.object({
  platform: z.string(),
  events_seen: z.number(),
  meetings_upserted: z.number(),
});

// POST /internal/microsoft/ensure-subscription — backend EnsureSubscriptionResponse
export const ensureSubscriptionResponseSchema = z.object({
  subscription_id: z.string(),
  expiration: z.string(),
  action: z.string(),
});
