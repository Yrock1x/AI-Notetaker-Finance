"use client";

// Aggregate stats for the deal Overview KPI strip — derived in the
// browser from the `meetings` and `analyses` rows (rather than a
// dedicated server endpoint), so it stays in sync with whatever RLS
// returns and doesn't require a new API route.

import { useQuery } from "@tanstack/react-query";
import { getBrowserSupabase } from "@/lib/supabase/browser";
import { useDealExtractions } from "./use-deal-extractions";

export interface DealStats {
  meetingsThisWeek: { value: number; delta: number; trend: "up" | "down" | "flat"; sub: string };
  hoursCaptured: { value: number; sub: string };
  actionItems: { value: number; dueThisWeek: number };
  decisions: { value: number };
  questions: { value: number; answered: number };
  totalMeetings: number;
}

interface MeetingStat {
  id: string;
  meeting_date: string | null;
  duration_seconds: number | null;
  created_at: string;
}

const ONE_WEEK_MS = 7 * 24 * 60 * 60 * 1000;

export function useDealStats(dealId: string | undefined): {
  data?: DealStats;
  isLoading: boolean;
} {
  const meetingsQ = useQuery<MeetingStat[]>({
    queryKey: ["deal-stats-meetings", dealId],
    enabled: !!dealId,
    staleTime: 30_000,
    queryFn: async () => {
      const supabase = getBrowserSupabase();
      const { data, error } = await supabase
        .from("meetings")
        .select("id, meeting_date, duration_seconds, created_at")
        .eq("deal_id", dealId!);
      if (error) throw error;
      return (data ?? []) as MeetingStat[];
    },
  });

  const extractionsQ = useDealExtractions(dealId);

  const data = ((): DealStats | undefined => {
    const meetings = meetingsQ.data;
    const ext = extractionsQ.data;
    if (!meetings || !ext) return undefined;

    const now = Date.now();
    const thisWeekStart = now - ONE_WEEK_MS;
    const lastWeekStart = thisWeekStart - ONE_WEEK_MS;

    const dateOf = (m: MeetingStat) =>
      new Date(m.meeting_date || m.created_at).getTime();

    const thisWeek = meetings.filter((m) => dateOf(m) >= thisWeekStart).length;
    const lastWeek = meetings.filter(
      (m) => dateOf(m) >= lastWeekStart && dateOf(m) < thisWeekStart,
    ).length;
    const trend: "up" | "down" | "flat" =
      thisWeek > lastWeek ? "up" : thisWeek < lastWeek ? "down" : "flat";

    const totalSeconds = meetings.reduce(
      (acc, m) => acc + (m.duration_seconds || 0),
      0,
    );
    const hours = totalSeconds / 3600;

    const dueThisWeek = ext.actions.filter((a) => {
      if (!a.due) return false;
      const t = Date.parse(a.due);
      if (isNaN(t)) return false;
      return t >= now && t <= now + ONE_WEEK_MS;
    }).length;

    return {
      meetingsThisWeek: {
        value: thisWeek,
        delta: thisWeek - lastWeek,
        trend,
        sub: "vs last week",
      },
      hoursCaptured: {
        value: Math.round(hours * 10) / 10,
        sub: `across ${meetings.length} call${meetings.length === 1 ? "" : "s"}`,
      },
      actionItems: { value: ext.actions.length, dueThisWeek },
      decisions: { value: ext.decisions.length },
      questions: {
        value: ext.questions.filter((q) => !q.answered).length,
        answered: ext.questions.filter((q) => q.answered).length,
      },
      totalMeetings: meetings.length,
    };
  })();

  return {
    data,
    isLoading: meetingsQ.isLoading || extractionsQ.isLoading,
  };
}
