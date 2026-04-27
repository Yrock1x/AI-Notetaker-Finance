"use client";

import { useMemo } from "react";
import { useCalendarMeetings, type CalendarMeeting } from "./use-calendar";
import { useBotSessions, type BotSession } from "./use-bot-sessions";

export interface TodayMeeting extends CalendarMeeting {
  isLive: boolean;
  joinUrl: string | null;
}

function startOfToday(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function endOfToday(): Date {
  const d = new Date();
  d.setHours(23, 59, 59, 999);
  return d;
}

export function useTodayMeetings() {
  const { meetings, isLoading: meetingsLoading } = useCalendarMeetings();
  const { data: botSessions = [], isLoading: botsLoading } = useBotSessions();

  const today = useMemo(() => {
    const start = startOfToday().getTime();
    const end = endOfToday().getTime();
    const liveByMeeting = new Map<string, BotSession>();
    for (const b of botSessions) {
      if (b.meeting_id && b.status === "recording") {
        liveByMeeting.set(b.meeting_id, b);
      }
    }
    return meetings
      .filter((m) => {
        const t = m.meeting_date ? new Date(m.meeting_date).getTime() : NaN;
        return Number.isFinite(t) && t >= start && t <= end;
      })
      .sort((a, b) => {
        const ta = new Date(a.meeting_date ?? a.created_at).getTime();
        const tb = new Date(b.meeting_date ?? b.created_at).getTime();
        return ta - tb;
      })
      .map<TodayMeeting>((m) => ({
        ...m,
        isLive: liveByMeeting.has(m.id),
        joinUrl: m.source_url ?? null,
      }));
  }, [meetings, botSessions]);

  return {
    meetings: today,
    isLoading: meetingsLoading || botsLoading,
  };
}
