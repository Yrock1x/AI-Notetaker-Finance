"use client";

// Meeting CRUD: reads via Supabase, uploads go through the worker for the
// signed upload URL, then the frontend writes the meeting row + fires an
// Inngest event to kick off the pipeline.

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

export function useMeetings(dealId: string | undefined) {
  return useQuery<PaginatedResponse<Meeting>>({
    queryKey: [MEETINGS_KEY, dealId],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("meetings")
        .select("*")
        .eq("deal_id", dealId!)
        .order("created_at", { ascending: false });
      if (error) throw error;
      return {
        items: (data ?? []) as Meeting[],
        cursor: null,
        has_more: false,
      };
    },
    enabled: !!dealId,
  });
}

export function useMeeting(
  dealId: string | undefined,
  meetingId: string | undefined
) {
  return useQuery<Meeting>({
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
    // Poll while the pipeline is running so the UI reflects status changes.
    refetchInterval: (query) => {
      const status = (query.state.data as Meeting | undefined)?.status;
      return status && ["transcribing", "diarizing", "analyzing", "uploading"].includes(status)
        ? 4000
        : false;
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
      patch: Partial<Pick<Meeting, "title" | "meeting_date">>;
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
