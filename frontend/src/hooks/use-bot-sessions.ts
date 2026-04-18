"use client";

// Bot sessions: reads go direct to Supabase; schedule/cancel fires an
// Inngest event (`bot.scheduled` / `bot.cancelled`) which the pipeline
// turns into a Recall.ai bot.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getBrowserSupabase } from "@/lib/supabase/browser";

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
}

export function useBotSessions(
  params: { deal_id?: string; status?: string } = {}
) {
  return useQuery<BotSession[]>({
    queryKey: ["bot-sessions", params],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      let query = supabase
        .from("meeting_bot_sessions")
        .select("*")
        .order("created_at", { ascending: false });
      if (params.deal_id) query = query.eq("deal_id", params.deal_id);
      if (params.status) query = query.eq("status", params.status);
      const { data, error } = await query;
      if (error) throw error;
      return (data ?? []) as BotSession[];
    },
    staleTime: 30 * 1000,
  });
}

export function useScheduleBot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ScheduleBotPayload) => {
      const supabase = getBrowserSupabase();
      const { data: auth } = await supabase.auth.getUser();
      if (!auth.user) throw new Error("Not authenticated");

      const { data: deal, error: dealErr } = await supabase
        .from("deals")
        .select("org_id")
        .eq("id", payload.deal_id)
        .single();
      if (dealErr) throw dealErr;

      // Insert the session row first; the Inngest function picks it up by id
      // and asks Recall.ai to create the actual bot.
      const { data, error } = await supabase
        .from("meeting_bot_sessions")
        .insert({
          org_id: deal.org_id,
          deal_id: payload.deal_id,
          meeting_id: payload.meeting_id ?? null,
          platform: payload.platform,
          meeting_url: payload.meeting_url,
          status: "scheduled",
          scheduled_start: payload.scheduled_start ?? null,
          created_by: auth.user.id,
        })
        .select()
        .single();
      if (error) throw error;

      await fetch("/api/inngest/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "bot/scheduled",
          data: { session_id: data.id },
        }),
      });

      return data as BotSession;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bot-sessions"] });
    },
  });
}

export function useCancelBot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (sessionId: string) => {
      const supabase = getBrowserSupabase();
      const { error } = await supabase
        .from("meeting_bot_sessions")
        .update({ status: "cancelled" })
        .eq("id", sessionId);
      if (error) throw error;

      await fetch("/api/inngest/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "bot/cancelled",
          data: { session_id: sessionId },
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bot-sessions"] });
    },
  });
}
