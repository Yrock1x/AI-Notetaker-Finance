"use client";

// CogniVault "Connect a deal to a VDR" hooks (worker REST API, cookie-authed).
//
// The connection's existence + share_scopes are the per-deal opt-in that gates
// what CogniVault can pull from the partner API. The connect step itself is an
// OAuth redirect: useConnectVdr() returns the authorize URL; the caller does a
// full-page navigation to it (CogniVault enforces "is a VDR admin" on consent).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { VdrConnection, VdrShareScope } from "@/types";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/worker-api";

const VDR_KEY = "cognivault-connection";

export function useVdrConnection(dealId: string | undefined) {
  return useQuery<VdrConnection>({
    queryKey: [VDR_KEY, dealId],
    queryFn: async () =>
      apiGet<VdrConnection>(`/cognivault/deals/${dealId}/connection`),
    enabled: !!dealId,
  });
}

// Returns the CogniVault authorize URL; the component navigates the browser to it.
export function useConnectVdr() {
  return useMutation({
    mutationFn: async (dealId: string) =>
      apiPost<{ authorization_url: string }>(
        `/cognivault/deals/${dealId}/connect`
      ),
  });
}

export function useUpdateVdrShareScopes() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      dealId,
      shareScopes,
    }: {
      dealId: string;
      shareScopes: VdrShareScope[];
    }) =>
      apiPatch<VdrConnection>(`/cognivault/deals/${dealId}/connection`, {
        share_scopes: shareScopes,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: [VDR_KEY, variables.dealId] });
    },
  });
}

export function useDisconnectVdr() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (dealId: string) => {
      await apiDelete<void>(`/cognivault/deals/${dealId}/connection`);
    },
    onSuccess: (_data, dealId) => {
      queryClient.invalidateQueries({ queryKey: [VDR_KEY, dealId] });
    },
  });
}
