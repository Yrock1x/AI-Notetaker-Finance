"use client";

// Recent activity feed via the worker GET /dashboard/activity endpoint. The
// worker returns a flat shape ({actor_name, deal_name, ...}); we re-nest it
// into the existing ActivityRow shape so the dashboard component is unchanged.

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/worker-api";

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

interface ActivityResponse {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  deal_id: string | null;
  deal_name: string | null;
  actor_name: string | null;
  created_at: string;
  details: Record<string, unknown> | null;
}

export function useRecentActivity(limit = 15) {
  return useQuery<ActivityRow[]>({
    queryKey: ["dashboard", "recent-activity", limit],
    queryFn: async () => {
      const rows = await apiGet<ActivityResponse[]>("/dashboard/activity");
      return rows.slice(0, limit).map((r) => ({
        id: r.id,
        action: r.action,
        resource_type: r.resource_type,
        resource_id: r.resource_id,
        deal_id: r.deal_id,
        details: r.details,
        created_at: r.created_at,
        user: r.actor_name
          ? { id: "", full_name: r.actor_name, email: "" }
          : null,
        deal:
          r.deal_id && r.deal_name
            ? { id: r.deal_id, name: r.deal_name }
            : null,
      }));
    },
    staleTime: 30 * 1000,
  });
}
