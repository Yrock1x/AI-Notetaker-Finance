"use client";

// The calendar's sticky right rail: Live Now, Today, and Next-7-days agenda
// sections. Unassigned meetings open the assign dialog instead of navigating.

import Link from "next/link";
import { Mic } from "lucide-react";
import type { CalendarMeeting } from "@/hooks/use-calendar";
import { DEAL_COLORS, formatTime, getDealColorIndex } from "./constants";

interface CalendarRailProps {
  today: Date;
  liveNow: CalendarMeeting[];
  todayMeetings: CalendarMeeting[];
  upcomingWeek: CalendarMeeting[];
  allDealIds: string[];
  onAssign: (m: CalendarMeeting) => void;
}

export function CalendarRail({
  today,
  liveNow,
  todayMeetings,
  upcomingWeek,
  allDealIds,
  onAssign,
}: CalendarRailProps) {
  return (
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
                  <p className="truncate text-xs font-semibold text-ink">
                    {m.title}
                  </p>
                  <p className="truncate text-[10px] text-ink/50">
                    {m.deal_name}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-2xl border border-ink/5 bg-white p-4">
        <h3 className="text-xs font-bold uppercase tracking-widest text-ink/40">
          Today · {today.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
        </h3>
        <div className="mt-3 space-y-2">
          {todayMeetings.length === 0 ? (
            <p className="text-xs text-ink/40">
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
                      onAssign(m);
                    }
                  }}
                  className="block rounded-lg border border-ink/5 px-3 py-2 hover:bg-[#F2F0E9]/40"
                >
                  <div className="flex items-baseline gap-2">
                    <span className="font-data text-[10px] font-semibold text-ink/40">
                      {formatTime(m.meeting_date || m.created_at)}
                    </span>
                    <p className="truncate text-xs font-semibold text-ink">
                      {m.title}
                    </p>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-ink/50">
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

      <div className="rounded-2xl border border-ink/5 bg-white p-4">
        <h3 className="text-xs font-bold uppercase tracking-widest text-ink/40">
          Next 7 days
        </h3>
        <div className="mt-3 space-y-2">
          {upcomingWeek.length === 0 ? (
            <p className="text-xs text-ink/40">
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
                      onAssign(m);
                    }
                  }}
                  className="grid grid-cols-[auto_1fr] items-center gap-3 rounded-lg border border-ink/5 px-3 py-2 hover:bg-[#F2F0E9]/40"
                >
                  <div className="rounded-md bg-[#F2F0E9] px-2 py-1 text-center">
                    <div className="text-[8px] font-bold uppercase tracking-wider text-ink/40">
                      {d.toLocaleDateString(undefined, {
                        month: "short",
                      })}
                    </div>
                    <div className="font-data text-sm font-bold text-ink">
                      {d.getDate()}
                    </div>
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-ink">
                      {m.title}
                    </p>
                    <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-ink/50">
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
  );
}
