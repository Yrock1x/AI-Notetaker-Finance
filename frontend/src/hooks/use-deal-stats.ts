"use client";

// Aggregate stats for the deal Overview KPI strip — derived in the
// browser from the `meetings` and `analyses` rows (rather than a
// dedicated server endpoint), so it stays in sync with whatever RLS
// returns and doesn't require a new API route.

import type { Meeting } from "@/types";
import { useMeetings } from "./use-meetings";
import { useDealExtractions } from "./use-deal-extractions";

export interface DealStats {
  meetingsThisWeek: { value: number; delta: number; trend: "up" | "down" | "flat"; sub: string };
  hoursCaptured: { value: number; sub: string };
  actionItems: { value: number; dueThisWeek: number };
  decisions: { value: number };
  questions: { value: number; answered: number };
  totalMeetings: number;
}

const ONE_WEEK_MS = 7 * 24 * 60 * 60 * 1000;

export function useDealStats(dealId: string | undefined): {
  data?: DealStats;
  isLoading: boolean;
} {
  // Reuse the shared meetings query (same ["meetings", dealId] cache entry as
  // useMeetings / useDealExtractions) rather than fetching /meetings again.
  const meetingsQ = useMeetings(dealId);

  const extractionsQ = useDealExtractions(dealId);

  const data = ((): DealStats | undefined => {
    const meetings = meetingsQ.data?.items;
    const ext = extractionsQ.data;
    if (!meetings || !ext) return undefined;

    const now = Date.now();
    const thisWeekStart = now - ONE_WEEK_MS;
    const lastWeekStart = thisWeekStart - ONE_WEEK_MS;

    const dateOf = (m: Meeting) =>
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
