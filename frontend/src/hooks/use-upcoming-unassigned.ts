"use client";

// Feeds the Dashboard "Upcoming meetings to assign" widget. Pulls
// calendar-synced meetings in the next 7 days that haven't been
// attached to a deal yet. Hidden entirely when the list is empty.

import { useQuery } from "@tanstack/react-query";
import { getBrowserSupabase } from "@/lib/supabase/browser";
import type { Meeting } from "@/types";

export function useUpcomingUnassigned() {
  return useQuery<Meeting[]>({
    queryKey: ["dashboard", "upcoming-unassigned"],
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const now = new Date();
      // Include meetings that just started (up to 30 min ago) so a call
      // in progress doesn't vanish from the widget the moment the clock
      // ticks past its start. Future window stays 7 days.
      const floor = new Date(now.getTime() - 30 * 60 * 1000);
      const horizon = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
      const { data, error } = await supabase
        .from("meetings")
        .select("*")
        .is("deal_id", null)
        .not("external_provider", "is", null)
        .gte("meeting_date", floor.toISOString())
        .lte("meeting_date", horizon.toISOString())
        .order("meeting_date", { ascending: true });
      if (error) throw error;
      return (data ?? []) as Meeting[];
    },
    // Reasonably fresh — this lists unassigned rows the user is
    // actively triaging, so we'd rather pay a lookup than show stale
    // state. Still refetch on focus / invalidations (the assign
    // mutation invalidates this key directly).
    staleTime: 30 * 1000,
  });
}
