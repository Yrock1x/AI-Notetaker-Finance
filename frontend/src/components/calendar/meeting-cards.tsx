"use client";

// The two meeting chips rendered inside every calendar view: deal-assigned
// (colored, links to the meeting, bot toggle) and unassigned (dashed,
// click-to-assign).

import Link from "next/link";
import { Clock, Video } from "lucide-react";
import type { CalendarMeeting } from "@/hooks/use-calendar";
import type { BotSession } from "@/hooks/use-bot-sessions";
import { ToggleSwitch } from "@/components/ui/toggle-switch";
import { BOT_STATUS_LABELS, DEAL_COLORS, formatTime } from "./constants";

export interface MeetingCardProps {
  meeting: CalendarMeeting;
  colorIndex: number;
  botEnabled: boolean;
  botStatus?: BotSession["status"];
  isLive: boolean;
  onToggleBot: () => void;
}

export function UnassignedMeetingCard({
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
      className="block w-full rounded-xl border border-dashed border-ink/10 bg-[#F2F0E9]/40 p-2 text-left transition-colors hover:border-primary/30 hover:bg-[#F2F0E9]/70"
      title="Click to assign this meeting to a deal."
    >
      <p className="truncate text-[11px] font-semibold text-ink/70">
        {meeting.title}
      </p>
      <div className="mt-0.5 flex items-center gap-1">
        <span className="h-1.5 w-1.5 rounded-full bg-ink/20" />
        <span className="truncate text-[10px] text-ink/50">
          Click to assign
        </span>
      </div>
      <div className="mt-0.5 flex items-center gap-1 text-[10px] text-ink/40">
        <Clock className="h-2.5 w-2.5" />
        {formatTime(meetingTime)}
      </div>
    </button>
  );
}

export function MeetingCard({
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
            <span className="truncate text-[10px] text-ink/50">
              {meeting.deal_name}
            </span>
          </div>
          <div className="mt-0.5 flex items-center gap-1 text-[10px] text-ink/40">
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
