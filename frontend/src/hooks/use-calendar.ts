"use client";

// Calendar = all meetings across deals in the user's org, via the worker
// GET /calendar/meetings endpoint (cookie-authenticated). The worker joins the
// deal name so the calendar page doesn't need an N+1 fan-out.

import { useQuery } from "@tanstack/react-query";
import type { Meeting } from "@/types";
import { apiGet } from "@/lib/worker-api";

export interface CalendarMeeting extends Meeting {
  deal_name: string;
  deal_id: string;
}

interface CalendarMeetingRow extends Meeting {
  deal?: { id: string; name: string } | null;
}

export function useCalendarMeetings() {
  const q = useQuery<CalendarMeeting[]>({
    queryKey: ["calendar", "meetings"],
    queryFn: async () => {
      const rows = await apiGet<CalendarMeetingRow[]>("/calendar/meetings");
      return rows.map((row) => ({
        ...row,
        deal_id: row.deal?.id ?? row.deal_id ?? "",
        deal_name: row.deal?.name ?? "",
      }));
    },
  });
  return {
    meetings: q.data ?? [],
    isLoading: q.isLoading,
  };
}
