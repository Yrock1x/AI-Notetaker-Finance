"use client";

// Side-by-side participants list + in-meeting chat feed. Both streams come
// from Recall.ai via the ``participant_events.*`` and ``chat_messages.*``
// webhooks and fan out over the worker's SSE stream
// (GET /meetings/{id}/stream); a slow poll bridges any stream outage.

import {
  useMeetingParticipants,
  useMeetingChat,
} from "@/hooks/use-meeting-extras";
import { Users, MessageSquare, Radio, Circle } from "lucide-react";

// "Live" while the SSE stream is up; "Polling" while the fallback poll is
// bridging an outage (data still flows, just slower).
function StreamHealth({ connected }: { connected: boolean }) {
  return connected ? (
    <span className="ml-auto flex items-center gap-1.5">
      <Radio className="h-3.5 w-3.5 text-emerald-500 animate-pulse" />
      <span className="text-[10px] font-data uppercase tracking-widest text-emerald-600">
        Live
      </span>
    </span>
  ) : (
    <span className="ml-auto flex items-center gap-1.5">
      <Circle className="h-3.5 w-3.5 text-ink/20" />
      <span className="text-[10px] font-data uppercase tracking-widest text-ink/40">
        Polling
      </span>
    </span>
  );
}

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
  const { participants, isStreamConnected: participantsLive } =
    useMeetingParticipants(meetingId);
  const { messages, isStreamConnected: chatLive } = useMeetingChat(meetingId);

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* Participants */}
      <section className="rounded-xl border bg-white p-5">
        <header className="mb-4 flex items-center gap-2">
          <Users className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-bold text-primary">
            Participants ({participants.length})
          </h3>
          <StreamHealth connected={participantsLive} />
        </header>
        {participants.length === 0 ? (
          <p className="text-xs text-ink/40">
            No participants captured yet. Join events arrive from the bot in
            real time.
          </p>
        ) : (
          <ul className="space-y-2">
            {participants.map((p) => (
              <li
                key={p.id}
                className="flex items-center justify-between rounded-lg border border-ink/5 px-3 py-2"
              >
                <div>
                  <p className="text-xs font-semibold text-primary">
                    {p.speaker_name || p.speaker_label}
                  </p>
                  {p.email_address && (
                    <p className="text-[11px] text-ink/40">
                      {p.email_address}
                    </p>
                  )}
                </div>
                <span className="font-data text-[10px] text-ink/40">
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
          <StreamHealth connected={chatLive} />
        </header>
        {messages.length === 0 ? (
          <p className="text-xs text-ink/40">
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
                  <span className="font-data text-[10px] text-ink/40">
                    {formatTime(m.sent_at)}
                  </span>
                </div>
                <p className="mt-0.5 whitespace-pre-wrap text-ink/80">
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
