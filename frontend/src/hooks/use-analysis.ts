import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type { Analysis, AnalysisRequest } from "@/types";

const ANALYSIS_KEY = "analyses";

export function useAnalyses(meetingId: string | undefined) {
  return useQuery({
    queryKey: [ANALYSIS_KEY, meetingId],
    queryFn: async () => {
      const { data } = await apiClient.get<Analysis[]>(
        `/meetings/${meetingId}/analyses`
      );
      return data;
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
      const { data } = await apiClient.get<Analysis>(
        `/meetings/${meetingId}/analyses/${analysisId}`
      );
      return data;
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
      const { data } = await apiClient.post<Analysis>(
        `/meetings/${meetingId}/analyses`,
        payload
      );
      return data;
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
      const { data } = await apiClient.post<Analysis>(
        `/meetings/${meetingId}/analyses/${analysisId}/rerun`
      );
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [ANALYSIS_KEY, variables.meetingId],
      });
    },
  });
}
