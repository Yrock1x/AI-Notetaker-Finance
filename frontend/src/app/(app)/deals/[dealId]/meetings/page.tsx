"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMeetings } from "@/hooks/use-meetings";
import { MeetingCard } from "@/components/meetings/meeting-card";
import { UploadDialog } from "@/components/meetings/upload-dialog";
import { LoadingState } from "@/components/shared/loading-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Plus, Upload } from "lucide-react";

export default function MeetingsPage() {
  const params = useParams<{ dealId: string }>();
  const { data, isLoading } = useMeetings(params.dealId);
  const [uploadOpen, setUploadOpen] = useState(false);

  const meetings = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Meetings</h2>
        <button
          onClick={() => setUploadOpen(true)}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Upload className="h-4 w-4" />
          Upload Recording
        </button>
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
        <div className="space-y-3">
          {meetings.map((meeting) => (
            <Link
              key={meeting.id}
              href={`/deals/${params.dealId}/meetings/${meeting.id}`}
            >
              <MeetingCard meeting={meeting} />
            </Link>
          ))}
        </div>
      )}

      <UploadDialog
        dealId={params.dealId}
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
      />
    </div>
  );
}
