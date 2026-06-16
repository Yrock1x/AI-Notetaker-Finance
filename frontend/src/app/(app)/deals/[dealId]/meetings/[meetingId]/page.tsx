"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMeeting, useUpdateMeeting } from "@/hooks/use-meetings";
import { meetingDisplayState } from "@/lib/meeting-status";
import { CallTypeSelector } from "@/components/analysis/call-type-selector";
import { useAnalyses, useRunAnalysis } from "@/hooks/use-analysis";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { MEETING_STATUS_LABELS } from "@/lib/constants";
import { formatDuration } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { ArrowLeft, Check, CheckCircle2, Clock, Pencil, Play, Radio, Sparkles, X } from "lucide-react";
import { CallType, MeetingStatus } from "@/types";

// Lazy-load heavy tab content — only loaded when the tab is active
const TranscriptViewer = dynamic(
  () => import("@/components/transcripts/transcript-viewer").then((m) => ({ default: m.TranscriptViewer })),
  { loading: () => <TabSkeleton /> }
);
const QAChat = dynamic(
  () => import("@/components/qa/qa-chat").then((m) => ({ default: m.QAChat })),
  { loading: () => <TabSkeleton /> }
);
const AnalysisPanel = dynamic(
  () => import("@/components/analysis/analysis-panel").then((m) => ({ default: m.AnalysisPanel })),
  { loading: () => <TabSkeleton /> }
);
const LiveTranscriptPanel = dynamic(
  () =>
    import("@/components/transcripts/live-transcript-panel").then((m) => ({
      default: m.LiveTranscriptPanel,
    })),
  { loading: () => <TabSkeleton /> }
);
const AttendeesPanel = dynamic(
  () =>
    import("@/components/meetings/attendees-panel").then((m) => ({
      default: m.AttendeesPanel,
    })),
  { loading: () => <TabSkeleton /> }
);

function TabSkeleton() {
  return (
    <div className="space-y-4 rounded-lg border p-6">
      <Skeleton className="h-6 w-1/3" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

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

type MeetingTab =
  | "live"
  | "insights"
  | "transcript"
  | "attendees"
  | "analysis"
  | "chat";

const BASE_TABS: { key: MeetingTab; label: string }[] = [
  { key: "insights", label: "Insights" },
  { key: "transcript", label: "Transcript" },
  { key: "attendees", label: "Attendees" },
  { key: "analysis", label: "Analysis" },
  { key: "chat", label: "AI Chat" },
];

export default function MeetingDetailPage() {
  const params = useParams<{ dealId: string; meetingId: string }>();
  const { data: meeting, isLoading } = useMeeting(params.dealId, params.meetingId);
  const updateMeeting = useUpdateMeeting(params.dealId);
  // Show the Live tab as soon as a bot is scheduled — not just when it's
  // actually recording. Users expect to see the live panel right after
  // clicking "Schedule Notetaker" so they can watch the bot join.
  // 'uploading' is the default status for calendar-synced meetings that
  // are waiting on the bot to arrive; treat it as a pre-live state too.
  // Time-aware: a months-old "recording"/"scheduled" row is a stale bot that
  // never finalized — don't force the Live panel for it.
  const liveState = meeting ? meetingDisplayState(meeting) : "other";
  const isLive =
    liveState === "live" ||
    liveState === "scheduled" ||
    meeting?.status === "uploading";
  const [activeTab, setActiveTab] = useState<MeetingTab>("insights");
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  // Auto-jump to the Live tab the moment a bot is scheduled or starts
  // recording so users watching the page don't miss the first few words.
  useEffect(() => {
    if (isLive) setActiveTab("live");
  }, [isLive]);

  if (isLoading || !meeting) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-4 w-1/3" />
        </div>
        <div className="flex space-x-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-8 w-24 rounded-full" />
          ))}
        </div>
        <TabSkeleton />
      </div>
    );
  }

  // A meeting has viewable content once its transcript has landed — which
  // for bot-recorded meetings happens at 'uploaded' (the state
  // /internal/bot/finalize leaves the row in after pulling from Recall).
  // Analyses may still be running at that point; individual tabs handle
  // their own empty states.
  const hasContent =
    meeting.status === MeetingStatus.UPLOADED ||
    meeting.status === MeetingStatus.ANALYZING ||
    meeting.status === MeetingStatus.TRANSCRIBED ||
    meeting.status === MeetingStatus.ANALYZED ||
    meeting.status === MeetingStatus.READY;

  const isProcessing =
    meeting.status === MeetingStatus.PROCESSING ||
    meeting.status === MeetingStatus.TRANSCRIBING ||
    meeting.status === MeetingStatus.ANALYZING;

  // The Live tab is only offered while the bot is actively recording.
  // When recording stops, the post-meeting pipeline takes over and the
  // regular Transcript tab becomes the source of truth.
  const tabs: { key: MeetingTab; label: string }[] = isLive
    ? [{ key: "live", label: "Live" }, ...BASE_TABS]
    : BASE_TABS;
  const showTabs = isLive || hasContent;

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
          {isEditingTitle ? (
            <form
              className="flex items-center gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                const next = titleDraft.trim();
                if (!next || next === meeting.title) {
                  setIsEditingTitle(false);
                  return;
                }
                await updateMeeting.mutateAsync({
                  meetingId: meeting.id,
                  patch: { title: next },
                });
                setIsEditingTitle(false);
              }}
            >
              <input
                autoFocus
                type="text"
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                className="min-w-[300px] rounded-md border px-3 py-1 text-2xl font-bold focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <button
                type="submit"
                disabled={updateMeeting.isPending}
                className="rounded-md bg-primary p-1.5 text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                title="Save"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setIsEditingTitle(false)}
                className="rounded-md border p-1.5 text-muted-foreground hover:bg-muted"
                title="Cancel"
              >
                <X className="h-4 w-4" />
              </button>
            </form>
          ) : (
            <div className="group flex items-center gap-2">
              <h1 className="text-2xl font-bold">{meeting.title}</h1>
              <button
                type="button"
                onClick={() => {
                  setTitleDraft(meeting.title);
                  setIsEditingTitle(true);
                }}
                className="rounded-md p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-muted hover:text-foreground group-hover:opacity-100"
                title="Rename meeting"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
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
      {showTabs && (
        <div className="flex space-x-2">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
                activeTab === tab.key
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              {tab.key === "live" && (
                <Radio className="h-3 w-3 animate-pulse text-red-500" />
              )}
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* Tab content */}
      {showTabs && (
        <>
          {activeTab === "live" && isLive && (
            // Two-column layout during a live recording: transcript on the
            // left (wider), Q&A chat on the right so you can ask questions
            // in real time without leaving the tab. Collapses to a single
            // column on <lg so mobile/tablet still works.
            <div className="grid h-[calc(100vh-14rem)] grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
              <LiveTranscriptPanel
                meetingId={params.meetingId}
                heightClass="h-full"
              />
              <QAChat
                scope="meeting"
                meetingId={params.meetingId}
                dealId={params.dealId}
                fillHeight
              />
            </div>
          )}

          {activeTab === "insights" && hasContent && (
            <InsightsTabContent
              meetingId={params.meetingId}
              pollWhileActive={isProcessing}
            />
          )}

          {activeTab === "transcript" && hasContent && (
            <TranscriptViewer meetingId={meeting.id} />
          )}

          {activeTab === "attendees" && (
            <AttendeesPanel meetingId={params.meetingId} />
          )}

          {activeTab === "analysis" && hasContent && (
            <AnalysisTabContent
              meetingId={params.meetingId}
              pollWhileActive={isProcessing}
            />
          )}

          {activeTab === "chat" && hasContent && (
            // Fill the remaining viewport vertically so the chat gets max
            // real estate for conversation. The offset is topbar + sticky
            // deal tabs + page header; tuned to match the Live split above.
            <div className="h-[calc(100vh-14rem)]">
              <QAChat
                scope="meeting"
                meetingId={params.meetingId}
                dealId={params.dealId}
                fillHeight
              />
            </div>
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

function AnalysisTabContent({
  meetingId,
  pollWhileActive,
}: {
  meetingId: string;
  pollWhileActive?: boolean;
}) {
  const { data: analyses, isLoading } = useAnalyses(meetingId, {
    pollWhileActive,
  });
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

// ---------------------------------------------------------------------------
// Insights report — auto-surfaced summary + action items + follow-ups from the
// summarization analysis that runs automatically after every call.
// ---------------------------------------------------------------------------
function InsightsTabContent({
  meetingId,
  pollWhileActive,
}: {
  meetingId: string;
  pollWhileActive?: boolean;
}) {
  const { data: analyses, isLoading } = useAnalyses(meetingId, {
    pollWhileActive,
  });
  if (isLoading) return <LoadingState message="Loading insights…" />;

  const list = analyses ?? [];
  const isSummary = (a: (typeof list)[number]) =>
    String(a.call_type) === "summarization";
  const summary =
    list.find((a) => isSummary(a) && String(a.status) === "completed") ??
    list.find(isSummary);
  const data = summary?.structured_output ?? summary?.result;

  if (!summary || !data) {
    return (
      <EmptyState
        title="Insights are being generated"
        description="A summary, action items, and follow-ups appear here automatically once the call finishes processing."
      />
    );
  }
  return <InsightsReport data={data} />;
}

function _arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}
function _str(v: unknown): string {
  if (typeof v === "string") return v;
  if (v == null) return "";
  return typeof v === "object" ? "" : String(v);
}
function _field(item: unknown, ...keys: string[]): string {
  if (typeof item === "string") return item;
  if (item && typeof item === "object") {
    const o = item as Record<string, unknown>;
    for (const k of keys) if (o[k] != null) return _str(o[k]);
  }
  return _str(item);
}

function InsightsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border bg-white p-5">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      {children}
    </div>
  );
}

function InsightsReport({ data }: { data: Record<string, unknown> }) {
  const summary = _str(data.executive_summary ?? data.summary);
  const actions = _arr(data.action_items);
  const decisions = _arr(data.decisions_made ?? data.decisions);
  const followUps = [
    ..._arr(data.key_takeaways),
    ..._arr(data.open_questions ?? data.follow_ups ?? data.next_steps),
  ];

  const empty = !summary && !actions.length && !decisions.length && !followUps.length;
  if (empty) {
    return (
      <EmptyState
        title="No insights extracted"
        description="The summary completed but didn't surface structured items for this call."
      />
    );
  }

  return (
    <div className="space-y-4">
      {summary && (
        <InsightsSection title="Summary">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
            {summary}
          </p>
        </InsightsSection>
      )}

      {actions.length > 0 && (
        <InsightsSection title={`Action Items (${actions.length})`}>
          <ul className="space-y-2.5">
            {actions.map((it, i) => {
              const text = _field(it, "action", "task", "description");
              const owner = _field(it, "owner", "assignee");
              const deadline = _field(it, "deadline", "due", "due_date");
              const priority = _field(it, "priority");
              const meta = [owner && `@${owner}`, deadline, priority]
                .filter(Boolean)
                .join(" · ");
              return (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span>
                    <span className="text-foreground">{text}</span>
                    {meta && (
                      <span className="ml-2 text-xs text-muted-foreground">{meta}</span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </InsightsSection>
      )}

      {decisions.length > 0 && (
        <InsightsSection title={`Decisions (${decisions.length})`}>
          <ul className="space-y-2">
            {decisions.map((it, i) => {
              const text = _field(it, "decision", "outcome");
              const by = _field(it, "decided_by", "owner");
              return (
                <li key={i} className="text-sm text-foreground">
                  {text}
                  {by && <span className="ml-2 text-xs text-muted-foreground">— {by}</span>}
                </li>
              );
            })}
          </ul>
        </InsightsSection>
      )}

      {followUps.length > 0 && (
        <InsightsSection title="Follow-ups & Open Questions">
          <ul className="space-y-1.5">
            {followUps.map((it, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span>{_field(it, "takeaway", "question", "item", "text")}</span>
              </li>
            ))}
          </ul>
        </InsightsSection>
      )}
    </div>
  );
}
