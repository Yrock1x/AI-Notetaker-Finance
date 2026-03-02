import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";

export interface Deliverable {
  id: string;
  deal_id: string;
  title: string;
  deliverable_type: string;
  file_format: string;
  status: string;
  download_url: string | null;
  created_at: string;
}

const DELIVERABLES_KEY = "deliverables";

export function useDeliverables(dealId: string | undefined) {
  return useQuery({
    queryKey: [DELIVERABLES_KEY, dealId],
    queryFn: async () => {
      const { data } = await apiClient.get<{ items: Deliverable[] }>(
        `/deals/${dealId}/deliverables`
      );
      return data;
    },
    enabled: !!dealId,
  });
}

export function useGenerateDeliverable() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ dealId, type }: { dealId: string; type: string }) => {
      const { data } = await apiClient.post<Deliverable>(
        `/deals/${dealId}/deliverables/generate`,
        { type }
      );
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [DELIVERABLES_KEY, variables.dealId],
      });
    },
  });
}

// ---------------------------------------------------------------------------
// Deliverable AI Chat
// ---------------------------------------------------------------------------

export interface DeliverableChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export function useDeliverableChat() {
  return useMutation({
    mutationFn: async ({
      dealId,
      message,
    }: {
      dealId: string;
      message: string;
    }) => {
      const { data } = await apiClient.post<DeliverableChatMessage>(
        `/deals/${dealId}/deliverables/chat`,
        { message }
      );
      return data;
    },
  });
}
