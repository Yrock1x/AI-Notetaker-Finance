"use client";

// Live participants + in-meeting chat, via the worker. Initial state comes
// from the REST endpoints (GET /meetings/{id}/participants and .../chat);
// live updates arrive on the shared SSE stream
// (GET /meetings/{id}/stream) as `participant` / `chat` events. A slow poll
// bridges any stream outage.

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/worker-api";

export interface MeetingParticipant {
  id: string;
  meeting_id: string;
  recall_participant_id: string | null;
  speaker_label: string;
  speaker_name: string | null;
  email_address: string | null;
  joined_at: string | null;
  left_at: string | null;
}

export interface MeetingChatMessage {
  id: string;
  meeting_id: string;
  sender_name: string | null;
  sender_email: string | null;
  text: string;
  sent_at: string;
  recall_message_id: string | null;
}

interface StreamEvent {
  kind: string;
  payload: unknown;
}

const POLL_INTERVAL_MS = 8000;

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function useMeetingParticipants(meetingId: string | undefined) {
  const [participants, setParticipants] = useState<MeetingParticipant[]>([]);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!meetingId) {
      setParticipants([]);
      return;
    }
    let cancelled = false;
    let streamUp = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const load = async () => {
      const data = await fetchJson<MeetingParticipant[]>(
        `/meetings/${meetingId}/participants`
      );
      if (!cancelled && data) setParticipants(data);
    };
    void load();

    const es = new EventSource(`${API_BASE}/meetings/${meetingId}/stream`, {
      withCredentials: true,
    });
    esRef.current = es;
    es.onopen = () => {
      streamUp = true;
    };
    es.onerror = () => {
      streamUp = false;
    };
    es.onmessage = (ev: MessageEvent) => {
      if (cancelled) return;
      let parsed: StreamEvent;
      try {
        parsed = JSON.parse(ev.data) as StreamEvent;
      } catch {
        return;
      }
      if (parsed.kind !== "participant") return;
      const row = parsed.payload as MeetingParticipant | undefined;
      if (!row) return;
      setParticipants((prev) => {
        const idx = prev.findIndex((p) => p.id === row.id);
        if (idx >= 0) {
          const copy = prev.slice();
          copy[idx] = row;
          return copy;
        }
        return [...prev, row];
      });
    };

    pollTimer = setInterval(() => {
      if (cancelled || streamUp) return;
      void load();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      es.close();
      esRef.current = null;
    };
  }, [meetingId]);

  return { participants };
}

export function useMeetingChat(meetingId: string | undefined) {
  const [messages, setMessages] = useState<MeetingChatMessage[]>([]);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!meetingId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    let streamUp = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    const load = async () => {
      const data = await fetchJson<MeetingChatMessage[]>(
        `/meetings/${meetingId}/chat`
      );
      if (!cancelled && data) setMessages(data);
    };
    void load();

    const es = new EventSource(`${API_BASE}/meetings/${meetingId}/stream`, {
      withCredentials: true,
    });
    esRef.current = es;
    es.onopen = () => {
      streamUp = true;
    };
    es.onerror = () => {
      streamUp = false;
    };
    es.onmessage = (ev: MessageEvent) => {
      if (cancelled) return;
      let parsed: StreamEvent;
      try {
        parsed = JSON.parse(ev.data) as StreamEvent;
      } catch {
        return;
      }
      if (parsed.kind !== "chat") return;
      const row = parsed.payload as MeetingChatMessage | undefined;
      if (!row) return;
      setMessages((prev) =>
        prev.some((m) => m.id === row.id) ? prev : [...prev, row]
      );
    };

    pollTimer = setInterval(() => {
      if (cancelled || streamUp) return;
      void load();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      es.close();
      esRef.current = null;
    };
  }, [meetingId]);

  return { messages };
}
