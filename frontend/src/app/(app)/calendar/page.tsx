"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useCalendarMeetings } from "@/hooks/use-calendar";
import type { CalendarMeeting } from "@/hooks/use-calendar";
import { LoadingState } from "@/components/shared/loading-state";
import { ChevronLeft, ChevronRight, Clock, Video } from "lucide-react";

const DAYS_OF_WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const DEAL_COLORS: Record<number, { bg: string; text: string; dot: string; toggle: string }> = {
  0: {
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    dot: "bg-emerald-500",
    toggle: "bg-emerald-500",
  },
  1: {
    bg: "bg-blue-50",
    text: "text-blue-700",
    dot: "bg-blue-500",
    toggle: "bg-blue-500",
  },
  2: {
    bg: "bg-purple-50",
    text: "text-purple-700",
    dot: "bg-purple-500",
    toggle: "bg-purple-500",
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
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

interface ToggleSwitchProps {
  enabled: boolean;
  onToggle: () => void;
  colorClass: string;
}

function ToggleSwitch({ enabled, onToggle, colorClass }: ToggleSwitchProps) {
  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onToggle();
      }}
      className={`relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border border-[#1A1A1A]/10 transition-colors duration-200 ease-in-out focus:outline-none ${
        enabled ? colorClass : "bg-[#1A1A1A]/10"
      }`}
      role="switch"
      aria-checked={enabled}
      title="Toggle Deal Companion bot"
    >
      <span
        className={`pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          enabled ? "translate-x-3" : "translate-x-0"
        }`}
      />
    </button>
  );
}

interface MeetingCardProps {
  meeting: CalendarMeeting;
  colorIndex: number;
  botEnabled: boolean;
  onToggleBot: () => void;
}

function MeetingCard({ meeting, colorIndex, botEnabled, onToggleBot }: MeetingCardProps) {
  const colors = DEAL_COLORS[colorIndex] || DEAL_COLORS[0];
  const meetingTime = meeting.meeting_date || meeting.created_at;

  return (
    <Link
      href={`/deals/${meeting.deal_id}/meetings/${meeting.id}`}
      className={`group block rounded-xl ${colors.bg} p-2 transition-all duration-200 hover:shadow-sm`}
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
          {botEnabled && (
            <Video className={`h-2.5 w-2.5 ${colors.text} opacity-60`} />
          )}
        </div>
      </div>
    </Link>
  );
}

export default function CalendarPage() {
  const { meetings, isLoading } = useCalendarMeetings();
  const today = new Date();
  const [currentYear, setCurrentYear] = useState(today.getFullYear());
  const [currentMonth, setCurrentMonth] = useState(today.getMonth());
  const [botOverrides, setBotOverrides] = useState<Record<string, boolean>>({});
  const [hiddenDeals, setHiddenDeals] = useState<Set<string>>(new Set());

  const allDealIds = useMemo(() => {
    const ids = new Set<string>();
    meetings.forEach((m) => ids.add(m.deal_id));
    return Array.from(ids);
  }, [meetings]);

  const toggleDeal = (dealId: string) => {
    setHiddenDeals((prev) => {
      const next = new Set(prev);
      if (next.has(dealId)) {
        next.delete(dealId);
      } else {
        next.add(dealId);
      }
      return next;
    });
  };

  const meetingsByDay = useMemo(() => {
    const map: Record<string, CalendarMeeting[]> = {};
    meetings.forEach((meeting) => {
      if (hiddenDeals.has(meeting.deal_id)) return;
      const dateStr = meeting.meeting_date || meeting.created_at;
      const date = new Date(dateStr);
      if (date.getFullYear() === currentYear && date.getMonth() === currentMonth) {
        const day = date.getDate();
        if (!map[day]) map[day] = [];
        map[day].push(meeting);
      }
    });
    return map;
  }, [meetings, currentYear, currentMonth, hiddenDeals]);

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

  const isBotEnabled = (meeting: CalendarMeeting) => {
    if (meeting.id in botOverrides) return botOverrides[meeting.id];
    return meeting.bot_enabled !== false;
  };

  const toggleBot = (meetingId: string, currentValue: boolean) => {
    setBotOverrides((prev) => ({
      ...prev,
      [meetingId]: !currentValue,
    }));
  };

  const daysInMonth = getDaysInMonth(currentYear, currentMonth);
  const firstDay = getFirstDayOfMonth(currentYear, currentMonth);
  const totalCells = Math.ceil((firstDay + daysInMonth) / 7) * 7;

  const isToday = (day: number) =>
    day === today.getDate() &&
    currentMonth === today.getMonth() &&
    currentYear === today.getFullYear();

  return (
    <div className="space-y-10 antialiased">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-4xl font-heading font-extrabold tracking-tight text-primary">
          Meeting Calendar
        </h1>
        <p className="font-subheading text-[#1A1A1A]/60 text-lg font-medium leading-relaxed">
          Scheduled meetings across all active deals. Toggle Deal Companion to
          auto-join and record.
        </p>
      </div>

      {/* Deal filters */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-subheading text-xs font-medium text-[#1A1A1A]/40 mr-1">Filter by deal:</span>
        {allDealIds.map((dealId, i) => {
          const colors = DEAL_COLORS[i % 3];
          const dealName = meetings.find((m) => m.deal_id === dealId)?.deal_name || dealId;
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
              <span className={`h-2.5 w-2.5 rounded-full transition-colors ${isVisible ? colors.dot : "bg-[#1A1A1A]/20"}`} />
              <span className="font-subheading text-xs font-bold text-[#1A1A1A]/60">
                {dealName}
              </span>
            </button>
          );
        })}
      </div>

      {isLoading ? (
        <LoadingState message="Loading calendar data..." />
      ) : (
        <div className="rounded-[2.5rem] border border-[#1A1A1A]/5 bg-white p-8 shadow-sm">
          {/* Month navigation */}
          <div className="mb-8 flex items-center justify-between">
            <button
              onClick={handlePrevMonth}
              className="rounded-full p-2 text-[#1A1A1A]/40 transition-colors hover:bg-[#F2F0E9] hover:text-[#1A1A1A]"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <h2 className="font-heading text-2xl font-bold text-primary">
              {MONTH_NAMES[currentMonth]} {currentYear}
            </h2>
            <button
              onClick={handleNextMonth}
              className="rounded-full p-2 text-[#1A1A1A]/40 transition-colors hover:bg-[#F2F0E9] hover:text-[#1A1A1A]"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>

          {/* Day-of-week headers */}
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

          {/* Calendar grid */}
          <div className="grid grid-cols-7 gap-px rounded-[2rem] border border-[#1A1A1A]/5 overflow-hidden bg-[#1A1A1A]/5">
            {Array.from({ length: totalCells }, (_, i) => {
              const day = i - firstDay + 1;
              const isCurrentMonth = day >= 1 && day <= daysInMonth;
              const dayMeetings = isCurrentMonth ? meetingsByDay[day] || [] : [];

              return (
                <div
                  key={i}
                  className={`min-h-[120px] p-2 ${
                    isCurrentMonth ? "bg-white" : "bg-[#F2F0E9]/50"
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
                        {dayMeetings.map((meeting) => (
                          <MeetingCard
                            key={meeting.id}
                            meeting={meeting}
                            colorIndex={getDealColorIndex(meeting.deal_id, allDealIds)}
                            botEnabled={isBotEnabled(meeting)}
                            onToggleBot={() => toggleBot(meeting.id, isBotEnabled(meeting))}
                          />
                        ))}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
