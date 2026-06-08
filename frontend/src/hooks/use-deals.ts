"use client";

// Deal CRUD via the worker REST API (cookie-authenticated). The worker
// enforces org scoping server-side; the frontend no longer talks to Supabase
// for deals.
//
// React Query keys are preserved verbatim so consuming components are
// unchanged.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  Deal,
  DealMember,
  DealCreate,
  DealUpdate,
  DealFilters,
  DealMemberAdd,
  PaginatedResponse,
} from "@/types";
import { apiGet, apiPost, apiPatch, apiDelete, buildQuery } from "@/lib/worker-api";

const DEALS_KEY = "deals";

const DEFAULT_DEALS_LIMIT = 50;

export function useDeals(filters?: DealFilters) {
  return useQuery<PaginatedResponse<Deal>>({
    queryKey: [DEALS_KEY, filters],
    queryFn: async () => {
      const qs = buildQuery({
        status: filters?.status,
        deal_type: filters?.deal_type,
        q: filters?.search,
        cursor: filters?.cursor,
        limit: filters?.limit ?? DEFAULT_DEALS_LIMIT,
      });
      return apiGet<PaginatedResponse<Deal>>(`/deals${qs}`);
    },
  });
}

export function useDeal(dealId: string | undefined) {
  return useQuery<Deal>({
    queryKey: [DEALS_KEY, dealId],
    queryFn: async () => apiGet<Deal>(`/deals/${dealId}`),
    enabled: !!dealId,
  });
}

export function useCreateDeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: DealCreate) =>
      apiPost<Deal>("/deals", payload),
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
    }) => apiPatch<Deal>(`/deals/${dealId}`, payload),
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
      await apiDelete<void>(`/deals/${dealId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [DEALS_KEY] });
    },
  });
}

export function useDealMembers(dealId: string | undefined) {
  return useQuery<DealMember[]>({
    queryKey: [DEALS_KEY, dealId, "members"],
    queryFn: async () => apiGet<DealMember[]>(`/deals/${dealId}/members`),
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
    }) => apiPost<DealMember>(`/deals/${dealId}/members`, payload),
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
      await apiDelete<void>(`/deals/${dealId}/members/${userId}`);
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [DEALS_KEY, variables.dealId, "members"],
      });
    },
  });
}
