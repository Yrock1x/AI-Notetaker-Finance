"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { QAChat } from "@/components/qa/qa-chat";
import { useMeetings } from "@/hooks/use-meetings";

export default function QAPage() {
  const params = useParams<{ dealId: string }>();
  const { data: meetings } = useMeetings(params.dealId);
  // "" = all meetings (deal-wide RAG). A meeting id narrows to that meeting.
  const [meetingId, setMeetingId] = useState<string>("");

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Deal Q&A</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Ask questions about this deal. Answers are grounded in meeting
            transcripts and uploaded documents with citations.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label
            htmlFor="qa-meeting-filter"
            className="text-xs font-medium text-muted-foreground"
          >
            Scope
          </label>
          <select
            id="qa-meeting-filter"
            value={meetingId}
            onChange={(e) => setMeetingId(e.target.value)}
            className="min-w-[220px] rounded-md border px-3 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">All meetings + documents</option>
            {(meetings?.items ?? []).map((m) => (
              <option key={m.id} value={m.id}>
                {m.title}
              </option>
            ))}
          </select>
        </div>
      </div>
      {meetingId ? (
        <QAChat
          key={`m-${meetingId}`}
          scope="meeting"
          meetingId={meetingId}
          dealId={params.dealId}
        />
      ) : (
        <QAChat key="d-all" scope="deal" dealId={params.dealId} />
      )}
    </div>
  );
}
