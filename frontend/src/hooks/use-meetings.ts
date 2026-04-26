"use client";

// Meeting CRUD: reads via Supabase, uploads go through the worker for the
// signed upload URL, then the frontend writes the meeting row + fires an
// Inngest event to kick off the pipeline.

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  Meeting,
  MeetingUploadInitiate,
  MeetingUploadInitiateResponse,
  PaginatedResponse,
} from "@/types";
import apiClient from "@/lib/api-client";
import { getBrowserSupabase } from "@/lib/supabase/browser";

const MEETINGS_KEY = "meetings";

// Cap on rows fetched per deal. A 200-meeting deal would otherwise ship
// every row on every Meetings tab view.
const DEFAULT_MEETINGS_LIMIT = 100;

export function useMeetings(dealId: string | undefined) {
  return useQuery<PaginatedResponse<Meeting>>({
    queryKey: [MEETINGS_KEY, dealId],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("meetings")
        .select("*")
        .eq("deal_id", dealId!)
        .order("created_at", { ascending: false })
        .limit(DEFAULT_MEETINGS_LIMIT);
      if (error) throw error;
      const items = (data ?? []) as Meeting[];
      return {
        items,
        cursor: null,
        has_more: items.length === DEFAULT_MEETINGS_LIMIT,
      };
    },
    enabled: !!dealId,
  });
}

// Status values that mean "pipeline is running" — used by the polling
// fallback so the UI eventually reflects state changes if Realtime drops.
const ACTIVE_PIPELINE_STATUSES = [
  "transcribing",
  "diarizing",
  "analyzing",
  "uploading",
];

export function useMeeting(
  dealId: string | undefined,
  meetingId: string | undefined
) {
  const queryClient = useQueryClient();

  const query = useQuery<Meeting>({
    queryKey: [MEETINGS_KEY, dealId, meetingId],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("meetings")
        .select("*")
        .eq("id", meetingId!)
        .single();
      if (error) throw error;
      return data as Meeting;
    },
    enabled: !!dealId && !!meetingId,
    // Slow fallback poll. Realtime (below) is the primary signal; this
    // catches the edge case where the WS subscription was dropped or the
    // user's network missed a notification while the page was hidden.
    refetchInterval: (q) => {
      const status = (q.state.data as Meeting | undefined)?.status;
      return status && ACTIVE_PIPELINE_STATUSES.includes(status) ? 30000 : false;
    },
  });

  // Realtime subscription on this meeting's row. Status changes pushed by
  // the Inngest pipeline arrive in <1s instead of waiting for the next
  // poll. We update the query cache directly with the new row so listeners
  // re-render immediately.
  useEffect(() => {
    if (!meetingId) return;
    const supabase = getBrowserSupabase();
    const channel = supabase
      .channel(`meeting:${meetingId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "meetings",
          filter: `id=eq.${meetingId}`,
        },
        (payload) => {
          queryClient.setQueryData<Meeting>(
            [MEETINGS_KEY, dealId, meetingId],
            payload.new as Meeting
          );
        }
      )
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, [dealId, meetingId, queryClient]);

  return query;
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
        Pick<Meeting, "title" | "meeting_date"> & { bot_enabled: boolean }
      >;
    }) => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("meetings")
        .update(patch)
        .eq("id", meetingId)
        .select()
        .single();
      if (error) throw error;
      return data as Meeting;
    },
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: [MEETINGS_KEY, dealId] });
      queryClient.invalidateQueries({
        queryKey: [MEETINGS_KEY, dealId, vars.meetingId],
      });
      queryClient.invalidateQueries({ queryKey: ["calendar", "meetings"] });
    },
  });
}

// Flip the bot on/off for a synced meeting. Writes the preference to
// meetings.bot_enabled (the single source of truth read by the
// auto-schedule cron + calendar sync). When the user turns the bot OFF,
// we also tell any in-flight session to leave the call — otherwise a
// recording bot would keep going until the meeting ends naturally.
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
      const supabase = getBrowserSupabase();
      const { error: updErr } = await supabase
        .from("meetings")
        .update({ bot_enabled })
        .eq("id", meetingId);
      if (updErr) throw updErr;

      // Turning the toggle OFF needs to stop any session the auto-scheduler
      // (or a manual Schedule click) already kicked off. Scan sessions
      // for this meeting that are still live and fire bot/cancelled for
      // them — the Inngest handler calls /internal/bot/stop which
      // instructs Recall to have the bot leave.
      if (!bot_enabled) {
        const { data: sessions } = await supabase
          .from("meeting_bot_sessions")
          .select("id, status")
          .eq("meeting_id", meetingId)
          .in("status", ["scheduled", "joining", "recording"]);
        for (const s of sessions ?? []) {
          await fetch("/api/inngest/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: "bot/cancelled",
              data: { session_id: s.id },
            }),
          });
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

export function useInitiateMeetingUpload() {
  // Calls the worker to mint a Supabase Storage signed upload URL.
  return useMutation({
    mutationFn: async (payload: MeetingUploadInitiate) => {
      const { data } = await apiClient.post<MeetingUploadInitiateResponse>(
        "/meetings/upload-ticket",
        {
          deal_id: payload.deal_id,
          filename: payload.filename,
          content_type: payload.content_type,
          size_bytes: payload.size_bytes,
        }
      );
      return data;
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
      const supabase = getBrowserSupabase();
      const { data: auth } = await supabase.auth.getUser();
      if (!auth.user) throw new Error("Not authenticated");

      const { data: deal, error: dealErr } = await supabase
        .from("deals")
        .select("org_id")
        .eq("id", payload.deal_id)
        .single();
      if (dealErr) throw dealErr;

      const insert = {
        org_id: deal.org_id,
        deal_id: payload.deal_id,
        title: payload.title,
        meeting_date: payload.meeting_date ?? null,
        duration_seconds: payload.duration_seconds ?? null,
        source: payload.source ?? "upload",
        file_key: payload.file_key,
        status: "uploaded",
        created_by: auth.user.id,
      };
      const { data, error } = await supabase
        .from("meetings")
        .insert(insert)
        .select()
        .single();
      if (error) throw error;

      // Fire the Inngest event to kick off the post-meeting pipeline. The
      // /api/inngest/send endpoint is a thin server-side wrapper that
      // validates the caller's session before relaying to Inngest.
      await fetch("/api/inngest/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "meeting/uploaded",
          data: { meeting_id: data.id, deal_id: payload.deal_id },
        }),
      });

      return data as Meeting;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [MEETINGS_KEY] });
    },
  });
}
