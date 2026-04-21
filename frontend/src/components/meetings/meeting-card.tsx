import type { ReactNode } from "react";
import type { Meeting } from "@/types";
import { MEETING_STATUS_LABELS } from "@/lib/constants";
import { formatDuration, cn } from "@/lib/utils";
import { Calendar, Clock, Mic } from "lucide-react";

interface MeetingCardProps {
  meeting: Meeting;
  // "archive" suppresses the "Upcoming" label on meetings that ran past
  // their scheduled time without ever recording — shows "Missed" instead.
  // Every other status label/color is unchanged.
  variant?: "active" | "archive";
  // Optional right-side slot (e.g. a ToggleSwitch) so callers can hang
  // extra controls next to the status badge without forking this card.
  rightSlot?: ReactNode;
}

const STATUS_COLORS: Record<string, string> = {
  scheduled: "bg-blue-100 text-blue-800",
  recording: "bg-red-100 text-red-800",
  processing: "bg-yellow-100 text-yellow-800",
  transcribed: "bg-green-100 text-green-800",
  analyzed: "bg-purple-100 text-purple-800",
  failed: "bg-red-100 text-red-800",
};

export function MeetingCard({
  meeting,
  variant = "active",
  rightSlot,
}: MeetingCardProps) {
  const isMissed = variant === "archive" && meeting.status === "scheduled";
  const badgeLabel = isMissed
    ? "Missed"
    : (MEETING_STATUS_LABELS[meeting.status] ?? meeting.status);
  const badgeClass = isMissed
    ? "bg-gray-100 text-gray-600"
    : (STATUS_COLORS[meeting.status] ?? "bg-gray-100 text-gray-800");

  return (
    <div className="group flex items-center justify-between rounded-lg border bg-white p-4 transition-shadow hover:shadow-md">
      <div className="flex items-start gap-3">
        <div className="rounded-md bg-primary/10 p-2 text-primary">
          <Mic className="h-4 w-4" />
        </div>
        <div>
          <h3 className="font-medium group-hover:text-primary">
            {meeting.title}
          </h3>
          <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {new Date(
                meeting.meeting_date || meeting.created_at
              ).toLocaleString([], {
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
              })}
            </span>
            <span>{meeting.source}</span>
            {meeting.duration_seconds != null && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDuration(meeting.duration_seconds)}
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {rightSlot}
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            badgeClass
          )}
        >
          {badgeLabel}
        </span>
      </div>
    </div>
  );
}
