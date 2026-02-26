"use client";

import { useState } from "react";
import { useTranscript, useTranscriptSegments } from "@/hooks/use-transcripts";
import { LoadingState } from "@/components/shared/loading-state";
import { formatTimestamp } from "@/lib/utils";
import { Search, User } from "lucide-react";

interface TranscriptViewerProps {
  meetingId: string;
}

const SPEAKER_COLORS = [
  "text-blue-700 bg-blue-50",
  "text-green-700 bg-green-50",
  "text-purple-700 bg-purple-50",
  "text-orange-700 bg-orange-50",
  "text-pink-700 bg-pink-50",
  "text-teal-700 bg-teal-50",
];

export function TranscriptViewer({ meetingId }: TranscriptViewerProps) {
  const { data: transcript, isLoading: transcriptLoading } = useTranscript(meetingId);
  const { data: segmentsData, isLoading: segmentsLoading } = useTranscriptSegments(meetingId);
  const [searchQuery, setSearchQuery] = useState("");

  if (transcriptLoading || segmentsLoading) {
    return <LoadingState message="Loading transcript..." />;
  }

  if (!transcript) {
    return (
      <div className="rounded-lg border p-6 text-center text-muted-foreground">
        No transcript available yet.
      </div>
    );
  }

  const segments = Array.isArray(segmentsData) ? segmentsData : segmentsData?.items ?? [];
  const speakerMap = new Map<string, number>();
  let speakerIndex = 0;

  const filteredSegments = searchQuery
    ? segments.filter((s) =>
        s.text.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : segments;

  const getSpeakerColor = (speaker: string) => {
    if (!speakerMap.has(speaker)) {
      speakerMap.set(speaker, speakerIndex++);
    }
    return SPEAKER_COLORS[speakerMap.get(speaker)! % SPEAKER_COLORS.length];
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Transcript</h3>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {transcript.word_count.toLocaleString()} words
            {transcript.confidence_score != null &&
              ` · ${(transcript.confidence_score * 100).toFixed(0)}% confidence`}
          </span>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search transcript..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-48 rounded-md border py-1.5 pl-8 pr-3 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>
      </div>

      <div className="max-h-[600px] space-y-1 overflow-y-auto rounded-lg border bg-white p-4">
        {filteredSegments.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            {searchQuery ? "No matching segments found." : "No transcript segments available."}
          </p>
        ) : (
          filteredSegments.map((segment) => (
            <div
              key={segment.id}
              className="flex gap-3 rounded px-2 py-1.5 hover:bg-muted/50"
            >
              <div className="flex shrink-0 items-start gap-2 pt-0.5">
                <span className="text-xs text-muted-foreground tabular-nums">
                  {formatTimestamp(segment.start_time)}
                </span>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${getSpeakerColor(segment.speaker_label)}`}
                >
                  <User className="h-2.5 w-2.5" />
                  {segment.speaker_name ?? segment.speaker_label}
                </span>
              </div>
              <p className="flex-1 text-sm leading-relaxed">{segment.text}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
