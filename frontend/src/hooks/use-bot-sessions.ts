"use client";

// Bot sessions via the worker REST API (cookie-authenticated). The worker
// creates the session row and drives the Recall.ai bot lifecycle server-side
// (and pre-creates the meeting row), so the frontend no longer writes to
// Supabase or fires Inngest events directly here.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, buildQuery } from "@/lib/worker-api";

export interface BotSession {
  id: string;
  org_id: string;
  deal_id: string;
  meeting_id: string | null;
  platform: "zoom" | "teams" | "google_meet";
  meeting_url: string;
  status: "scheduled" | "joining" | "recording" | "completed" | "failed" | "cancelled";
  scheduled_start?: string | null;
  actual_start?: string | null;
  actual_end?: string | null;
  recording_file_key?: string | null;
  live_transcript_channel?: string | null;
  recall_bot_id?: string | null;
  consent_obtained: boolean;
  created_by: string;
  created_at: string;
}

export interface ScheduleBotPayload {
  deal_id: string;
  platform: BotSession["platform"];
  meeting_url: string;
  scheduled_start?: string | null;
  meeting_id?: string | null;
  title?: string | null;
}

export function useBotSessions(
  params: { deal_id?: string; status?: string } = {}
) {
  return useQuery<BotSession[]>({
    queryKey: ["bot-sessions", params],
    queryFn: async () => {
      const qs = buildQuery({
        deal_id: params.deal_id,
        status: params.status,
      });
      return apiGet<BotSession[]>(`/bot-sessions${qs}`);
    },
    staleTime: 30 * 1000,
    // A bot going live (or ending) is driven server-side by the Recall webhook,
    // with no row-level push to the client. Poll so the live banner / "Live now"
    // stat appears/clears on its own. Cheap endpoint; pauses when the tab is
    // hidden (refetchIntervalInBackground defaults to false).
    refetchInterval: 30 * 1000,
  });
}

export function useScheduleBot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ScheduleBotPayload) =>
      apiPost<BotSession>("/bot-sessions", {
        deal_id: payload.deal_id,
        platform: payload.platform,
        meeting_url: payload.meeting_url,
        scheduled_start: payload.scheduled_start ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bot-sessions"] });
      queryClient.invalidateQueries({ queryKey: ["calendar", "meetings"] });
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });
}

export function useCancelBot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (sessionId: string) => {
      await apiPost<BotSession>(`/bot-sessions/${sessionId}/cancel`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bot-sessions"] });
    },
  });
}
