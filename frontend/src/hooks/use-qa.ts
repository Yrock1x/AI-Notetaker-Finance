import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type { QAInteraction, QARequest, QAResponse } from "@/types";

const QA_KEY = "qa";

export function useQAHistory(dealId: string | undefined) {
  return useQuery({
    queryKey: [QA_KEY, dealId],
    queryFn: async () => {
      const { data } = await apiClient.get<QAInteraction[]>(
        `/deals/${dealId}/qa`
      );
      return data;
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
      const { data } = await apiClient.post<QAResponse>(
        `/deals/${dealId}/qa`,
        payload
      );
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [QA_KEY, variables.dealId],
      });
    },
  });
}
