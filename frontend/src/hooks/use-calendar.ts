"use client";

// Calendar = all meetings across deals in the user's active org. One
// Supabase query joins meetings + deal name so the calendar page doesn't
// need a N+1 fan-out.

import { useQuery } from "@tanstack/react-query";
import type { Meeting } from "@/types";
import { getBrowserSupabase } from "@/lib/supabase/browser";

export interface CalendarMeeting extends Meeting {
  deal_name: string;
  deal_id: string;
}

export function useCalendarMeetings() {
  const q = useQuery<CalendarMeeting[]>({
    queryKey: ["calendar", "meetings"],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("meetings")
        .select("*, deal:deals(id, name)")
        .order("meeting_date", { ascending: false })
        .limit(500);
      if (error) throw error;
      return (data ?? []).map((row) => {
        const deal = Array.isArray(row.deal) ? row.deal[0] : row.deal;
        return {
          ...row,
          deal_id: deal?.id ?? row.deal_id ?? "",
          deal_name: deal?.name ?? "",
        } as CalendarMeeting;
      });
    },
  });
  return {
    meetings: q.data ?? [],
    isLoading: q.isLoading,
  };
}
