import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiPost } from "@/lib/worker-api";

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
  // The worker has no persisted GET for deliverables — they're generated on
  // demand (POST /generate). Back this list purely with the React Query cache:
  // it starts empty and useGenerateDeliverable appends to it. (Previously this
  // queried a nonexistent endpoint, 404'd, and the page silently showed empty.)
  return useQuery<{ items: Deliverable[] }>({
    queryKey: [DELIVERABLES_KEY, dealId],
    queryFn: async () => ({ items: [] }),
    enabled: !!dealId,
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

export function useGenerateDeliverable() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ dealId, type }: { dealId: string; type: string }) => {
      return apiPost<Deliverable>(`/deals/${dealId}/deliverables/generate`, {
        type,
      });
    },
    onSuccess: (data, variables) => {
      // Append to the cached list rather than invalidating — there's no GET to
      // refetch from, so invalidating would just reset to the empty placeholder.
      queryClient.setQueryData<{ items: Deliverable[] }>(
        [DELIVERABLES_KEY, variables.dealId],
        (prev) => ({ items: [data, ...(prev?.items ?? [])] })
      );
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
      return apiPost<DeliverableChatMessage>(`/deals/${dealId}/deliverables/chat`, {
        message,
      });
    },
  });
}
