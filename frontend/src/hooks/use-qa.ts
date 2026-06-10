import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/worker-api";
import type { QAInteraction, QARequest, QAResponse } from "@/types";

const QA_KEY = "qa";

export function useQAHistory(dealId: string | undefined) {
  return useQuery({
    queryKey: [QA_KEY, dealId],
    queryFn: async () => {
      return apiGet<QAInteraction[]>(`/deals/${dealId}/qa/history`);
    },
    enabled: !!dealId,
  });
}

export function useAskQuestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      dealId,
      payload,
    }: {
      dealId: string;
      payload: QARequest;
    }) => {
      return apiPost<QAResponse>(`/deals/${dealId}/qa/ask`, payload);
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [QA_KEY, variables.dealId],
      });
    },
  });
}

export function useMeetingAskQuestion() {
  return useMutation({
    mutationFn: async ({
      meetingId,
      payload,
    }: {
      meetingId: string;
      payload: QARequest;
    }) => {
      return apiPost<QAResponse>(`/meetings/${meetingId}/qa/ask`, payload);
    },
  });
}
