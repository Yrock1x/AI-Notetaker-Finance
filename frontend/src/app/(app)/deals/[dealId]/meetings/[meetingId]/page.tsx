"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMeeting } from "@/hooks/use-meetings";
import { TranscriptViewer } from "@/components/transcripts/transcript-viewer";
import { MeetingQAChat } from "@/components/qa/meeting-qa-chat";
import { AnalysisPanel } from "@/components/analysis/analysis-panel";
import { CallTypeSelector } from "@/components/analysis/call-type-selector";
import { useAnalyses, useRunAnalysis } from "@/hooks/use-analysis";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import { MEETING_STATUS_LABELS } from "@/lib/constants";
import { formatDuration } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { ArrowLeft, Clock, Play } from "lucide-react";
import { CallType } from "@/types";

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

type MeetingTab = "transcript" | "analysis" | "chat";

const meetingTabs: { key: MeetingTab; label: string }[] = [
  { key: "transcript", label: "Transcript" },
  { key: "analysis", label: "Analysis" },
  { key: "chat", label: "AI Chat" },
];

export default function MeetingDetailPage() {
  const params = useParams<{ dealId: string; meetingId: string }>();
  const { data: meeting, isLoading } = useMeeting(params.dealId, params.meetingId);
  const [activeTab, setActiveTab] = useState<MeetingTab>("transcript");

  if (isLoading || !meeting) {
    return <LoadingState message="Loading meeting..." />;
  }

  const hasContent =
    meeting.status === "transcribed" ||
    meeting.status === "analyzed" ||
    meeting.status === "ready";

  const isProcessing =
    meeting.status === "processing" ||
    meeting.status === "transcribing" ||
    meeting.status === "analyzing";

  return (
    <div className="space-y-6">
      {/* Header */}
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

        <span
          className={cn(
            "rounded-full px-3 py-1 text-xs font-medium",
            STATUS_COLORS[meeting.status] ?? "bg-gray-100 text-gray-800"
          )}
        >
          {MEETING_STATUS_LABELS[meeting.status] ?? meeting.status}
        </span>
      </div>

      {/* Tab bar */}
      {hasContent && (
        <div className="flex space-x-2">
          {meetingTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
                activeTab === tab.key
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* Tab content */}
      {hasContent && (
        <>
          {activeTab === "transcript" && (
            <TranscriptViewer meetingId={meeting.id} />
          )}

          {activeTab === "analysis" && (
            <AnalysisTabContent meetingId={params.meetingId} />
          )}

          {activeTab === "chat" && (
            <MeetingQAChat meetingId={params.meetingId} />
          )}
        </>
      )}

      {isProcessing && (
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

function AnalysisTabContent({ meetingId }: { meetingId: string }) {
  const { data: analyses, isLoading } = useAnalyses(meetingId);
  const runAnalysis = useRunAnalysis();
  const [selectedCallType, setSelectedCallType] = useState<CallType>(
    CallType.MANAGEMENT_PRESENTATION
  );

  const handleRunAnalysis = async () => {
    await runAnalysis.mutateAsync({
      meetingId,
      payload: { call_type: selectedCallType },
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 rounded-lg border bg-white p-4">
        <CallTypeSelector
          value={selectedCallType}
          onChange={setSelectedCallType}
        />
        <button
          onClick={handleRunAnalysis}
          disabled={runAnalysis.isPending}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {runAnalysis.isPending ? "Running..." : "Run Analysis"}
        </button>
      </div>

      {isLoading ? (
        <LoadingState message="Loading analyses..." />
      ) : !analyses || analyses.length === 0 ? (
        <EmptyState
          title="No analyses yet"
          description="Select a call type and run an analysis to get AI-generated insights from this meeting."
        />
      ) : (
        <div className="space-y-4">
          {analyses.map((analysis) => (
            <AnalysisPanel key={analysis.id} analysis={analysis} />
          ))}
        </div>
      )}
    </div>
  );
}
