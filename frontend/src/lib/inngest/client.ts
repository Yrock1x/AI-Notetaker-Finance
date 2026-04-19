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

type AppEvents = {
  "meeting/uploaded": MeetingUploaded;
  "document/uploaded": DocumentUploaded;
  "bot/scheduled": BotScheduled;
  "bot/cancelled": BotCancelled;
  "zoom/recording.completed": ZoomRecordingCompleted;
  "teams/call_record.created": TeamsCallRecordCreated;
};

export const inngest = new Inngest({
  id: "cognisuite",
  schemas: new EventSchemas().fromRecord<AppEvents>(),
});

export type { AppEvents };
