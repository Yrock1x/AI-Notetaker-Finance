"use client";

// Transcript reads via the worker REST API (cookie-authenticated). The worker
// scopes rows by the parent meeting's org.

import { useQuery } from "@tanstack/react-query";
import type {
  Transcript,
  TranscriptSegment,
  TranscriptSegmentFilters,
  PaginatedResponse,
} from "@/types";
import { apiGet, ApiError, buildQuery } from "@/lib/worker-api";

const TRANSCRIPTS_KEY = "transcripts";

export function useTranscript(meetingId: string | undefined) {
  return useQuery<Transcript | null>({
    queryKey: [TRANSCRIPTS_KEY, meetingId],
    queryFn: async () => {
      try {
        return await apiGet<Transcript>(`/meetings/${meetingId}/transcript`);
      } catch (e) {
        // No transcript yet → worker 404s; surface as null like maybeSingle().
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    enabled: !!meetingId,
  });
}

export function useTranscriptSegments(
  meetingId: string | undefined,
  filters?: TranscriptSegmentFilters
) {
  return useQuery<PaginatedResponse<TranscriptSegment>>({
    queryKey: [TRANSCRIPTS_KEY, meetingId, "segments", filters],
    queryFn: async () => {
      const qs = buildQuery({
        speaker: filters?.speaker_label,
        limit: filters?.page_size,
      });
      const items = await apiGet<TranscriptSegment[]>(
        `/meetings/${meetingId}/transcript-segments${qs}`
      );
      return {
        items,
        cursor: null,
        has_more: false,
      };
    },
    enabled: !!meetingId,
  });
}

export function useSearchTranscript(
  meetingId: string | undefined,
  query: string
) {
  return useQuery<TranscriptSegment[]>({
    queryKey: [TRANSCRIPTS_KEY, meetingId, "search", query],
    queryFn: async () => {
      const qs = buildQuery({ q: query, limit: 200 });
      return apiGet<TranscriptSegment[]>(
        `/meetings/${meetingId}/transcript-segments${qs}`
      );
    },
    enabled: !!meetingId && query.length > 0,
  });
}
