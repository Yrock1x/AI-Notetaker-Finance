"use client";

// Meeting reads/updates via the worker REST API (cookie-authenticated).
// Uploads use the worker storage upload-ticket, then create the meeting row
// + fire the Inngest pipeline event.
//
// React Query keys are preserved. The former Supabase Realtime subscription
// on the meeting row is replaced by the existing slow polling fallback for
// active-pipeline statuses (the live page uses the SSE stream separately).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  Meeting,
  MeetingUploadInitiate,
  MeetingUploadInitiateResponse,
  PaginatedResponse,
} from "@/types";
import { apiGet, apiPatch, apiPost } from "@/lib/worker-api";
import { sendInngestEvent } from "@/lib/inngest-send";

const MEETINGS_KEY = "meetings";

export function useMeetings(dealId: string | undefined) {
  return useQuery<PaginatedResponse<Meeting>>({
    queryKey: [MEETINGS_KEY, dealId],
    queryFn: async () => {
      const items = await apiGet<Meeting[]>(`/deals/${dealId}/meetings`);
      return {
        items,
        cursor: null,
        has_more: false,
      };
    },
    enabled: !!dealId,
  });
}

// Status values that mean "pipeline is running" — used by the polling
// fallback so the UI eventually reflects state changes. These must be real
// MeetingStatus values (see types/enums.ts): "diarizing" was never one, and
// "processing" was missing.
const ACTIVE_PIPELINE_STATUSES = [
  "uploading",
  "processing",
  "transcribing",
  "analyzing",
];

export function useMeeting(
  dealId: string | undefined,
  meetingId: string | undefined
) {
  return useQuery<Meeting>({
    queryKey: [MEETINGS_KEY, dealId, meetingId],
    queryFn: async () => apiGet<Meeting>(`/meetings/${meetingId}`),
    enabled: !!dealId && !!meetingId,
    // Poll while the pipeline is active. (Previously Realtime pushed status
    // changes; the worker REST API has no row-level push, so this poll is now
    // the sole status-progression signal.)
    refetchInterval: (q) => {
      const status = (q.state.data as Meeting | undefined)?.status;
      return status && ACTIVE_PIPELINE_STATUSES.includes(status) ? 10000 : false;
    },
  });
}

export function useUpdateMeeting(dealId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      meetingId,
      patch,
    }: {
      meetingId: string;
      patch: Partial<
        Pick<Meeting, "title" | "meeting_date" | "deal_id"> & {
          bot_enabled: boolean;
        }
      >;
    }) => apiPatch<Meeting>(`/meetings/${meetingId}`, patch),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: [MEETINGS_KEY, dealId] });
      queryClient.invalidateQueries({
        queryKey: [MEETINGS_KEY, dealId, vars.meetingId],
      });
      queryClient.invalidateQueries({ queryKey: ["calendar", "meetings"] });
    },
  });
}

// Flip the bot on/off for a synced meeting. Writes the preference via
// PATCH /meetings/{id}. When turning the bot OFF, also cancel any in-flight
// bot session for this meeting so a recording bot leaves the call.
export function useToggleMeetingBot(dealId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      meetingId,
      bot_enabled,
    }: {
      meetingId: string;
      bot_enabled: boolean;
    }) => {
      await apiPatch<Meeting>(`/meetings/${meetingId}`, { bot_enabled });

      if (!bot_enabled) {
        // Cancel any live sessions for this meeting via the bot-sessions API.
        try {
          const sessions = await apiGet<Array<{ id: string; status: string; meeting_id: string | null }>>(
            `/bot-sessions`
          );
          const live = sessions.filter(
            (s) =>
              s.meeting_id === meetingId &&
              ["scheduled", "joining", "recording"].includes(s.status)
          );
          await Promise.all(
            live.map((s) => apiPost(`/bot-sessions/${s.id}/cancel`))
          );
        } catch {
          // Best-effort — toggle already persisted.
        }
      }
      return { meetingId, bot_enabled };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [MEETINGS_KEY, dealId] });
      queryClient.invalidateQueries({ queryKey: [MEETINGS_KEY] });
      queryClient.invalidateQueries({ queryKey: ["calendar", "meetings"] });
      queryClient.invalidateQueries({ queryKey: ["bot-sessions"] });
    },
  });
}

// Storage ticket shape from POST /storage/upload-ticket.
interface UploadTicket {
  bucket: string;
  key: string;
  upload_url: string;
  method: string;
}

const RECORDINGS_BUCKET = "meeting-recordings";

export function useInitiateMeetingUpload() {
  // Mints a signed upload URL via the worker storage endpoint.
  return useMutation({
    mutationFn: async (
      payload: MeetingUploadInitiate
    ): Promise<MeetingUploadInitiateResponse> => {
      const ticket = await apiPost<UploadTicket>("/storage/upload-ticket", {
        bucket: RECORDINGS_BUCKET,
        deal_id: payload.deal_id,
        filename: payload.filename,
      });
      // Map to the existing response shape consumers expect.
      return {
        file_key: ticket.key,
        upload_url: ticket.upload_url,
        token: "",
      };
    },
  });
}

export interface ConfirmMeetingUploadPayload {
  deal_id: string;
  file_key: string;
  title: string;
  content_type: string;
  duration_seconds?: number | null;
  meeting_date?: string | null;
  source?: Meeting["source"];
}

export function useConfirmMeetingUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ConfirmMeetingUploadPayload) => {
      // Create the meeting row via the worker, then fire the Inngest pipeline
      // event. (Worker creates the row server-side, scoping org from the deal.)
      const meeting = await apiPost<Meeting>(`/deals/${payload.deal_id}/meetings`, {
        title: payload.title,
        file_key: payload.file_key,
        meeting_date: payload.meeting_date ?? null,
        duration_seconds: payload.duration_seconds ?? null,
        source: payload.source ?? "upload",
        status: "uploaded",
      });

      // Throws on a relay rejection so the mutation reports the failure instead
      // of leaving the meeting stuck in "uploaded" with no pipeline running.
      await sendInngestEvent("meeting/uploaded", {
        meeting_id: meeting.id,
        deal_id: payload.deal_id,
      });

      return meeting;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [MEETINGS_KEY] });
    },
  });
}
