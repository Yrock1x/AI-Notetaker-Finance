"use client";

// Persistence layer for AI-extracted action item completion state, via the
// worker REST API (cookie-authenticated).
//
// Action items don't have their own DB rows — they're indexes into the
// `analyses.structured_output` JSON. Completion state is persisted keyed by a
// deterministic action_key (matches `${analysis_id}-act-${i}` from
// use-deal-extractions).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiDelete } from "@/lib/worker-api";

const KEY = "action-item-completions";

interface CompletionRow {
  action_key: string;
  completed_by: string;
  completed_at: string;
}

export function useActionItemCompletions(dealId: string | undefined) {
  return useQuery<Set<string>>({
    queryKey: [KEY, dealId],
    enabled: !!dealId,
    staleTime: 30_000,
    queryFn: async () => {
      const rows = await apiGet<{ action_key: string }[]>(
        `/deals/${dealId}/action-items`
      );
      return new Set(rows.map((r) => r.action_key));
    },
  });
}

interface ToggleArgs {
  dealId: string;
  actionKey: string;
  actionText: string;
  // The analysis row that produced this action item — used for the FK so the
  // completion is cascade-deleted if the analysis is re-run.
  analysisId: string;
  completed: boolean;
}

export function useToggleActionItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      dealId,
      actionKey,
      actionText,
      analysisId,
      completed,
    }: ToggleArgs) => {
      if (!completed) {
        await apiDelete<void>(
          `/deals/${dealId}/action-items/${encodeURIComponent(actionKey)}`
        );
        return;
      }
      await apiPost(`/deals/${dealId}/action-items`, {
        analysis_id: analysisId,
        action_key: actionKey,
        action_text: actionText,
      });
    },
    onMutate: async ({ dealId, actionKey, completed }) => {
      await queryClient.cancelQueries({ queryKey: [KEY, dealId] });
      const previous = queryClient.getQueryData<Set<string>>([KEY, dealId]);
      const next = new Set(previous ?? []);
      if (completed) next.add(actionKey);
      else next.delete(actionKey);
      queryClient.setQueryData([KEY, dealId], next);
      return { previous };
    },
    onError: (_err, vars, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData([KEY, vars.dealId], ctx.previous);
      }
    },
    onSettled: (_data, _err, vars) => {
      queryClient.invalidateQueries({ queryKey: [KEY, vars.dealId] });
    },
  });
}

export type CompletionSet = Set<string>;
export type { CompletionRow };
