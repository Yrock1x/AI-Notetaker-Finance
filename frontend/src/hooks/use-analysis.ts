import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/worker-api";
import type { Analysis, AnalysisRequest } from "@/types";

const ANALYSIS_KEY = "analyses";

export function useAnalyses(meetingId: string | undefined) {
  return useQuery({
    queryKey: [ANALYSIS_KEY, meetingId],
    queryFn: async () => {
      return apiGet<Analysis[]>(`/meetings/${meetingId}/analyses`);
    },
    enabled: !!meetingId,
  });
}

export function useAnalysis(
  meetingId: string | undefined,
  analysisId: string | undefined
) {
  return useQuery({
    queryKey: [ANALYSIS_KEY, meetingId, analysisId],
    queryFn: async () => {
      return apiGet<Analysis>(`/meetings/${meetingId}/analyses/${analysisId}`);
    },
    enabled: !!meetingId && !!analysisId,
  });
}

export function useRunAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      meetingId,
      payload,
    }: {
      meetingId: string;
      payload: AnalysisRequest;
    }) => {
      return apiPost<Analysis>(`/meetings/${meetingId}/analyses`, payload);
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [ANALYSIS_KEY, variables.meetingId],
      });
    },
  });
}

export function useRerunAnalysis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      meetingId,
      analysisId,
    }: {
      meetingId: string;
      analysisId: string;
    }) => {
      return apiPost<Analysis>(
        `/meetings/${meetingId}/analyses/${analysisId}/rerun`
      );
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [ANALYSIS_KEY, variables.meetingId],
      });
    },
  });
}
