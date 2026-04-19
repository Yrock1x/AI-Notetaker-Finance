"use client";

// Side-by-side participants list + in-meeting chat feed. Both streams come
// from Recall.ai via the ``participant_events.*`` and ``chat_messages.*``
// webhooks and are broadcast via Supabase Realtime.

import {
  useMeetingParticipants,
  useMeetingChat,
} from "@/hooks/use-meeting-extras";
import { Users, MessageSquare } from "lucide-react";

function formatTime(iso: string | null) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function AttendeesPanel({ meetingId }: { meetingId: string }) {
  const { participants } = useMeetingParticipants(meetingId);
  const { messages } = useMeetingChat(meetingId);

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* Participants */}
      <section className="rounded-xl border bg-white p-5">
        <header className="mb-4 flex items-center gap-2">
          <Users className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-bold text-primary">
            Participants ({participants.length})
          </h3>
        </header>
        {participants.length === 0 ? (
          <p className="text-xs text-[#1A1A1A]/40">
            No participants captured yet. Join events arrive from the bot in
            real time.
          </p>
        ) : (
          <ul className="space-y-2">
            {participants.map((p) => (
              <li
                key={p.id}
                className="flex items-center justify-between rounded-lg border border-[#1A1A1A]/5 px-3 py-2"
              >
                <div>
                  <p className="text-xs font-semibold text-primary">
                    {p.speaker_name || p.speaker_label}
                  </p>
                  {p.email_address && (
                    <p className="text-[11px] text-[#1A1A1A]/40">
                      {p.email_address}
                    </p>
                  )}
                </div>
                <span className="font-data text-[10px] text-[#1A1A1A]/40">
                  {p.left_at
                    ? `left ${formatTime(p.left_at)}`
                    : p.joined_at
                    ? `joined ${formatTime(p.joined_at)}`
                    : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Chat */}
      <section className="rounded-xl border bg-white p-5">
        <header className="mb-4 flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-bold text-primary">
            In-meeting chat ({messages.length})
          </h3>
        </header>
        {messages.length === 0 ? (
          <p className="text-xs text-[#1A1A1A]/40">
            No chat messages yet.
          </p>
        ) : (
          <ul className="max-h-[500px] space-y-3 overflow-y-auto">
            {messages.map((m) => (
              <li key={m.id} className="text-xs">
                <div className="flex items-baseline gap-2">
                  <span className="font-semibold text-primary">
                    {m.sender_name || "Unknown"}
                  </span>
                  <span className="font-data text-[10px] text-[#1A1A1A]/40">
                    {formatTime(m.sent_at)}
                  </span>
                </div>
                <p className="mt-0.5 whitespace-pre-wrap text-[#1A1A1A]/80">
                  {m.text}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
