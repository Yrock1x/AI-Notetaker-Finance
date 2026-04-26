"use client";

// Calendar — month / week / agenda views over every meeting in the user's
// orgs. Adds a stats strip, status filter chips, a Today button, a Today
// + Next-7-days agenda rail, live-meeting pulse animation, and a
// click-empty-day-to-schedule shortcut into the ScheduleBotDialog.

import { useMemo, useState } from "react";
import Link from "next/link";
import { useCalendarMeetings } from "@/hooks/use-calendar";
import type { CalendarMeeting } from "@/hooks/use-calendar";
import { useBotSessions } from "@/hooks/use-bot-sessions";
import type { BotSession } from "@/hooks/use-bot-sessions";
import { useToggleMeetingBot } from "@/hooks/use-meetings";
import { LoadingState } from "@/components/shared/loading-state";
import { ScheduleBotDialog } from "@/components/meetings/schedule-bot-dialog";
import { AssignMeetingDialog } from "@/components/meetings/assign-meeting-dialog";
import { ToggleSwitch } from "@/components/ui/toggle-switch";
import { getBrowserSupabase } from "@/lib/supabase/browser";
import { useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Mic,
  Plus,
  RefreshCw,
  Video,
} from "lucide-react";

const DAYS_OF_WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const DEAL_COLORS: Record<
  number,
  { bg: string; text: string; dot: string; toggle: string; ring: string }
> = {
  0: {
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    dot: "bg-emerald-500",
    toggle: "bg-emerald-500",
    ring: "ring-emerald-200",
  },
  1: {
    bg: "bg-blue-50",
    text: "text-blue-700",
    dot: "bg-blue-500",
    toggle: "bg-blue-500",
    ring: "ring-blue-200",
  },
  2: {
    bg: "bg-purple-50",
    text: "text-purple-700",
    dot: "bg-purple-500",
    toggle: "bg-purple-500",
    ring: "ring-purple-200",
  },
};

function getDealColorIndex(dealId: string, allDealIds: string[]): number {
  const index = allDealIds.indexOf(dealId);
  return Math.max(0, index) % 3;
}

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 1).getDay();
}

function formatTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

type View = "month" | "week" | "agenda";
type StatusFilter = "all" | "live" | "upcoming" | "past";

const BOT_STATUS_LABELS: Record<
  BotSession["status"],
  { label: string; className: string }
> = {
  scheduled: { label: "Upcoming", className: "bg-blue-100 text-blue-700" },
  joining: { label: "Joining…", className: "bg-amber-100 text-amber-700" },
  recording: { label: "Recording", className: "bg-red-100 text-red-700" },
  completed: {
    label: "Completed",
    className: "bg-emerald-100 text-emerald-700",
  },
  failed: { label: "Failed", className: "bg-red-50 text-red-500" },
  cancelled: {
    label: "Cancelled",
    className: "bg-[#1A1A1A]/5 text-[#1A1A1A]/50",
  },
};

function meetingTimestamp(m: CalendarMeeting): number {
  return new Date(m.meeting_date || m.created_at).getTime();
}

function classifyStatus(
  m: CalendarMeeting,
  session: BotSession | undefined,
): StatusFilter {
  if (m.status === "recording" || session?.status === "recording") return "live";
  const t = meetingTimestamp(m);
  if (t > Date.now()) return "upcoming";
  return "past";
}

interface MeetingCardProps {
  meeting: CalendarMeeting;
  colorIndex: number;
  botEnabled: boolean;
  botStatus?: BotSession["status"];
  isLive: boolean;
  onToggleBot: () => void;
}

function UnassignedMeetingCard({
  meeting,
  onClick,
}: {
  meeting: CalendarMeeting;
  onClick: () => void;
}) {
  const meetingTime = meeting.meeting_date || meeting.created_at;
  return (
    <button
      type="button"
      onClick={onClick}
      className="block w-full rounded-xl border border-dashed border-[#1A1A1A]/10 bg-[#F2F0E9]/40 p-2 text-left transition-colors hover:border-primary/30 hover:bg-[#F2F0E9]/70"
      title="Click to assign this meeting to a deal."
    >
      <p className="truncate text-[11px] font-semibold text-[#1A1A1A]/70">
        {meeting.title}
      </p>
      <div className="mt-0.5 flex items-center gap-1">
        <span className="h-1.5 w-1.5 rounded-full bg-[#1A1A1A]/20" />
        <span className="truncate text-[10px] text-[#1A1A1A]/50">
          Click to assign
        </span>
      </div>
      <div className="mt-0.5 flex items-center gap-1 text-[10px] text-[#1A1A1A]/40">
        <Clock className="h-2.5 w-2.5" />
        {formatTime(meetingTime)}
      </div>
    </button>
  );
}

function MeetingCard({
  meeting,
  colorIndex,
  botEnabled,
  botStatus,
  isLive,
  onToggleBot,
}: MeetingCardProps) {
  const colors = DEAL_COLORS[colorIndex] || DEAL_COLORS[0];
  const meetingTime = meeting.meeting_date || meeting.created_at;
  const statusChip = botStatus ? BOT_STATUS_LABELS[botStatus] : null;

  return (
    <Link
      href={`/deals/${meeting.deal_id}/meetings/${meeting.id}`}
      className={`group block rounded-xl ${colors.bg} ${
        isLive ? "ring-2 ring-red-300/70 animate-[livepulse_2.2s_ease-in-out_infinite]" : ""
      } p-2 transition-all duration-200 hover:shadow-sm`}
    >
      <div className="flex items-start justify-between gap-1">
        <div className="min-w-0 flex-1">
          <p className={`truncate text-[11px] font-semibold ${colors.text}`}>
            {meeting.title}
          </p>
          <div className="mt-0.5 flex items-center gap-1">
            <span className={`h-1.5 w-1.5 rounded-full ${colors.dot}`} />
            <span className="truncate text-[10px] text-[#1A1A1A]/50">
              {meeting.deal_name}
            </span>
          </div>
          <div className="mt-0.5 flex items-center gap-1 text-[10px] text-[#1A1A1A]/40">
            <Clock className="h-2.5 w-2.5" />
            {formatTime(meetingTime)}
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 pt-0.5">
          <ToggleSwitch
            enabled={botEnabled}
            onToggle={onToggleBot}
            colorClass={colors.toggle}
          />
          {statusChip ? (
            <span
              className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold ${statusChip.className}`}
            >
              {statusChip.label}
            </span>
          ) : botEnabled ? (
            <Video className={`h-2.5 w-2.5 ${colors.text} opacity-60`} />
          ) : null}
        </div>
      </div>
    </Link>
  );
}

export default function CalendarPage() {
  const { meetings, isLoading } = useCalendarMeetings();
  const { data: botSessions = [] } = useBotSessions();
  const queryClient = useQueryClient();
  const toggleBotMutation = useToggleMeetingBot(undefined);

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
      const supabase = getBrowserSupabase();
      const { data: auth } = await supabase.auth.getUser();
      if (!auth.user) throw new Error("not authed");
      const { data: memberships } = await supabase
        .from("org_memberships")
        .select("org_id")
        .eq("user_id", auth.user.id)
        .limit(1);
      const orgId = memberships?.[0]?.org_id;
      if (!orgId) throw new Error("no org");
      await fetch("/api/inngest/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "calendar/refresh.requested",
          data: { org_id: orgId, user_id: auth.user.id },
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

          {/* Right rail */}
          <aside className="space-y-4 lg:sticky lg:top-2">
            {liveNow.length > 0 && (
              <div className="rounded-2xl border border-red-200 bg-red-50/40 p-4">
                <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-red-700">
                  <span className="inline-flex h-2 w-2 animate-pulse rounded-full bg-red-500" />
                  Live now · {liveNow.length}
                </h3>
                <div className="mt-3 space-y-2">
                  {liveNow.map((m) => (
                    <Link
                      key={m.id}
                      href={`/deals/${m.deal_id}/meetings/${m.id}/live`}
                      className="flex items-center gap-2 rounded-lg bg-white px-3 py-2 hover:bg-red-50"
                    >
                      <Mic className="h-3 w-3 text-red-500" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-semibold text-[#1A1A1A]">
                          {m.title}
                        </p>
                        <p className="truncate text-[10px] text-[#1A1A1A]/50">
                          {m.deal_name}
                        </p>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            <div className="rounded-2xl border border-[#1A1A1A]/5 bg-white p-4">
              <h3 className="text-xs font-bold uppercase tracking-widest text-[#1A1A1A]/40">
                Today · {today.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
              </h3>
              <div className="mt-3 space-y-2">
                {todayMeetings.length === 0 ? (
                  <p className="text-xs text-[#1A1A1A]/40">
                    Nothing on the schedule. Click a day cell to add one.
                  </p>
                ) : (
                  todayMeetings.map((m) => {
                    const colors =
                      DEAL_COLORS[
                        m.deal_id ? getDealColorIndex(m.deal_id, allDealIds) : 0
                      ];
                    return (
                      <Link
                        key={m.id}
                        href={
                          m.deal_id
                            ? `/deals/${m.deal_id}/meetings/${m.id}`
                            : "#"
                        }
                        onClick={(e) => {
                          if (!m.deal_id) {
                            e.preventDefault();
                            setAssignTarget(m);
                          }
                        }}
                        className="block rounded-lg border border-[#1A1A1A]/5 px-3 py-2 hover:bg-[#F2F0E9]/40"
                      >
                        <div className="flex items-baseline gap-2">
                          <span className="font-data text-[10px] font-semibold text-[#1A1A1A]/40">
                            {formatTime(m.meeting_date || m.created_at)}
                          </span>
                          <p className="truncate text-xs font-semibold text-[#1A1A1A]">
                            {m.title}
                          </p>
                        </div>
                        <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-[#1A1A1A]/50">
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${colors.dot}`}
                          />
                          {m.deal_name || "Unassigned"}
                        </div>
                      </Link>
                    );
                  })
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-[#1A1A1A]/5 bg-white p-4">
              <h3 className="text-xs font-bold uppercase tracking-widest text-[#1A1A1A]/40">
                Next 7 days
              </h3>
              <div className="mt-3 space-y-2">
                {upcomingWeek.length === 0 ? (
                  <p className="text-xs text-[#1A1A1A]/40">
                    Nothing scheduled. Refresh from your calendar provider or
                    schedule a notetaker.
                  </p>
                ) : (
                  upcomingWeek.map((m) => {
                    const d = new Date(m.meeting_date || m.created_at);
                    const colors =
                      DEAL_COLORS[
                        m.deal_id ? getDealColorIndex(m.deal_id, allDealIds) : 0
                      ];
                    return (
                      <Link
                        key={m.id}
                        href={
                          m.deal_id
                            ? `/deals/${m.deal_id}/meetings/${m.id}`
                            : "#"
                        }
                        onClick={(e) => {
                          if (!m.deal_id) {
                            e.preventDefault();
                            setAssignTarget(m);
                          }
                        }}
                        className="grid grid-cols-[auto_1fr] items-center gap-3 rounded-lg border border-[#1A1A1A]/5 px-3 py-2 hover:bg-[#F2F0E9]/40"
                      >
                        <div className="rounded-md bg-[#F2F0E9] px-2 py-1 text-center">
                          <div className="text-[8px] font-bold uppercase tracking-wider text-[#1A1A1A]/40">
                            {d.toLocaleDateString(undefined, {
                              month: "short",
                            })}
                          </div>
                          <div className="font-data text-sm font-bold text-[#1A1A1A]">
                            {d.getDate()}
                          </div>
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-xs font-semibold text-[#1A1A1A]">
                            {m.title}
                          </p>
                          <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-[#1A1A1A]/50">
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${colors.dot}`}
                            />
                            {m.deal_name || "Unassigned"} ·{" "}
                            {formatTime(m.meeting_date || m.created_at)}
                          </div>
                        </div>
                      </Link>
                    );
                  })
                )}
              </div>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

function StatTile({
  label,
  value,
  unit,
  sub,
  isLive,
}: {
  label: string;
  value: number;
  unit?: string;
  sub: string;
  isLive?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border bg-white px-4 py-3 ${
        isLive ? "border-red-200" : "border-[#1A1A1A]/5"
      }`}
    >
      <p className="text-[10.5px] font-bold uppercase tracking-widest text-[#1A1A1A]/40">
        {label}
      </p>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="font-data text-2xl font-bold text-[#1A1A1A]">
          {value}
        </span>
        {unit && (
          <span className="text-sm font-semibold text-[#1A1A1A]/50">
            {unit}
          </span>
        )}
        {isLive && (
          <span className="ml-auto inline-flex h-2 w-2 animate-pulse rounded-full bg-red-500" />
        )}
      </div>
      <p className="mt-0.5 text-[10.5px] text-[#1A1A1A]/50">{sub}</p>
    </div>
  );
}

interface BaseViewProps {
  meetings: CalendarMeeting[];
  allDealIds: string[];
  isBotEnabled: (m: CalendarMeeting) => boolean;
  sessionByMeetingId: Record<string, BotSession>;
  onToggleBot: (m: CalendarMeeting, current: boolean) => void;
  onAssign: (m: CalendarMeeting) => void;
}

interface MonthViewProps extends Omit<BaseViewProps, "meetings"> {
  year: number;
  month: number;
  onPrev: () => void;
  onNext: () => void;
  meetingsByDay: Record<string, CalendarMeeting[]>;
  isToday: (day: number) => boolean;
  onDayClick: (day: number) => void;
}

function MonthView({
  year,
  month,
  onPrev,
  onNext,
  meetingsByDay,
  allDealIds,
  isBotEnabled,
  sessionByMeetingId,
  isToday,
  onDayClick,
  onToggleBot,
  onAssign,
}: MonthViewProps) {
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfMonth(year, month);
  const totalCells = Math.ceil((firstDay + daysInMonth) / 7) * 7;
  return (
    <>
      <div className="mb-8 flex items-center justify-between">
        <button
          onClick={onPrev}
          className="rounded-full p-2 text-[#1A1A1A]/40 transition-colors hover:bg-[#F2F0E9] hover:text-[#1A1A1A]"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h2 className="font-heading text-2xl font-bold text-primary">
          {MONTH_NAMES[month]} {year}
        </h2>
        <button
          onClick={onNext}
          className="rounded-full p-2 text-[#1A1A1A]/40 transition-colors hover:bg-[#F2F0E9] hover:text-[#1A1A1A]"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-px">
        {DAYS_OF_WEEK.map((day) => (
          <div
            key={day}
            className="pb-3 text-center font-data text-xs font-bold text-[#1A1A1A]/40"
          >
            {day}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-px rounded-[2rem] border border-[#1A1A1A]/5 overflow-hidden bg-[#1A1A1A]/5">
        {Array.from({ length: totalCells }, (_, i) => {
          const day = i - firstDay + 1;
          const isCurrentMonth = day >= 1 && day <= daysInMonth;
          const dayMeetings = isCurrentMonth ? meetingsByDay[day] || [] : [];
          return (
            <div
              key={i}
              onClick={
                isCurrentMonth && dayMeetings.length === 0
                  ? () => onDayClick(day)
                  : undefined
              }
              className={`group relative min-h-[120px] p-2 ${
                isCurrentMonth ? "bg-white" : "bg-[#F2F0E9]/50"
              } ${
                isCurrentMonth && dayMeetings.length === 0
                  ? "cursor-pointer hover:bg-[#F2F0E9]/70"
                  : ""
              }`}
            >
              {isCurrentMonth && (
                <>
                  <div className="mb-1 flex items-center justify-end">
                    <span
                      className={`flex h-6 w-6 items-center justify-center rounded-full font-data text-xs font-semibold ${
                        isToday(day)
                          ? "bg-primary text-white"
                          : "text-[#1A1A1A]/70"
                      }`}
                    >
                      {day}
                    </span>
                  </div>
                  <div className="space-y-1">
                    {dayMeetings.map((meeting) =>
                      meeting.deal_id ? (
                        <MeetingCard
                          key={meeting.id}
                          meeting={meeting}
                          colorIndex={getDealColorIndex(
                            meeting.deal_id,
                            allDealIds,
                          )}
                          botEnabled={isBotEnabled(meeting)}
                          botStatus={sessionByMeetingId[meeting.id]?.status}
                          isLive={
                            classifyStatus(
                              meeting,
                              sessionByMeetingId[meeting.id],
                            ) === "live"
                          }
                          onToggleBot={() =>
                            onToggleBot(meeting, isBotEnabled(meeting))
                          }
                        />
                      ) : (
                        <UnassignedMeetingCard
                          key={meeting.id}
                          meeting={meeting}
                          onClick={() => onAssign(meeting)}
                        />
                      ),
                    )}
                  </div>
                  {dayMeetings.length === 0 && (
                    <span className="absolute bottom-2 left-2 hidden items-center gap-1 text-[10px] text-[#1A1A1A]/30 group-hover:flex">
                      <Plus className="h-2.5 w-2.5" /> schedule
                    </span>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

interface WeekViewProps extends BaseViewProps {
  anchor: Date;
  onPrev: () => void;
  onNext: () => void;
  onScheduleAt: (date: Date) => void;
}

function WeekView({
  anchor,
  onPrev,
  onNext,
  meetings,
  allDealIds,
  isBotEnabled,
  sessionByMeetingId,
  onToggleBot,
  onAssign,
  onScheduleAt,
}: WeekViewProps) {
  const startOfWeek = new Date(anchor);
  startOfWeek.setDate(anchor.getDate() - anchor.getDay());
  startOfWeek.setHours(0, 0, 0, 0);
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startOfWeek);
    d.setDate(startOfWeek.getDate() + i);
    return d;
  });
  const meetingsByDay = useMemo(() => {
    const map: Record<string, CalendarMeeting[]> = {};
    meetings.forEach((m) => {
      const d = new Date(m.meeting_date || m.created_at);
      d.setHours(0, 0, 0, 0);
      const key = d.toISOString();
      (map[key] ||= []).push(m);
    });
    return map;
  }, [meetings]);
  const todayKey = (() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d.toISOString();
  })();
  const rangeLabel = `${days[0].toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${days[6].toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;

  return (
    <>
      <div className="mb-8 flex items-center justify-between">
        <button
          onClick={onPrev}
          className="rounded-full p-2 text-[#1A1A1A]/40 transition-colors hover:bg-[#F2F0E9] hover:text-[#1A1A1A]"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h2 className="font-heading text-2xl font-bold text-primary">
          {rangeLabel}
        </h2>
        <button
          onClick={onNext}
          className="rounded-full p-2 text-[#1A1A1A]/40 transition-colors hover:bg-[#F2F0E9] hover:text-[#1A1A1A]"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>
      <div className="grid grid-cols-7 gap-3">
        {days.map((d, i) => {
          const key = d.toISOString();
          const dayMeetings = (meetingsByDay[key] ?? []).sort(
            (a, b) => meetingTimestamp(a) - meetingTimestamp(b),
          );
          const isCurrent = key === todayKey;
          return (
            <div
              key={i}
              className={`rounded-xl border p-2 min-h-[280px] ${
                isCurrent
                  ? "border-primary/30 bg-primary/5"
                  : "border-[#1A1A1A]/5 bg-white"
              }`}
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="font-data text-[10px] font-bold uppercase tracking-widest text-[#1A1A1A]/40">
                  {DAYS_OF_WEEK[d.getDay()]}
                </span>
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full font-data text-xs font-semibold ${
                    isCurrent
                      ? "bg-primary text-white"
                      : "text-[#1A1A1A]/70"
                  }`}
                >
                  {d.getDate()}
                </span>
              </div>
              <div className="space-y-1">
                {dayMeetings.length === 0 ? (
                  <button
                    type="button"
                    onClick={() => onScheduleAt(d)}
                    className="flex h-full w-full items-center justify-center rounded-lg border border-dashed border-[#1A1A1A]/10 p-4 text-[10px] font-medium text-[#1A1A1A]/30 hover:border-primary/30 hover:text-[#1A1A1A]/60"
                  >
                    <Plus className="mr-1 h-3 w-3" /> schedule
                  </button>
                ) : (
                  dayMeetings.map((meeting) =>
                    meeting.deal_id ? (
                      <MeetingCard
                        key={meeting.id}
                        meeting={meeting}
                        colorIndex={getDealColorIndex(
                          meeting.deal_id,
                          allDealIds,
                        )}
                        botEnabled={isBotEnabled(meeting)}
                        botStatus={sessionByMeetingId[meeting.id]?.status}
                        isLive={
                          classifyStatus(
                            meeting,
                            sessionByMeetingId[meeting.id],
                          ) === "live"
                        }
                        onToggleBot={() =>
                          onToggleBot(meeting, isBotEnabled(meeting))
                        }
                      />
                    ) : (
                      <UnassignedMeetingCard
                        key={meeting.id}
                        meeting={meeting}
                        onClick={() => onAssign(meeting)}
                      />
                    ),
                  )
                )}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

function AgendaView({
  meetings,
  allDealIds,
  isBotEnabled,
  sessionByMeetingId,
  onToggleBot,
  onAssign,
}: BaseViewProps) {
  const sorted = [...meetings].sort(
    (a, b) => meetingTimestamp(a) - meetingTimestamp(b),
  );
  const groups = useMemo(() => {
    const map = new Map<string, CalendarMeeting[]>();
    for (const m of sorted) {
      const d = new Date(m.meeting_date || m.created_at);
      const key = d.toLocaleDateString(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
      });
      const arr = map.get(key) ?? [];
      arr.push(m);
      map.set(key, arr);
    }
    return [...map.entries()];
  }, [sorted]);

  if (groups.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-[#1A1A1A]/40">
        No meetings match this filter.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {groups.map(([day, items]) => (
        <section key={day}>
          <h3 className="mb-3 font-heading text-sm font-bold text-[#1A1A1A]/70">
            {day}
          </h3>
          <div className="space-y-2">
            {items.map((meeting) =>
              meeting.deal_id ? (
                <div
                  key={meeting.id}
                  className="grid grid-cols-[auto_1fr]"
                  style={{ gap: 12 }}
                >
                  <span className="pt-2 font-data text-xs font-semibold text-[#1A1A1A]/40">
                    {formatTime(meeting.meeting_date || meeting.created_at)}
                  </span>
                  <MeetingCard
                    meeting={meeting}
                    colorIndex={getDealColorIndex(
                      meeting.deal_id,
                      allDealIds,
                    )}
                    botEnabled={isBotEnabled(meeting)}
                    botStatus={sessionByMeetingId[meeting.id]?.status}
                    isLive={
                      classifyStatus(
                        meeting,
                        sessionByMeetingId[meeting.id],
                      ) === "live"
                    }
                    onToggleBot={() =>
                      onToggleBot(meeting, isBotEnabled(meeting))
                    }
                  />
                </div>
              ) : (
                <div
                  key={meeting.id}
                  className="grid grid-cols-[auto_1fr]"
                  style={{ gap: 12 }}
                >
                  <span className="pt-2 font-data text-xs font-semibold text-[#1A1A1A]/40">
                    {formatTime(meeting.meeting_date || meeting.created_at)}
                  </span>
                  <UnassignedMeetingCard
                    meeting={meeting}
                    onClick={() => onAssign(meeting)}
                  />
                </div>
              ),
            )}
          </div>
        </section>
      ))}
    </div>
  );
}
