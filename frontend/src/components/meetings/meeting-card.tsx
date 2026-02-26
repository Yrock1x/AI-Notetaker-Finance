import type { Meeting } from "@/types";
import { MEETING_STATUS_LABELS } from "@/lib/constants";
import { formatDuration, cn } from "@/lib/utils";
import { Calendar, Clock, Mic } from "lucide-react";

interface MeetingCardProps {
  meeting: Meeting;
}

const STATUS_COLORS: Record<string, string> = {
  scheduled: "bg-blue-100 text-blue-800",
  recording: "bg-red-100 text-red-800",
  processing: "bg-yellow-100 text-yellow-800",
  transcribed: "bg-green-100 text-green-800",
  analyzed: "bg-purple-100 text-purple-800",
  failed: "bg-red-100 text-red-800",
};

export function MeetingCard({ meeting }: MeetingCardProps) {
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
              {new Date(meeting.created_at).toLocaleDateString()}
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
      <span
        className={cn(
          "rounded-full px-2 py-0.5 text-xs font-medium",
          STATUS_COLORS[meeting.status] ?? "bg-gray-100 text-gray-800"
        )}
      >
        {MEETING_STATUS_LABELS[meeting.status] ?? meeting.status}
      </span>
    </div>
  );
}
