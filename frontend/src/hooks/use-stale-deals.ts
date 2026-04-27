"use client";

import { useMemo } from "react";
import { useDeals } from "./use-deals";
import { useCalendarMeetings } from "./use-calendar";
import { DealStatus, type Deal } from "@/types";

export interface StaleDeal {
  deal: Deal;
  lastMeetingAt: Date | null;
  daysSince: number | null;
}

export function useStaleDeals(daysThreshold = 14) {
  const { data: dealsResp, isLoading: dealsLoading } = useDeals();
  const { meetings, isLoading: meetingsLoading } = useCalendarMeetings();

  const stale = useMemo(() => {
    const deals = dealsResp?.items ?? [];
    const activeDeals = deals.filter((d) => d.status === DealStatus.ACTIVE);

    const latestByDeal = new Map<string, number>();
    for (const m of meetings) {
      if (!m.deal_id) continue;
      const t = m.meeting_date ? new Date(m.meeting_date).getTime() : NaN;
      if (!Number.isFinite(t)) continue;
      const prev = latestByDeal.get(m.deal_id);
      if (prev === undefined || t > prev) latestByDeal.set(m.deal_id, t);
    }

    const now = Date.now();
    const thresholdMs = daysThreshold * 24 * 60 * 60 * 1000;
    const result: StaleDeal[] = [];
    for (const deal of activeDeals) {
      const last = latestByDeal.get(deal.id);
      if (last === undefined) {
        result.push({ deal, lastMeetingAt: null, daysSince: null });
      } else if (now - last > thresholdMs) {
        result.push({
          deal,
          lastMeetingAt: new Date(last),
          daysSince: Math.floor((now - last) / (24 * 60 * 60 * 1000)),
        });
      }
    }
    return result.sort((a, b) => {
      // Never-met deals first, then oldest meetings.
      const aT = a.lastMeetingAt?.getTime() ?? 0;
      const bT = b.lastMeetingAt?.getTime() ?? 0;
      return aT - bT;
    });
  }, [dealsResp, meetings, daysThreshold]);

  return {
    staleDeals: stale,
    isLoading: dealsLoading || meetingsLoading,
  };
}
