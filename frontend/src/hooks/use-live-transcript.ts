"use client";

// Live transcription — subscribes to Postgres-changes on transcript_segments
// scoped by meeting_id. Partials show up first (is_partial=true) and get
// upserted in place by recall_segment_id when finalized.
//
// Backed by Supabase Realtime, which honours RLS: users only receive
// segments for meetings in an org they belong to.

import { useEffect, useRef, useState } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { getBrowserSupabase } from "@/lib/supabase/browser";

export interface LiveSegment {
  id: string;
  meeting_id: string;
  recall_segment_id: string | null;
  speaker_label: string;
  speaker_name: string | null;
  text: string;
  start_time: number;
  end_time: number;
  confidence: number | null;
  is_partial: boolean;
}

interface UseLiveTranscriptResult {
  segments: LiveSegment[];
  isConnected: boolean;
  isInitialLoading: boolean;
}

export function useLiveTranscript(
  meetingId: string | undefined
): UseLiveTranscriptResult {
  const [segments, setSegments] = useState<LiveSegment[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const channelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    if (!meetingId) {
      setSegments([]);
      setIsConnected(false);
      setIsInitialLoading(false);
      return;
    }

    const supabase = getBrowserSupabase();
    let cancelled = false;

    // 1) Prime with whatever segments already exist — partials included so
    //    users who open the panel mid-meeting don't stare at a blank screen.
    supabase
      .from("transcript_segments")
      .select(
        "id, meeting_id, recall_segment_id, speaker_label, speaker_name, text, start_time, end_time, confidence, is_partial"
      )
      .eq("meeting_id", meetingId)
      .order("start_time", { ascending: true })
      .limit(500)
      .then(({ data }) => {
        if (cancelled) return;
        setSegments((data ?? []) as LiveSegment[]);
        setIsInitialLoading(false);
      });

    // 2) Subscribe to INSERT + UPDATE events; merge by recall_segment_id so a
    //    finalized segment replaces its partial in place.
    const channel = supabase
      .channel(`transcripts:${meetingId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "transcript_segments",
          filter: `meeting_id=eq.${meetingId}`,
        },
        (payload) => {
          const row = payload.new as LiveSegment | undefined;
          if (!row) return;
          setSegments((prev) => mergeSegment(prev, row));
        }
      )
      .subscribe((status) => {
        setIsConnected(status === "SUBSCRIBED");
      });

    channelRef.current = channel;

    return () => {
      cancelled = true;
      channel.unsubscribe();
      channelRef.current = null;
    };
  }, [meetingId]);

  return { segments, isConnected, isInitialLoading };
}

// Merge rule: if a segment with the same recall_segment_id exists, replace
// it (finalized text overwrites partial). Otherwise insert sorted by
// start_time.
function mergeSegment(prev: LiveSegment[], next: LiveSegment): LiveSegment[] {
  const key = next.recall_segment_id || next.id;
  const idx = prev.findIndex(
    (s) => (s.recall_segment_id || s.id) === key
  );
  if (idx >= 0) {
    const copy = prev.slice();
    copy[idx] = next;
    return copy;
  }
  // Insert in order.
  const inserted = prev.slice();
  const pos = inserted.findIndex((s) => s.start_time > next.start_time);
  if (pos === -1) inserted.push(next);
  else inserted.splice(pos, 0, next);
  return inserted;
}
