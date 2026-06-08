"use client";

// Live transcription — consumes the worker SSE stream
// (GET /api/v1/meetings/{id}/stream). Partials show up first
// (is_partial=true) and get upserted in place by recall_segment_id when
// finalized.
//
// If the EventSource can't connect (or is interrupted), a 5-second poll
// against the transcript-segments endpoint picks up new segments so the panel
// still progresses (just with higher latency).

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/worker-api";

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

const POLL_INTERVAL_MS = 5000;

// SSE envelope: { kind, payload }.
interface StreamEvent {
  kind: string;
  payload: unknown;
}

export function useLiveTranscript(
  meetingId: string | undefined
): UseLiveTranscriptResult {
  const [segments, setSegments] = useState<LiveSegment[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!meetingId) {
      setSegments([]);
      setIsConnected(false);
      setIsInitialLoading(false);
      return;
    }

    let cancelled = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let streamUp = false;

    const fetchAll = async (): Promise<LiveSegment[]> => {
      const res = await fetch(
        `${API_BASE}/meetings/${meetingId}/transcript-segments?limit=500`,
        { credentials: "include" }
      );
      if (!res.ok) return [];
      return (await res.json()) as LiveSegment[];
    };

    // 1) Prime with whatever segments already exist so users opening the panel
    //    mid-meeting don't stare at a blank screen.
    fetchAll()
      .then((data) => {
        if (cancelled) return;
        setSegments(data);
        setIsInitialLoading(false);
      })
      .catch(() => {
        if (!cancelled) setIsInitialLoading(false);
      });

    // 2) Open the SSE stream; merge transcript_segment events by
    //    recall_segment_id so a finalized segment replaces its partial.
    const es = new EventSource(`${API_BASE}/meetings/${meetingId}/stream`, {
      withCredentials: true,
    });
    esRef.current = es;

    es.onopen = () => {
      streamUp = true;
      if (!cancelled) setIsConnected(true);
    };
    es.onerror = () => {
      streamUp = false;
      if (!cancelled) setIsConnected(false);
      // EventSource auto-reconnects; the poll fallback bridges the gap.
    };
    es.onmessage = (ev: MessageEvent) => {
      if (cancelled) return;
      let parsed: StreamEvent;
      try {
        parsed = JSON.parse(ev.data) as StreamEvent;
      } catch {
        return;
      }
      if (parsed.kind !== "transcript_segment") return;
      const row = parsed.payload as LiveSegment | undefined;
      if (!row) return;
      setSegments((prev) => mergeSegment(prev, row));
    };

    // 3) Poll fallback. Only commits new rows when the stream is NOT up, so a
    //    healthy SSE connection stays the source of truth.
    pollTimer = setInterval(async () => {
      if (cancelled || streamUp) return;
      try {
        const next = await fetchAll();
        if (cancelled) return;
        setSegments((prev) => (next.length === prev.length ? prev : next));
      } catch {
        /* swallow — next tick retries */
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      es.close();
      esRef.current = null;
    };
  }, [meetingId]);

  return { segments, isConnected, isInitialLoading };
}

// Merge rule: if a segment with the same recall_segment_id exists, replace it
// (finalized text overwrites partial). Otherwise insert sorted by start_time.
function mergeSegment(prev: LiveSegment[], next: LiveSegment): LiveSegment[] {
  const key = next.recall_segment_id || next.id;
  const idx = prev.findIndex((s) => (s.recall_segment_id || s.id) === key);
  if (idx >= 0) {
    const copy = prev.slice();
    copy[idx] = next;
    return copy;
  }
  const inserted = prev.slice();
  const pos = inserted.findIndex((s) => s.start_time > next.start_time);
  if (pos === -1) inserted.push(next);
  else inserted.splice(pos, 0, next);
  return inserted;
}
