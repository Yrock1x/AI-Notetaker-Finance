"use client";

// Live transcription — consumes the worker SSE stream
// (GET /api/v1/meetings/{id}/stream). Partials show up first
// (is_partial=true) and get upserted in place by recall_segment_id when
// finalized.
//
// If the EventSource can't connect (or is interrupted), a 5-second poll
// against the transcript-segments endpoint picks up new segments so the panel
// still progresses (just with higher latency).
//
// The stream is SHARED per meetingId via a reference-counted module store: the
// Live tab mounts this hook from both the LiveBanner and the LiveTranscriptPanel
// for the same meeting, and we must not open two EventSources (each also pins a
// worker resource). The first subscriber opens the connection; the last one to
// unmount closes it.

import { useMemo, useSyncExternalStore } from "react";
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

// ---------------------------------------------------------------------------
// Shared per-meeting stream hub (one EventSource + poll, many subscribers).
// ---------------------------------------------------------------------------
interface Hub {
  snapshot: UseLiveTranscriptResult;
  listeners: Set<() => void>;
  refCount: number;
  es: EventSource | null;
  pollTimer: ReturnType<typeof setInterval> | null;
  streamUp: boolean;
  stopped: boolean;
}

const hubs = new Map<string, Hub>();

const EMPTY: UseLiveTranscriptResult = {
  segments: [],
  isConnected: false,
  isInitialLoading: false,
};

function update(hub: Hub, patch: Partial<UseLiveTranscriptResult>): void {
  hub.snapshot = { ...hub.snapshot, ...patch };
  for (const l of hub.listeners) l();
}

async function fetchAll(meetingId: string): Promise<LiveSegment[]> {
  const res = await fetch(
    `${API_BASE}/meetings/${meetingId}/transcript-segments?limit=500`,
    { credentials: "include" }
  );
  if (!res.ok) return [];
  return (await res.json()) as LiveSegment[];
}

function startHub(meetingId: string, hub: Hub): void {
  // 1) Prime with whatever segments already exist so users opening the panel
  //    mid-meeting don't stare at a blank screen.
  fetchAll(meetingId)
    .then((data) => {
      if (hub.stopped) return;
      update(hub, { segments: data, isInitialLoading: false });
    })
    .catch(() => {
      if (!hub.stopped) update(hub, { isInitialLoading: false });
    });

  // 2) Open the SSE stream; merge transcript_segment events by
  //    recall_segment_id so a finalized segment replaces its partial.
  const es = new EventSource(`${API_BASE}/meetings/${meetingId}/stream`, {
    withCredentials: true,
  });
  hub.es = es;

  es.onopen = () => {
    hub.streamUp = true;
    if (!hub.stopped) update(hub, { isConnected: true });
  };
  es.onerror = () => {
    hub.streamUp = false;
    if (!hub.stopped) update(hub, { isConnected: false });
    // EventSource auto-reconnects; the poll fallback bridges the gap.
  };
  es.onmessage = (ev: MessageEvent) => {
    if (hub.stopped) return;
    let parsed: StreamEvent;
    try {
      parsed = JSON.parse(ev.data) as StreamEvent;
    } catch {
      return;
    }
    if (parsed.kind !== "transcript_segment") return;
    const row = parsed.payload as LiveSegment | undefined;
    if (!row) return;
    update(hub, { segments: mergeSegment(hub.snapshot.segments, row) });
  };

  // 3) Poll fallback. Only commits new rows when the stream is NOT up, so a
  //    healthy SSE connection stays the source of truth.
  hub.pollTimer = setInterval(async () => {
    if (hub.stopped || hub.streamUp) return;
    try {
      const next = await fetchAll(meetingId);
      if (hub.stopped) return;
      // Commit on any change, not just a length change — a partial finalizing
      // in place (same id, new text, is_partial flips) keeps the count constant.
      if (segmentsSignature(next) !== segmentsSignature(hub.snapshot.segments)) {
        update(hub, { segments: next });
      }
    } catch {
      /* swallow — next tick retries */
    }
  }, POLL_INTERVAL_MS);
}

function stopHub(hub: Hub): void {
  hub.stopped = true;
  if (hub.pollTimer) clearInterval(hub.pollTimer);
  hub.es?.close();
  hub.es = null;
}

function makeSubscribe(meetingId: string | undefined) {
  return (onChange: () => void): (() => void) => {
    if (!meetingId) return () => {};
    let hub = hubs.get(meetingId);
    if (!hub) {
      hub = {
        snapshot: { segments: [], isConnected: false, isInitialLoading: true },
        listeners: new Set(),
        refCount: 0,
        es: null,
        pollTimer: null,
        streamUp: false,
        stopped: false,
      };
      hubs.set(meetingId, hub);
      startHub(meetingId, hub);
    }
    hub.listeners.add(onChange);
    hub.refCount += 1;
    return () => {
      const h = hubs.get(meetingId);
      if (!h) return;
      h.listeners.delete(onChange);
      h.refCount -= 1;
      if (h.refCount <= 0) {
        stopHub(h);
        hubs.delete(meetingId);
      }
    };
  };
}

export function useLiveTranscript(
  meetingId: string | undefined
): UseLiveTranscriptResult {
  const subscribe = useMemo(() => makeSubscribe(meetingId), [meetingId]);
  const getSnapshot = () =>
    meetingId ? hubs.get(meetingId)?.snapshot ?? EMPTY : EMPTY;
  return useSyncExternalStore(subscribe, getSnapshot, () => EMPTY);
}

// Cheap change-detector for the poll fallback: count + per-segment (key, partial
// flag, text length). Catches in-place updates without a full deep compare.
function segmentsSignature(segments: LiveSegment[]): string {
  let sig = String(segments.length);
  for (const s of segments) {
    sig += `|${s.recall_segment_id || s.id}:${s.is_partial ? 1 : 0}:${s.text.length}`;
  }
  return sig;
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
