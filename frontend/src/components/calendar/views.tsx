"use client";

// The three calendar layouts — month grid, week columns, agenda list. All
// render the shared MeetingCard/UnassignedMeetingCard chips and receive their
// data + callbacks from the page (which owns state and fetching).

import { useMemo } from "react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import type { CalendarMeeting } from "@/hooks/use-calendar";
import type { BotSession } from "@/hooks/use-bot-sessions";
import {
  DAYS_OF_WEEK,
  MONTH_NAMES,
  classifyStatus,
  getDaysInMonth,
  getDealColorIndex,
  getFirstDayOfMonth,
  meetingTimestamp,
  formatTime,
} from "./constants";
import { MeetingCard, UnassignedMeetingCard } from "./meeting-cards";

export interface BaseViewProps {
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

export function MonthView({
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
          className="rounded-full p-2 text-ink/40 transition-colors hover:bg-[#F2F0E9] hover:text-ink"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h2 className="font-heading text-2xl font-bold text-primary">
          {MONTH_NAMES[month]} {year}
        </h2>
        <button
          onClick={onNext}
          className="rounded-full p-2 text-ink/40 transition-colors hover:bg-[#F2F0E9] hover:text-ink"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-px">
        {DAYS_OF_WEEK.map((day) => (
          <div
            key={day}
            className="pb-3 text-center font-data text-xs font-bold text-ink/40"
          >
            {day}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-px rounded-[2rem] border border-ink/5 overflow-hidden bg-ink/5">
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
                          : "text-ink/70"
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
                    <span className="absolute bottom-2 left-2 hidden items-center gap-1 text-[10px] text-ink/30 group-hover:flex">
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

export function WeekView({
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
          className="rounded-full p-2 text-ink/40 transition-colors hover:bg-[#F2F0E9] hover:text-ink"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h2 className="font-heading text-2xl font-bold text-primary">
          {rangeLabel}
        </h2>
        <button
          onClick={onNext}
          className="rounded-full p-2 text-ink/40 transition-colors hover:bg-[#F2F0E9] hover:text-ink"
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
                  : "border-ink/5 bg-white"
              }`}
            >
              <div className="mb-2 flex items-center justify-between">
                <span className="font-data text-[10px] font-bold uppercase tracking-widest text-ink/40">
                  {DAYS_OF_WEEK[d.getDay()]}
                </span>
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full font-data text-xs font-semibold ${
                    isCurrent
                      ? "bg-primary text-white"
                      : "text-ink/70"
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
                    className="flex h-full w-full items-center justify-center rounded-lg border border-dashed border-ink/10 p-4 text-[10px] font-medium text-ink/30 hover:border-primary/30 hover:text-ink/60"
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

export function AgendaView({
  meetings,
  allDealIds,
  isBotEnabled,
  sessionByMeetingId,
  onToggleBot,
  onAssign,
}: BaseViewProps) {
  const groups = useMemo(() => {
    const sorted = [...meetings].sort(
      (a, b) => meetingTimestamp(a) - meetingTimestamp(b),
    );
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
  }, [meetings]);

  if (groups.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-ink/40">
        No meetings match this filter.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {groups.map(([day, items]) => (
        <section key={day}>
          <h3 className="mb-3 font-heading text-sm font-bold text-ink/70">
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
                  <span className="pt-2 font-data text-xs font-semibold text-ink/40">
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
                  <span className="pt-2 font-data text-xs font-semibold text-ink/40">
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
