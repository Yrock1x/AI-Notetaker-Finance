"use client";

// Standalone live transcription view — used when someone deep-links to a
// live meeting. The meeting detail page embeds the same panel inline as a
// "Live" tab (see ../page.tsx).

import { useParams } from "next/navigation";
import { useMeeting } from "@/hooks/use-meetings";
import { useBotSessions } from "@/hooks/use-bot-sessions";
import { LiveTranscriptPanel } from "@/components/transcripts/live-transcript-panel";

export default function LiveTranscriptPage() {
  const params = useParams<{ dealId: string; meetingId: string }>();
  const { data: meeting } = useMeeting(params.dealId, params.meetingId);
  const { data: botSessions = [] } = useBotSessions({
    deal_id: params.dealId,
  });

  const activeSession = botSessions.find(
    (s) =>
      s.meeting_id === params.meetingId &&
      ["scheduled", "joining", "recording"].includes(s.status)
  );

  return (
    <div className="flex h-[calc(100vh-12rem)] flex-col gap-4">
      <div>
        <h2 className="font-heading text-2xl font-bold text-primary">
          {meeting?.title ?? "Live Meeting"}
        </h2>
        <p className="font-subheading text-sm text-[#1A1A1A]/60">
          {activeSession?.platform
            ? `Bot on ${activeSession.platform.replace("_", " ")} — ${activeSession.status}`
            : "Bot not connected"}
        </p>
      </div>
      <LiveTranscriptPanel
        meetingId={params.meetingId}
        heightClass="flex-1"
      />
    </div>
  );
}
