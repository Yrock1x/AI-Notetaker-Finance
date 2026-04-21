"use client";

import { useState } from "react";
import { CalendarClock, Video } from "lucide-react";
import { useUpcomingUnassigned } from "@/hooks/use-upcoming-unassigned";
import { AssignMeetingDialog } from "@/components/meetings/assign-meeting-dialog";
import type { Meeting } from "@/types";

const SOURCE_LABEL: Record<string, string> = {
  zoom: "Zoom",
  teams: "Teams",
  meet: "Meet",
  upload: "Upload",
};

// Hidden when the user has nothing to triage — the dashboard shouldn't
// spawn empty-state chrome for things that don't exist yet.
export function UpcomingUnassignedWidget() {
  const { data: meetings = [] } = useUpcomingUnassigned();
  const [active, setActive] = useState<Meeting | null>(null);

  if (meetings.length === 0) return null;

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarClock className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">
            Upcoming meetings to assign
          </h2>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            {meetings.length}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          Attach to a deal so the bot joins automatically.
        </p>
      </div>

      <div className="space-y-2">
        {meetings.map((m) => {
          const when = m.meeting_date || m.created_at;
          return (
            <div
              key={m.id}
              className="flex items-center justify-between rounded-lg border bg-white p-3 hover:shadow-sm"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{m.title}</p>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    {new Date(when).toLocaleString([], {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium">
                    <Video className="h-3 w-3" />
                    {SOURCE_LABEL[m.source] ?? m.source}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActive(m)}
                className="ml-3 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
              >
                Assign…
              </button>
            </div>
          );
        })}
      </div>

      <AssignMeetingDialog
        meeting={active}
        open={active !== null}
        onClose={() => setActive(null)}
      />
    </section>
  );
}
