"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMeetings } from "@/hooks/use-meetings";
import { MeetingCard } from "@/components/meetings/meeting-card";
import { UploadDialog } from "@/components/meetings/upload-dialog";
import { ScheduleBotDialog } from "@/components/meetings/schedule-bot-dialog";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Plus, Upload, Bot, Archive } from "lucide-react";

// "Active" = things the user is waiting on or participating in.
// Anything past the live call — including every post-meeting pipeline
// state and failures — lands in Archive so the top of the page stays
// focused on what's current.
const ACTIVE_STATUSES = new Set(["scheduled", "recording", "uploading"]);

function sortByDate(a: { meeting_date?: string | null; created_at: string }, b: typeof a, dir: "asc" | "desc") {
  const ta = new Date(a.meeting_date || a.created_at).getTime();
  const tb = new Date(b.meeting_date || b.created_at).getTime();
  return dir === "asc" ? ta - tb : tb - ta;
}

export default function MeetingsPage() {
  const params = useParams<{ dealId: string }>();
  const { data, isLoading } = useMeetings(params.dealId);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);

  const meetings = data?.items ?? [];

  const { active, archived } = useMemo(() => {
    const active = meetings
      .filter((m) => ACTIVE_STATUSES.has(m.status))
      .sort((a, b) => sortByDate(a, b, "asc"));
    const archived = meetings
      .filter((m) => !ACTIVE_STATUSES.has(m.status))
      .sort((a, b) => sortByDate(a, b, "desc"));
    return { active, archived };
  }, [meetings]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Meetings</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setScheduleOpen(true)}
            className="inline-flex items-center gap-2 rounded-md border border-primary bg-white px-4 py-2 text-sm font-medium text-primary hover:bg-primary/5"
          >
            <Bot className="h-4 w-4" />
            Schedule Notetaker
          </button>
          <button
            onClick={() => setUploadOpen(true)}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Upload className="h-4 w-4" />
            Upload Recording
          </button>
        </div>
      </div>

      {isLoading ? (
        <LoadingState message="Loading meetings..." />
      ) : meetings.length === 0 ? (
        <EmptyState
          title="No meetings yet"
          description="Upload a meeting recording to get started with transcription and analysis."
          action={
            <button
              onClick={() => setUploadOpen(true)}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" />
              Upload Recording
            </button>
          }
        />
      ) : (
        <div className="space-y-6">
          {active.length > 0 && (
            <section className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Active
              </h3>
              {active.map((meeting) => (
                <Link
                  key={meeting.id}
                  href={`/deals/${params.dealId}/meetings/${meeting.id}`}
                >
                  <MeetingCard meeting={meeting} />
                </Link>
              ))}
            </section>
          )}

          {archived.length > 0 && (
            <section className="space-y-3">
              <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                <Archive className="h-3 w-3" />
                Archive
                <span className="font-normal normal-case tracking-normal text-[10px] text-muted-foreground/60">
                  ({archived.length})
                </span>
              </h3>
              {archived.map((meeting) => (
                <Link
                  key={meeting.id}
                  href={`/deals/${params.dealId}/meetings/${meeting.id}`}
                >
                  <MeetingCard meeting={meeting} />
                </Link>
              ))}
            </section>
          )}
        </div>
      )}

      <UploadDialog
        dealId={params.dealId}
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
      />
      <ScheduleBotDialog
        dealId={params.dealId}
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
      />
    </div>
  );
}
