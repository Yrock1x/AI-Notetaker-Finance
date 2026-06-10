// Shared calendar domain helpers: deal color assignment, date math, and the
// live/upcoming/past classification used by the views, the stats strip, and
// the agenda rail.

import type { CalendarMeeting } from "@/hooks/use-calendar";
import type { BotSession } from "@/hooks/use-bot-sessions";

export const DAYS_OF_WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export const MONTH_NAMES = [
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

export const DEAL_COLORS: Record<
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

export function getDealColorIndex(dealId: string, allDealIds: string[]): number {
  const index = allDealIds.indexOf(dealId);
  return Math.max(0, index) % 3;
}

export function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

export function getFirstDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 1).getDay();
}

export function formatTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export type View = "month" | "week" | "agenda";
export type StatusFilter = "all" | "live" | "upcoming" | "past";

export const BOT_STATUS_LABELS: Record<
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

export function meetingTimestamp(m: CalendarMeeting): number {
  return new Date(m.meeting_date || m.created_at).getTime();
}

// A call is treated as "live" only if it's actually happening right now.
// Without a time-window guard, any meeting whose status got stuck at
// "recording" (bot crashed, Recall never fired its done webhook, etc.)
// would show up in the Live Now rail forever, even on days when the
// calendar is empty.
export const LIVE_WINDOW_MS = 6 * 60 * 60 * 1000;

export function isSessionLive(session: BotSession | undefined): boolean {
  if (!session) return false;
  if (session.status !== "recording") return false;
  if (session.actual_end) return false;
  const startStr = session.actual_start ?? session.scheduled_start;
  if (!startStr) return false;
  const startedAt = new Date(startStr).getTime();
  if (Number.isNaN(startedAt)) return false;
  return Date.now() - startedAt < LIVE_WINDOW_MS;
}

export function classifyStatus(
  m: CalendarMeeting,
  session: BotSession | undefined,
): StatusFilter {
  if (isSessionLive(session)) return "live";
  if (m.status === "recording") {
    const startedAt = meetingTimestamp(m);
    if (Date.now() - startedAt < LIVE_WINDOW_MS) return "live";
  }
  const t = meetingTimestamp(m);
  if (t > Date.now()) return "upcoming";
  return "past";
}
