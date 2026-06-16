"use client";

// Feeds the Dashboard "Upcoming meetings to assign" widget. Pulls
// calendar-synced, deal-less meetings from the worker, then narrows to the
// next 7 days (plus a 30-min grace window for calls that just started) so a
// live call doesn't vanish the moment the clock ticks past its start.

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/worker-api";
import type { Meeting } from "@/types";

export function useUpcomingUnassigned() {
  return useQuery<Meeting[]>({
    queryKey: ["dashboard", "upcoming-unassigned"],
    queryFn: async () => {
      const rows = await apiGet<Meeting[]>("/dashboard/upcoming-unassigned");
      const now = Date.now();
      const floor = now - 30 * 60 * 1000;
      const horizon = now + 7 * 24 * 60 * 60 * 1000;
      return rows.filter((m) => {
        if (!m.meeting_date) return false;
        const t = new Date(m.meeting_date).getTime();
        return Number.isFinite(t) && t >= floor && t <= horizon;
      });
    },
    // Reasonably fresh — this lists rows the user is actively triaging.
    staleTime: 30 * 1000,
  });
}
