// Inngest client + event type declarations.
//
// This file is imported both by the /api/inngest Next route handler (which
// hosts the worker) and by API routes that enqueue events. The client is
// the single source of truth for event names + payload shapes.

import { EventSchemas, Inngest } from "inngest";

// Shared payload shapes so both enqueue sites + handlers stay in sync.
type MeetingUploaded = {
  data: { meeting_id: string; deal_id: string };
};
type MeetingBotCompleted = {
  data: { session_id: string; meeting_id: string; deal_id: string };
};
type DocumentUploaded = {
  data: { document_id: string; deal_id: string };
};
type BotScheduled = { data: { session_id: string } };
type BotCancelled = { data: { session_id: string } };
type ZoomRecordingCompleted = {
  data: { zoom_meeting_id: string; download_url: string };
};
type TeamsCallRecordCreated = {
  data: { call_record_id: string; tenant_id: string | null };
};
type CalendarSyncRequested = {
  data: { org_id: string; user_id: string; platform: string };
};
type CalendarRefreshRequested = {
  // Triggered by the user clicking "Refresh" on the Calendar page. The
  // handler looks up their active integrations and fans out one
  // calendar/sync.requested per platform.
  data: { org_id: string; user_id: string };
};
type MicrosoftSubscriptionEnsure = {
  data: { org_id: string; user_id: string };
};

type AppEvents = {
  "meeting/uploaded": MeetingUploaded;
  "meeting/bot-completed": MeetingBotCompleted;
  "document/uploaded": DocumentUploaded;
  "bot/scheduled": BotScheduled;
  "bot/cancelled": BotCancelled;
  "zoom/recording.completed": ZoomRecordingCompleted;
  "teams/call_record.created": TeamsCallRecordCreated;
  "calendar/sync.requested": CalendarSyncRequested;
  "calendar/refresh.requested": CalendarRefreshRequested;
  "microsoft/subscription.ensure": MicrosoftSubscriptionEnsure;
};

// NOTE: keep this id in sync with the app registered in Inngest Cloud. The
// project was rebranded Deal Companion → CogniSuite but the Inngest app was
// originally created as "dealwise" and swapping the id orphans the signing
// key + function history. Keep it as "dealwise" until you deliberately
// create a fresh app (and issue a new INNGEST_EVENT_KEY / INNGEST_SIGNING_KEY).
export const inngest = new Inngest({
  id: "dealwise",
  schemas: new EventSchemas().fromRecord<AppEvents>(),
});

export type { AppEvents };
