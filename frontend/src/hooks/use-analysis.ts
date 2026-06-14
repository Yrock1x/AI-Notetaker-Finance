import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/worker-api";
import type { Analysis, AnalysisRequest } from "@/types";

const ANALYSIS_KEY = "analyses";

// Analysis rows progress running → completed/failed. While any is still
// in-flight (or the upstream pipeline is expected to create one), poll so the
// Insights/Analysis tabs reflect completion without a manual refresh — there is
// no row-level push from the worker.
const ANALYSIS_IN_FLIGHT = ["pending", "running", "processing", "analyzing"];

export function useAnalyses(
  meetingId: string | undefined,
  opts: { pollWhileActive?: boolean } = {}
) {
  const { pollWhileActive = false } = opts;
  return useQuery({
    queryKey: [ANALYSIS_KEY, meetingId],
    queryFn: async () => {
      return apiGet<Analysis[]>(`/meetings/${meetingId}/analyses`);
    },
    enabled: !!meetingId,
    refetchInterval: (q) => {
      const rows = q.state.data as Analysis[] | undefined;
      if (rows?.some((a) => ANALYSIS_IN_FLIGHT.includes(String(a.status)))) {
        return 8000;
      }
      // No analysis row yet, but the pipeline upstream is still running — keep
      // checking so a freshly-created analysis appears on its own.
      if (pollWhileActive && (!rows || rows.length === 0)) return 8000;
      return false;
    },
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
