"use client";

import { useQuery } from "@tanstack/react-query";
import { getBrowserSupabase } from "@/lib/supabase/browser";

export interface ActivityRow {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  deal_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
  user: {
    id: string;
    full_name: string | null;
    email: string;
  } | null;
  deal: {
    id: string;
    name: string;
  } | null;
}

export function useRecentActivity(limit = 15) {
  return useQuery<ActivityRow[]>({
    queryKey: ["dashboard", "recent-activity", limit],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("audit_logs")
        .select(
          "id, action, resource_type, resource_id, deal_id, details, created_at, user:profiles(id, full_name, email), deal:deals(id, name)"
        )
        .order("created_at", { ascending: false })
        .limit(limit);
      if (error) throw error;
      return (data ?? []).map((row) => ({
        ...row,
        user: Array.isArray(row.user) ? row.user[0] ?? null : row.user,
        deal: Array.isArray(row.deal) ? row.deal[0] ?? null : row.deal,
      })) as ActivityRow[];
    },
    staleTime: 30 * 1000,
  });
}
