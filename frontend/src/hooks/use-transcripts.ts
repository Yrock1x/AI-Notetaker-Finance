import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type {
  Transcript,
  TranscriptSegment,
  TranscriptSegmentFilters,
  PaginatedResponse,
} from "@/types";

const TRANSCRIPTS_KEY = "transcripts";

export function useTranscript(meetingId: string | undefined) {
  return useQuery({
    queryKey: [TRANSCRIPTS_KEY, meetingId],
    queryFn: async () => {
      const { data } = await apiClient.get<Transcript>(
        `/meetings/${meetingId}/transcript`
      );
      return data;
    },
    enabled: !!meetingId,
  });
}

export function useTranscriptSegments(
  meetingId: string | undefined,
  filters?: TranscriptSegmentFilters
) {
  return useQuery({
    queryKey: [TRANSCRIPTS_KEY, meetingId, "segments", filters],
    queryFn: async () => {
      const { data } = await apiClient.get<
        PaginatedResponse<TranscriptSegment>
      >(`/meetings/${meetingId}/transcript/segments`, {
        params: filters,
      });
      return data;
    },
    enabled: !!meetingId,
  });
}

export function useSearchTranscript(
  meetingId: string | undefined,
  query: string
) {
  return useQuery({
    queryKey: [TRANSCRIPTS_KEY, meetingId, "search", query],
    queryFn: async () => {
      const { data } = await apiClient.get<TranscriptSegment[]>(
        `/meetings/${meetingId}/transcript/search`,
        {
          params: { q: query },
        }
      );
      return data;
    },
    enabled: !!meetingId && query.length > 0,
  });
}
