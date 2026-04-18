"use client";

// Transcript reads go direct to Supabase. RLS scopes rows to the user's
// orgs automatically.

import { useQuery } from "@tanstack/react-query";
import type {
  Transcript,
  TranscriptSegment,
  TranscriptSegmentFilters,
  PaginatedResponse,
} from "@/types";
import { getBrowserSupabase } from "@/lib/supabase/browser";

const TRANSCRIPTS_KEY = "transcripts";

export function useTranscript(meetingId: string | undefined) {
  return useQuery<Transcript | null>({
    queryKey: [TRANSCRIPTS_KEY, meetingId],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("transcripts")
        .select("*")
        .eq("meeting_id", meetingId!)
        .maybeSingle();
      if (error) throw error;
      return (data as Transcript) ?? null;
    },
    enabled: !!meetingId,
  });
}

export function useTranscriptSegments(
  meetingId: string | undefined,
  filters?: TranscriptSegmentFilters
) {
  return useQuery<PaginatedResponse<TranscriptSegment>>({
    queryKey: [TRANSCRIPTS_KEY, meetingId, "segments", filters],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      let query = supabase
        .from("transcript_segments")
        .select("*")
        .eq("meeting_id", meetingId!)
        .eq("is_partial", false)
        .order("start_time", { ascending: true });
      if (filters?.speaker_label) query = query.eq("speaker_label", filters.speaker_label);
      if (filters?.page_size) query = query.limit(filters.page_size);
      const { data, error } = await query;
      if (error) throw error;
      return {
        items: (data ?? []) as TranscriptSegment[],
        cursor: null,
        has_more: false,
      };
    },
    enabled: !!meetingId,
  });
}

export function useSearchTranscript(
  meetingId: string | undefined,
  query: string
) {
  return useQuery<TranscriptSegment[]>({
    queryKey: [TRANSCRIPTS_KEY, meetingId, "search", query],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const safe = query.replace(/[%_]/g, (c) => `\\${c}`);
      const { data, error } = await supabase
        .from("transcript_segments")
        .select("*")
        .eq("meeting_id", meetingId!)
        .eq("is_partial", false)
        .ilike("text", `%${safe}%`)
        .order("start_time", { ascending: true })
        .limit(200);
      if (error) throw error;
      return (data ?? []) as TranscriptSegment[];
    },
    enabled: !!meetingId && query.length > 0,
  });
}
