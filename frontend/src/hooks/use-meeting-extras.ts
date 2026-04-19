"use client";

// Live participants + in-meeting chat. Both are populated by Recall.ai
// webhooks → ``meeting_participants`` and ``meeting_chat_messages``. We
// subscribe via Supabase Realtime so users watching the Live tab see
// joiners and chat in real time.

import { useEffect, useRef, useState } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";
import { getBrowserSupabase } from "@/lib/supabase/browser";

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

export function useMeetingParticipants(meetingId: string | undefined) {
  const [participants, setParticipants] = useState<MeetingParticipant[]>([]);
  const channelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    if (!meetingId) {
      setParticipants([]);
      return;
    }
    const supabase = getBrowserSupabase();
    let cancelled = false;

    supabase
      .from("meeting_participants")
      .select("*")
      .eq("meeting_id", meetingId)
      .order("joined_at", { ascending: true })
      .then(({ data }) => {
        if (cancelled) return;
        setParticipants((data ?? []) as MeetingParticipant[]);
      });

    const channel = supabase
      .channel(`participants:${meetingId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "meeting_participants",
          filter: `meeting_id=eq.${meetingId}`,
        },
        (payload) => {
          const row = payload.new as MeetingParticipant | undefined;
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
        }
      )
      .subscribe();
    channelRef.current = channel;

    return () => {
      cancelled = true;
      channel.unsubscribe();
      channelRef.current = null;
    };
  }, [meetingId]);

  return { participants };
}

export function useMeetingChat(meetingId: string | undefined) {
  const [messages, setMessages] = useState<MeetingChatMessage[]>([]);
  const channelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    if (!meetingId) {
      setMessages([]);
      return;
    }
    const supabase = getBrowserSupabase();
    let cancelled = false;

    supabase
      .from("meeting_chat_messages")
      .select("*")
      .eq("meeting_id", meetingId)
      .order("sent_at", { ascending: true })
      .limit(500)
      .then(({ data }) => {
        if (cancelled) return;
        setMessages((data ?? []) as MeetingChatMessage[]);
      });

    const channel = supabase
      .channel(`chat:${meetingId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "meeting_chat_messages",
          filter: `meeting_id=eq.${meetingId}`,
        },
        (payload) => {
          const row = payload.new as MeetingChatMessage | undefined;
          if (!row) return;
          setMessages((prev) => [...prev, row]);
        }
      )
      .subscribe();
    channelRef.current = channel;

    return () => {
      cancelled = true;
      channel.unsubscribe();
      channelRef.current = null;
    };
  }, [meetingId]);

  return { messages };
}
