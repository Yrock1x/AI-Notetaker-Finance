"use client";

// Calendar — month / week / agenda views over every meeting in the user's
// orgs. This page owns the state (view, filters, navigation) and data
// wiring; the layouts live in components/calendar/ (views, meeting cards,
// stats tile, agenda rail).

import { useMemo, useState } from "react";
import { useCalendarMeetings } from "@/hooks/use-calendar";
import type { CalendarMeeting } from "@/hooks/use-calendar";
import { useBotSessions } from "@/hooks/use-bot-sessions";
import type { BotSession } from "@/hooks/use-bot-sessions";
import { useToggleMeetingBot } from "@/hooks/use-meetings";
import { LoadingState } from "@/components/shared/loading-state";
import { ScheduleBotDialog } from "@/components/meetings/schedule-bot-dialog";
import { AssignMeetingDialog } from "@/components/meetings/assign-meeting-dialog";
import {
  DEAL_COLORS,
  MONTH_NAMES,
  classifyStatus,
  meetingTimestamp,
  type StatusFilter,
  type View,
} from "@/components/calendar/constants";
import { CalendarRail } from "@/components/calendar/calendar-rail";
import { StatTile } from "@/components/calendar/stat-tile";
import {
  AgendaView,
  MonthView,
  WeekView,
} from "@/components/calendar/views";
import { useOrg } from "@/hooks/use-org";
import { useSession } from "@/hooks/use-session";
import { useQueryClient } from "@tanstack/react-query";
import { Bot, CalendarDays, RefreshCw } from "lucide-react";

export default function CalendarPage() {
  const { meetings, isLoading } = useCalendarMeetings();
  const { data: botSessions = [] } = useBotSessions();
  const queryClient = useQueryClient();
  const toggleBotMutation = useToggleMeetingBot(undefined);
  const { currentOrg } = useOrg();
  const { user } = useSession();

  const today = new Date();
  const [view, setView] = useState<View>("month");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [currentYear, setCurrentYear] = useState(today.getFullYear());
  const [currentMonth, setCurrentMonth] = useState(today.getMonth());
  const [weekAnchor, setWeekAnchor] = useState<Date>(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  });
  const [botOverrides, setBotOverrides] = useState<Record<string, boolean>>({});
  const [hiddenDeals, setHiddenDeals] = useState<Set<string>>(new Set());
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [scheduleDefault, setScheduleDefault] = useState<string | undefined>(
    undefined,
  );
  const [assignTarget, setAssignTarget] = useState<CalendarMeeting | null>(
    null,
  );
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      const orgId = currentOrg?.id;
      const userId = user?.id;
      if (!userId) throw new Error("not authed");
      if (!orgId) throw new Error("no org");
      await fetch("/api/inngest/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "calendar/refresh.requested",
          data: { org_id: orgId, user_id: userId },
        }),
      });
      await new Promise((r) => setTimeout(r, 4000));
      await queryClient.invalidateQueries({
        queryKey: ["calendar", "meetings"],
      });
    } catch (err) {
      console.error("calendar refresh failed", err);
    } finally {
      setRefreshing(false);
    }
  };

  const sessionByMeetingId = useMemo(() => {
    const map: Record<string, BotSession> = {};
    for (const s of botSessions) {
      if (!s.meeting_id) continue;
      if (s.status === "cancelled" || s.status === "failed") continue;
      map[s.meeting_id] = s;
    }
    return map;
  }, [botSessions]);

  const allDealIds = useMemo(() => {
    const ids = new Set<string>();
    meetings.forEach((m) => {
      if (m.deal_id) ids.add(m.deal_id);
    });
    return Array.from(ids);
  }, [meetings]);

  // Stats — scoped to whatever the current view's window is, so the strip
  // mirrors what the user is actually looking at.
  const monthStats = useMemo(() => {
    const inMonth = meetings.filter((m) => {
      const d = new Date(m.meeting_date || m.created_at);
      return (
        d.getFullYear() === currentYear && d.getMonth() === currentMonth
      );
    });
    const totalSeconds = inMonth.reduce(
      (acc, m) => acc + (m.duration_seconds || 0),
      0,
    );
    const liveCount = inMonth.filter((m) => {
      const s = sessionByMeetingId[m.id];
      return classifyStatus(m, s) === "live";
    }).length;
    const upcomingCount = inMonth.filter(
      (m) => classifyStatus(m, sessionByMeetingId[m.id]) === "upcoming",
    ).length;
    const botEnabled = inMonth.filter((m) => m.bot_enabled !== false).length;
    return {
      total: inMonth.length,
      hours: Math.round((totalSeconds / 3600) * 10) / 10,
      live: liveCount,
      upcoming: upcomingCount,
      botEnabled,
    };
  }, [meetings, currentYear, currentMonth, sessionByMeetingId]);

  const filteredMeetings = useMemo(() => {
    return meetings.filter((m) => {
      if (m.deal_id && hiddenDeals.has(m.deal_id)) return false;
      if (statusFilter === "all") return true;
      const s = sessionByMeetingId[m.id];
      return classifyStatus(m, s) === statusFilter;
    });
  }, [meetings, hiddenDeals, statusFilter, sessionByMeetingId]);

  const meetingsByDay = useMemo(() => {
    const map: Record<string, CalendarMeeting[]> = {};
    filteredMeetings.forEach((meeting) => {
      const dateStr = meeting.meeting_date || meeting.created_at;
      const date = new Date(dateStr);
      if (
        date.getFullYear() === currentYear &&
        date.getMonth() === currentMonth
      ) {
        const day = date.getDate();
        if (!map[day]) map[day] = [];
        map[day].push(meeting);
      }
    });
    return map;
  }, [filteredMeetings, currentYear, currentMonth]);

  const handlePrevMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear(currentYear - 1);
    } else {
      setCurrentMonth(currentMonth - 1);
    }
  };

  const handleNextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear(currentYear + 1);
    } else {
      setCurrentMonth(currentMonth + 1);
    }
  };

  const goToToday = () => {
    setCurrentMonth(today.getMonth());
    setCurrentYear(today.getFullYear());
    const wk = new Date(today);
    wk.setHours(0, 0, 0, 0);
    setWeekAnchor(wk);
  };

  const toggleDeal = (dealId: string) => {
    setHiddenDeals((prev) => {
      const next = new Set(prev);
      if (next.has(dealId)) next.delete(dealId);
      else next.add(dealId);
      return next;
    });
  };

  const isBotEnabled = (meeting: CalendarMeeting) => {
    if (meeting.id in botOverrides) return botOverrides[meeting.id];
    return meeting.bot_enabled !== false;
  };

  const toggleBot = async (meeting: CalendarMeeting, currentValue: boolean) => {
    const next = !currentValue;
    setBotOverrides((prev) => ({ ...prev, [meeting.id]: next }));
    try {
      await toggleBotMutation.mutateAsync({
        meetingId: meeting.id,
        bot_enabled: next,
      });
    } catch {
      setBotOverrides((prev) => ({ ...prev, [meeting.id]: currentValue }));
    }
  };

  const openScheduleAt = (date: Date) => {
    // Round forward to the next half-hour slot for a sensible default.
    const d = new Date(date);
    const minutes = d.getMinutes();
    const rounded = minutes < 30 ? 30 : 60;
    d.setMinutes(rounded, 0, 0);
    // Format YYYY-MM-DDTHH:MM in local time for the datetime-local input.
    const pad = (n: number) => n.toString().padStart(2, "0");
    const iso = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    setScheduleDefault(iso);
    setScheduleOpen(true);
  };

  const isToday = (year: number, month: number, day: number) =>
    day === today.getDate() &&
    month === today.getMonth() &&
    year === today.getFullYear();

  const liveNow = meetings.filter(
    (m) => classifyStatus(m, sessionByMeetingId[m.id]) === "live",
  );
  const upcomingWeek = useMemo(() => {
    const now = Date.now();
    const limit = now + 7 * 24 * 60 * 60 * 1000;
    return filteredMeetings
      .filter((m) => {
        const t = meetingTimestamp(m);
        return t >= now && t <= limit;
      })
      .sort((a, b) => meetingTimestamp(a) - meetingTimestamp(b))
      .slice(0, 8);
  }, [filteredMeetings]);

  const todayMeetings = useMemo(() => {
    return filteredMeetings
      .filter((m) => {
        const d = new Date(m.meeting_date || m.created_at);
        return (
          d.getFullYear() === today.getFullYear() &&
          d.getMonth() === today.getMonth() &&
          d.getDate() === today.getDate()
        );
      })
      .sort((a, b) => meetingTimestamp(a) - meetingTimestamp(b));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filteredMeetings]);

  return (
    <div className="space-y-6 antialiased">
      {/* Live pulse keyframes — local since the calendar uses its own
          warm-beige palette and not the workspace tokens. */}
      <style jsx global>{`
        @keyframes livepulse {
          0%,
          100% {
            box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.4);
          }
          50% {
            box-shadow: 0 0 0 8px rgba(220, 38, 38, 0);
          }
        }
      `}</style>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-4xl font-heading font-extrabold tracking-tight text-primary">
            Meeting Calendar
          </h1>
          <p className="font-subheading text-[#1A1A1A]/60 text-lg font-medium leading-relaxed">
            Scheduled meetings across all active deals. Toggle CogniSuite to
            auto-join and record.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 self-start">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-md border border-[#1A1A1A]/10 bg-white px-3 py-2 text-sm font-medium text-[#1A1A1A]/70 transition-colors hover:bg-[#F2F0E9] disabled:opacity-60"
            title="Pull fresh events from your calendar providers"
          >
            <RefreshCw
              className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
          <button
            onClick={() => {
              setScheduleDefault(undefined);
              setScheduleOpen(true);
            }}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Bot className="h-4 w-4" />
            Schedule Notetaker
          </button>
        </div>
      </div>

      <ScheduleBotDialog
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
        defaultStart={scheduleDefault}
      />
      <AssignMeetingDialog
        meeting={assignTarget}
        open={assignTarget !== null}
        onClose={() => setAssignTarget(null)}
      />

      {/* Stats strip */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatTile
          label="Meetings · this view"
          value={monthStats.total}
          sub={`in ${MONTH_NAMES[currentMonth]}`}
        />
        <StatTile
          label="Hours captured"
          value={monthStats.hours}
          unit="h"
          sub={`across ${monthStats.total} call${monthStats.total === 1 ? "" : "s"}`}
        />
        <StatTile
          label="Upcoming"
          value={monthStats.upcoming}
          sub="this month"
        />
        <StatTile
          label="Bot enabled"
          value={monthStats.botEnabled}
          sub="will auto-join"
        />
        <StatTile
          label="Live now"
          value={monthStats.live}
          sub={monthStats.live > 0 ? "recording" : "no live calls"}
          isLive={monthStats.live > 0}
        />
      </div>

      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-3">
        {/* View toggle */}
        <div className="inline-flex gap-0.5 rounded-md border border-[#1A1A1A]/10 bg-white p-0.5">
          {(["month", "week", "agenda"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`rounded px-3 py-1.5 text-xs font-semibold transition-colors capitalize ${
                view === v
                  ? "bg-primary text-primary-foreground"
                  : "text-[#1A1A1A]/60 hover:bg-[#F2F0E9]"
              }`}
            >
              {v}
            </button>
          ))}
        </div>

        <button
          onClick={goToToday}
          className="inline-flex items-center gap-1.5 rounded-md border border-[#1A1A1A]/10 bg-white px-3 py-1.5 text-xs font-semibold text-[#1A1A1A]/70 hover:bg-[#F2F0E9]"
        >
          <CalendarDays className="h-3 w-3" />
          Today
        </button>

        {/* Status filter chips */}
        <div className="inline-flex gap-0.5 rounded-md border border-[#1A1A1A]/10 bg-white p-0.5">
          {(
            [
              { value: "all", label: "All" },
              { value: "live", label: "Live" },
              { value: "upcoming", label: "Upcoming" },
              { value: "past", label: "Past" },
            ] as { value: StatusFilter; label: string }[]
          ).map((opt) => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value)}
              className={`rounded px-3 py-1.5 text-xs font-semibold transition-colors ${
                statusFilter === opt.value
                  ? "bg-primary text-primary-foreground"
                  : "text-[#1A1A1A]/60 hover:bg-[#F2F0E9]"
              }`}
            >
              {opt.label}
              {opt.value === "live" && monthStats.live > 0 && (
                <span className="ml-1 inline-flex h-1.5 w-1.5 animate-pulse rounded-full bg-red-500 align-middle" />
              )}
            </button>
          ))}
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-3">
          <span className="font-subheading text-xs font-medium text-[#1A1A1A]/40">
            Filter by deal:
          </span>
          {allDealIds.map((dealId, i) => {
            const colors = DEAL_COLORS[i % 3];
            const dealName =
              meetings.find((m) => m.deal_id === dealId)?.deal_name || dealId;
            const isVisible = !hiddenDeals.has(dealId);
            return (
              <button
                key={dealId}
                onClick={() => toggleDeal(dealId)}
                className={`flex items-center gap-2 rounded-full px-3 py-1.5 border transition-all duration-200 ${
                  isVisible
                    ? `${colors.bg} border-transparent`
                    : "bg-white border-[#1A1A1A]/10 opacity-50"
                }`}
              >
                <span
                  className={`h-2.5 w-2.5 rounded-full transition-colors ${
                    isVisible ? colors.dot : "bg-[#1A1A1A]/20"
                  }`}
                />
                <span className="font-subheading text-xs font-bold text-[#1A1A1A]/60">
                  {dealName}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {isLoading ? (
        <LoadingState message="Loading calendar data..." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px] items-start">
          <div className="rounded-[2.5rem] border border-[#1A1A1A]/5 bg-white p-8 shadow-sm">
            {view === "month" && (
              <MonthView
                year={currentYear}
                month={currentMonth}
                onPrev={handlePrevMonth}
                onNext={handleNextMonth}
                meetingsByDay={meetingsByDay}
                allDealIds={allDealIds}
                isBotEnabled={isBotEnabled}
                sessionByMeetingId={sessionByMeetingId}
                isToday={(d) => isToday(currentYear, currentMonth, d)}
                onDayClick={(day) => {
                  const d = new Date(currentYear, currentMonth, day, 9, 0, 0);
                  openScheduleAt(d);
                }}
                onToggleBot={toggleBot}
                onAssign={(m) => setAssignTarget(m)}
              />
            )}
            {view === "week" && (
              <WeekView
                anchor={weekAnchor}
                onPrev={() =>
                  setWeekAnchor(
                    (a) => new Date(a.getTime() - 7 * 24 * 60 * 60 * 1000),
                  )
                }
                onNext={() =>
                  setWeekAnchor(
                    (a) => new Date(a.getTime() + 7 * 24 * 60 * 60 * 1000),
                  )
                }
                meetings={filteredMeetings}
                allDealIds={allDealIds}
                isBotEnabled={isBotEnabled}
                sessionByMeetingId={sessionByMeetingId}
                onToggleBot={toggleBot}
                onAssign={(m) => setAssignTarget(m)}
                onScheduleAt={openScheduleAt}
              />
            )}
            {view === "agenda" && (
              <AgendaView
                meetings={filteredMeetings}
                allDealIds={allDealIds}
                isBotEnabled={isBotEnabled}
                sessionByMeetingId={sessionByMeetingId}
                onToggleBot={toggleBot}
                onAssign={(m) => setAssignTarget(m)}
              />
            )}
          </div>

          <CalendarRail
            today={today}
            liveNow={liveNow}
            todayMeetings={todayMeetings}
            upcomingWeek={upcomingWeek}
            allDealIds={allDealIds}
            onAssign={(m) => setAssignTarget(m)}
          />
        </div>
      )}
    </div>
  );
}
