"use client";

import { useState } from "react";
import { CalendarClock, Video } from "lucide-react";
import { useScribeTheme } from "@/components/cogniscribe/theme-provider";
import { useUpcomingUnassigned } from "@/hooks/use-upcoming-unassigned";
import { AssignMeetingDialog } from "@/components/meetings/assign-meeting-dialog";
import type { Meeting } from "@/types";

const SOURCE_LABEL: Record<string, string> = {
  zoom: "Zoom",
  teams: "Teams",
  meet: "Meet",
  google_meet: "Meet",
  upload: "Upload",
};

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function NeedsAttention() {
  const { isDark } = useScribeTheme();
  const { data: unassigned = [], isLoading } = useUpcomingUnassigned();
  const [active, setActive] = useState<Meeting | null>(null);

  const hasNothing = !isLoading && unassigned.length === 0;
  const totalCount = unassigned.length;

  return (
    <section
      className={`rounded-2xl border p-6 ${
        isDark
          ? "bg-[#121212] border-white/10"
          : "bg-white border-black/[0.06]"
      }`}
    >
      <div className="flex items-center gap-3 mb-5">
        <span className="inline-block h-5 w-1 rounded-full bg-gradient-to-b from-amber-400 to-amber-600" />
        <span
          className={`text-[10px] font-medium tracking-[0.22em] uppercase ${
            isDark ? "text-amber-300/80" : "text-amber-600"
          }`}
        >
          Needs attention
        </span>
        {totalCount > 0 && (
          <span
            className={`ml-auto inline-flex items-center justify-center min-w-[22px] h-[22px] px-1.5 rounded-full text-[10.5px] font-semibold tabular-nums ${
              isDark
                ? "bg-amber-500/15 text-amber-300"
                : "bg-amber-100 text-amber-700"
            }`}
          >
            {totalCount}
          </span>
        )}
      </div>

      {hasNothing && (
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <div
            className={`inline-flex h-10 w-10 items-center justify-center rounded-full mb-3 ${
              isDark ? "bg-emerald-500/10 text-emerald-300" : "bg-emerald-50 text-emerald-600"
            }`}
          >
            ✓
          </div>
          <p className={`text-sm ${isDark ? "text-white/55" : "text-black/55"}`}>
            You&apos;re all clear — every meeting is assigned to a deal.
          </p>
        </div>
      )}

      {unassigned.length > 0 && (
        <div className="mb-5">
          <div className="flex items-center gap-2 mb-2">
            <CalendarClock className={`h-3.5 w-3.5 ${isDark ? "text-indigo-300" : "text-indigo-600"}`} />
            <h3 className={`text-[12.5px] font-semibold ${isDark ? "text-white/85" : "text-black/85"}`}>
              {unassigned.length} unassigned {unassigned.length === 1 ? "meeting" : "meetings"}
            </h3>
          </div>
          <ul className="space-y-1.5">
            {unassigned.slice(0, 4).map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  onClick={() => setActive(m)}
                  className={`w-full text-left flex items-center gap-3 rounded-xl px-3 py-2 transition-colors border ${
                    isDark
                      ? "border-transparent hover:border-indigo-400/20 hover:bg-indigo-500/[0.05]"
                      : "border-transparent hover:border-indigo-200 hover:bg-indigo-50/40"
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{m.title}</p>
                    <p className={`text-[11px] ${isDark ? "text-white/45" : "text-black/45"}`}>
                      {formatWhen(m.meeting_date || m.created_at)}
                    </p>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      isDark ? "bg-white/[0.06] text-white/65" : "bg-black/[0.04] text-black/65"
                    }`}
                  >
                    <Video className="h-2.5 w-2.5" />
                    {SOURCE_LABEL[m.source] ?? m.source}
                  </span>
                  <span
                    className={`text-[11px] font-medium ${
                      isDark ? "text-indigo-300" : "text-indigo-600"
                    }`}
                  >
                    Assign →
                  </span>
                </button>
              </li>
            ))}
            {unassigned.length > 4 && (
              <li className={`text-[11px] pl-3 ${isDark ? "text-white/40" : "text-black/40"}`}>
                + {unassigned.length - 4} more
              </li>
            )}
          </ul>
        </div>
      )}

      <AssignMeetingDialog
        meeting={active}
        open={active !== null}
        onClose={() => setActive(null)}
      />
    </section>
  );
}
