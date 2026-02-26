"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useMeeting } from "@/hooks/use-meetings";
import { TranscriptViewer } from "@/components/transcripts/transcript-viewer";
import { LoadingState } from "@/components/shared/loading-state";
import { MEETING_STATUS_LABELS } from "@/lib/constants";
import { formatDuration } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { ArrowLeft, BarChart3, Clock } from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  scheduled: "bg-blue-100 text-blue-800",
  recording: "bg-red-100 text-red-800",
  processing: "bg-yellow-100 text-yellow-800",
  transcribed: "bg-green-100 text-green-800",
  analyzed: "bg-purple-100 text-purple-800",
  ready: "bg-green-100 text-green-800",
  transcribing: "bg-yellow-100 text-yellow-800",
  analyzing: "bg-purple-100 text-purple-800",
  failed: "bg-red-100 text-red-800",
};

export default function MeetingDetailPage() {
  const params = useParams<{ dealId: string; meetingId: string }>();
  const { data: meeting, isLoading } = useMeeting(params.dealId, params.meetingId);

  if (isLoading || !meeting) {
    return <LoadingState message="Loading meeting..." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <Link
            href={`/deals/${params.dealId}/meetings`}
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" />
            Back to meetings
          </Link>
          <h1 className="text-2xl font-bold">{meeting.title}</h1>
          <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
            <span>{meeting.source}</span>
            <span>·</span>
            <span>
              {meeting.meeting_date
                ? new Date(meeting.meeting_date).toLocaleDateString()
                : new Date(meeting.created_at).toLocaleDateString()}
            </span>
            {meeting.duration_seconds != null && (
              <>
                <span>·</span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatDuration(meeting.duration_seconds)}
                </span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium",
              STATUS_COLORS[meeting.status] ?? "bg-gray-100 text-gray-800"
            )}
          >
            {MEETING_STATUS_LABELS[meeting.status] ?? meeting.status}
          </span>
          {(meeting.status === "transcribed" || meeting.status === "analyzed" || meeting.status === "ready") && (
            <Link
              href={`/deals/${params.dealId}/meetings/${meeting.id}/analysis`}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <BarChart3 className="h-4 w-4" />
              View Analysis
            </Link>
          )}
        </div>
      </div>

      {(meeting.status === "transcribed" || meeting.status === "analyzed" || meeting.status === "ready") && (
        <TranscriptViewer meetingId={meeting.id} />
      )}

      {(meeting.status === "processing" || meeting.status === "transcribing" || meeting.status === "analyzing") && (
        <div className="rounded-lg border bg-yellow-50 p-6 text-center">
          <p className="text-sm text-yellow-800">
            This meeting is currently being processed. Transcript and analysis
            will be available once processing is complete.
          </p>
        </div>
      )}
    </div>
  );
}
