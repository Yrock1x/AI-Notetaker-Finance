import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type {
  Deal,
  DealMember,
  DealCreate,
  DealUpdate,
  DealFilters,
  DealMemberAdd,
  PaginatedResponse,
} from "@/types";

const DEALS_KEY = "deals";

export function useDeals(filters?: DealFilters) {
  return useQuery({
    queryKey: [DEALS_KEY, filters],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Deal>>("/deals", {
        params: filters,
      });
      return data;
    },
  });
}

export function useDeal(dealId: string | undefined) {
  return useQuery({
    queryKey: [DEALS_KEY, dealId],
    queryFn: async () => {
      const { data } = await apiClient.get<Deal>(`/deals/${dealId}`);
      return data;
    },
    enabled: !!dealId,
  });
}

export function useCreateDeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: DealCreate) => {
      const { data } = await apiClient.post<Deal>("/deals", payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [DEALS_KEY] });
    },
  });
}

export function useUpdateDeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      dealId,
      payload,
    }: {
      dealId: string;
      payload: DealUpdate;
    }) => {
      const { data } = await apiClient.patch<Deal>(
        `/deals/${dealId}`,
        payload
      );
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [DEALS_KEY, variables.dealId],
      });
      queryClient.invalidateQueries({ queryKey: [DEALS_KEY] });
    },
  });
}

export function useDeleteDeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (dealId: string) => {
      await apiClient.delete(`/deals/${dealId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [DEALS_KEY] });
    },
  });
}

export function useDealMembers(dealId: string | undefined) {
  return useQuery({
    queryKey: [DEALS_KEY, dealId, "members"],
    queryFn: async () => {
      const { data } = await apiClient.get<DealMember[]>(
        `/deals/${dealId}/members`
      );
      return data;
    },
    enabled: !!dealId,
  });
}

export function useAddDealMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      dealId,
      payload,
    }: {
      dealId: string;
      payload: DealMemberAdd;
    }) => {
      const { data } = await apiClient.post<DealMember>(
        `/deals/${dealId}/members`,
        payload
      );
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [DEALS_KEY, variables.dealId, "members"],
      });
    },
  });
}

export function useRemoveDealMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      dealId,
      userId,
    }: {
      dealId: string;
      userId: string;
    }) => {
      await apiClient.delete(`/deals/${dealId}/members/${userId}`);
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [DEALS_KEY, variables.dealId, "members"],
      });
    },
  });
}
